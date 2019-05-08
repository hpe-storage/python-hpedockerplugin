import six

from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin.cmd.cmd_claimavailableip import ClaimAvailableIPCmd
from hpedockerplugin.cmd.cmd_createfpg import CreateFpgCmd
from hpedockerplugin.cmd.cmd_createvfs import CreateVfsCmd

from hpedockerplugin import exception
from hpedockerplugin.hpe import share

LOG = logging.getLogger(__name__)


class CreateShareCmd(cmd.Cmd):
    def __init__(self, file_mgr, share_args):
        self._file_mgr = file_mgr
        self._etcd = file_mgr.get_etcd()
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._config = file_mgr.get_config()
        self._backend = file_mgr.get_backend()
        self._share_args = share_args
        self._status = 'CREATING'
        self._share_cnt_incremented = False

    def unexecute(self):
        share_name = self._share_args['name']
        LOG.info("cmd::unexecute: Removing share entry from ETCD: %s" %
                 share_name)
        self._etcd.delete_share(share_name)
        if self._status == "AVAILABLE":
            LOG.info("cmd::unexecute: Deleting share from backend: %s" %
                     share_name)
            self._mediator.delete_share(self._share_args['id'])
            self._mediator.delete_file_store(self._share_args['fpg'],
                                             share_name)
        if self._share_cnt_incremented:
            fpg_metadata = self._fp_etcd.get_fpg_metadata(
                self._backend,
                self._share_args['cpg'],
                self._share_args['fpg']
            )
            cnt = int(fpg_metadata['share_cnt']) - 1
            fpg_metadata['share_cnt'] = cnt
            fpg_metadata['reached_full_capacity'] = False
            self._fp_etcd.save_fpg_metadata(self._backend,
                                            self._share_args['cpg'],
                                            self._share_args['fpg'],
                                            fpg_metadata)

    def create_share(self):
        self._create_share()

    def _create_share(self):
        share_etcd = self._file_mgr.get_etcd()
        share_name = self._share_args['name']
        try:
            LOG.info("Creating share %s on the backend" % share_name)
            share_id = self._mediator.create_share(self._share_args)
            self._share_args['id'] = share_id
        except Exception as ex:
            msg = "Share creation failed [share_name: %s, error: %s" %\
                  (share_name, six.text_type(ex))
            LOG.error(msg)
            self.unexecute()
            raise exception.ShareCreationFailed(msg)

        try:
            self._status = 'AVAILABLE'
            self._share_args['status'] = self._status
            share_etcd.save_share(self._share_args)
            # Increment count only if it is Docker managed FPG
            if self._share_args.get('docker_managed'):
                self._increment_share_cnt_for_fpg()
        except Exception as ex:
            msg = "Share creation failed [share_name: %s, error: %s" %\
                  (share_name, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareCreationFailed(msg)

    # FPG lock is already acquired in this flow
    def _increment_share_cnt_for_fpg(self):
        cpg_name = self._share_args['cpg']
        fpg_name = self._share_args['fpg']
        LOG.info("Incrementing share count for FPG %s..." % fpg_name)
        fpg = self._fp_etcd.get_fpg_metadata(self._backend,
                                             cpg_name,
                                             fpg_name)
        cnt = fpg.get('share_cnt', 0) + 1
        fpg['share_cnt'] = cnt
        LOG.info("Checking if count reached full capacity...")
        if cnt >= share.MAX_SHARES_PER_FPG:
            LOG.info("Full capacity on FPG %s reached" % fpg_name)
            fpg['reached_full_capacity'] = True
        LOG.info("Saving modified share count %s to ETCD for FPG %s"
                 % (cnt, fpg_name))
        self._fp_etcd.save_fpg_metadata(self._backend, cpg_name,
                                        fpg_name, fpg)
        self._share_cnt_incremented = True


class CreateShareOnNewFpgCmd(CreateShareCmd):
    def __init__(self, file_mgr, share_args, make_default_fpg=False):
        super(CreateShareOnNewFpgCmd, self).__init__(file_mgr, share_args)
        self._make_default_fpg = make_default_fpg

    def execute(self):
        return self._create_share_on_new_fpg()

    def _create_share_on_new_fpg(self):
        LOG.info("Creating share on new FPG...")
        cpg_name = self._share_args['cpg']
        fpg_name = self._share_args['fpg']
        vfs_name = self._share_args['vfs']
        LOG.info("New FPG name %s" % fpg_name)
        # Since we are creating a new FPG here, CPG must be locked
        # just to avoid any possible duplicate FPG creation
        with self._fp_etcd.get_cpg_lock(self._backend, cpg_name):
            try:
                LOG.info("Creating new FPG %s..." % fpg_name)
                create_fpg_cmd = CreateFpgCmd(
                    self._file_mgr, cpg_name,
                    fpg_name, self._make_default_fpg
                )
                create_fpg_cmd.execute()
            except exception.FpgCreationFailed as ex:
                msg = "Create share on new FPG failed. Msg: %s" \
                      % six.text_type(ex)
                LOG.error(msg)
                raise exception.ShareCreationFailed(reason=msg)

            LOG.info("Trying to claim available IP from IP pool...")
            config = self._file_mgr.get_config()
            claim_free_ip_cmd = ClaimAvailableIPCmd(self._backend,
                                                    config,
                                                    self._fp_etcd)
            try:
                ip, netmask = claim_free_ip_cmd.execute()

                LOG.info("Available IP %s claimed for VFS creation" % ip)
                create_vfs_cmd = CreateVfsCmd(self._file_mgr, cpg_name,
                                              fpg_name, vfs_name, ip, netmask)
                LOG.info("Creating VFS %s with IP %s..." % (vfs_name, ip))
                create_vfs_cmd.execute()
                LOG.info("VFS %s created with IP %s" % (vfs_name, ip))

                # Now that VFS has been created successfully, move the IP from
                # locked-ip-list to ips-in-use list
                LOG.info("Marking IP %s for VFS %s in use" % (ip, vfs_name))
                claim_free_ip_cmd.mark_ip_in_use()
                self._share_args['vfsIPs'] = [(ip, netmask)]

            except exception.IPAddressPoolExhausted as ex:
                msg = "Create VFS failed. Msg: %s" % six.text_type(ex)
                LOG.error(msg)
                raise exception.VfsCreationFailed(reason=msg)
            except exception.VfsCreationFailed as ex:
                msg = "Create share on new FPG failed. Msg: %s" \
                      % six.text_type(ex)
                LOG.error(msg)
                self.unexecute()
                raise exception.ShareCreationFailed(reason=msg)

            self._share_args['fpg'] = fpg_name
            self._share_args['vfs'] = vfs_name

            # All set to create share at this point
            return self._create_share()


class CreateShareOnDefaultFpgCmd(CreateShareCmd):
    def __init__(self, file_mgr, share_args):
        super(CreateShareOnDefaultFpgCmd, self).__init__(file_mgr, share_args)

    def execute(self):
        try:
            fpg_info = self._get_default_available_fpg()
            fpg_name = fpg_info['fpg']
            with self._fp_etcd.get_fpg_lock(self._backend,
                                            self._share_args['cpg'],
                                            fpg_name):
                self._share_args['fpg'] = fpg_name
                self._share_args['vfs'] = fpg_info['vfs']
                # Only one IP per FPG is supported at the moment
                # Given that, list can be dropped
                subnet_ips_map = fpg_info['ips']
                subnet, ips = next(iter(subnet_ips_map.items()))
                self._share_args['vfsIPs'] = [(ips[0], subnet)]
                return self._create_share()
        except Exception as ex:
            # It may be that a share on some full FPG was deleted by
            # the user and as a result leaving an empty slot. Check
            # all the FPGs that were created as default and see if
            # any of those have share count less than MAX_SHARE_PER_FPG
            try:
                cpg = self._share_args['cpg']
                all_fpgs_for_cpg = self._fp_etcd.get_all_fpg_metadata(
                    self._backend, cpg
                )
                for fpg in all_fpgs_for_cpg:
                    fpg_name = fpg['fpg']
                    if fpg_name.startswith("Docker"):
                        with self._fp_etcd.get_fpg_lock(
                                self._backend, cpg, fpg_name):
                            if fpg['share_cnt'] < share.MAX_SHARES_PER_FPG:
                                self._share_args['fpg'] = fpg_name
                                self._share_args['vfs'] = fpg['vfs']
                                # Only one IP per FPG is supported
                                # Given that, list can be dropped
                                subnet_ips_map = fpg['ips']
                                items = subnet_ips_map.items()
                                subnet, ips = next(iter(items))
                                self._share_args['vfsIPs'] = [(ips[0],
                                                               subnet)]
                                return self._create_share()
            except Exception:
                pass
            raise ex

    # If default FPG is full, it raises exception
    # EtcdMaxSharesPerFpgLimitException
    def _get_default_available_fpg(self):
        fpg_name = self._get_current_default_fpg_name()
        fpg_info = self._fp_etcd.get_fpg_metadata(self._backend,
                                                  self._share_args['cpg'],
                                                  fpg_name)
        if fpg_info['share_cnt'] >= share.MAX_SHARES_PER_FPG:
            raise exception.EtcdMaxSharesPerFpgLimitException(
                fpg_name=fpg_name)
        return fpg_info

    def _get_current_default_fpg_name(self):
        cpg_name = self._share_args['cpg']
        try:
            backend_metadata = self._fp_etcd.get_backend_metadata(
                self._backend)
            default_fpgs = backend_metadata.get('default_fpgs')
            if default_fpgs:
                default_fpg = default_fpgs.get(cpg_name)
                if default_fpg:
                    return default_fpg
            raise exception.EtcdDefaultFpgNotPresent(cpg=cpg_name)
        except exception.EtcdMetadataNotFound:
            raise exception.EtcdDefaultFpgNotPresent(cpg=cpg_name)


class CreateShareOnExistingFpgCmd(CreateShareCmd):
    def __init__(self, file_mgr, share_args):
        super(CreateShareOnExistingFpgCmd, self).__init__(file_mgr,
                                                          share_args)

    def execute(self):
        LOG.info("Creating share on existing FPG...")
        fpg_name = self._share_args['fpg']
        cpg_name = self._share_args['cpg']
        LOG.info("Existing FPG name: %s" % fpg_name)
        with self._fp_etcd.get_fpg_lock(self._backend, cpg_name, fpg_name):
            try:
                LOG.info("Checking if FPG %s exists in ETCD...." % fpg_name)
                # Specified FPG may or may not exist. In case it
                # doesn't, EtcdFpgMetadataNotFound exception is raised
                fpg_info = self._fp_etcd.get_fpg_metadata(
                    self._backend, cpg_name, fpg_name)
                LOG.info("FPG %s found" % fpg_name)
                self._share_args['vfs'] = fpg_info['vfs']
                # Only one IP per FPG is supported at the moment
                # Given that, list can be dropped
                subnet_ips_map = fpg_info['ips']
                subnet, ips = next(iter(subnet_ips_map.items()))
                self._share_args['vfsIPs'] = [(ips[0], subnet)]
                LOG.info("Creating share % under FPG %s"
                         % (self._share_args['name'], fpg_name))
                self._create_share()
            except exception.EtcdMetadataNotFound:
                LOG.info("Specified FPG %s not found in ETCD. Checking "
                         "if this is a legacy FPG..." % fpg_name)
                # Assume it's a legacy FPG, try to get details
                fpg_info = self._get_legacy_fpg()

                LOG.info("FPG %s is a legacy FPG" % fpg_name)
                # CPG passed can be different than actual CPG
                # used for creating legacy FPG. Override default
                # or supplied CPG
                if cpg_name != fpg_info['cpg']:
                    msg = ('ERROR: Invalid CPG %s specified or configured in '
                           'hpe.conf for the specified legacy FPG %s. Please '
                           'specify correct CPG as %s' %
                           (cpg_name, fpg_name, fpg_info['cpg']))
                    LOG.error(msg)
                    raise exception.InvalidInput(msg)

                vfs_info = self._get_backend_vfs_for_fpg()
                vfs_name = vfs_info['name']
                ip_info = vfs_info['IPInfo'][0]

                self._share_args['vfs'] = vfs_name
                # Only one IP per FPG is supported at the moment
                # Given that, list can be dropped
                netmask = ip_info['netmask']
                ip = ip_info['IPAddr']
                self._share_args['vfsIPs'] = [(ip, netmask)]
                self._create_share()

    def _get_legacy_fpg(self):
        return self._mediator.get_fpg(self._share_args['fpg'])

    def _get_backend_vfs_for_fpg(self):
        return self._mediator.get_vfs(self._share_args['fpg'])
