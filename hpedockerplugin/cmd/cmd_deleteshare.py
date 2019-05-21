import json
import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception

LOG = logging.getLogger(__name__)


class DeleteShareCmd(cmd.Cmd):
    def __init__(self, file_mgr, share_info):
        self._file_mgr = file_mgr
        self._etcd = file_mgr.get_etcd()
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._backend = file_mgr.get_backend()
        self._share_info = share_info
        self._cpg_name = share_info['cpg']
        self._fpg_name = share_info['fpg']

    def execute(self):
        LOG.info("Delting share %s..." % self._share_info['name'])
        # Most likely nothing got created at the backend when share is
        # not in AVAILABLE state
        if self._share_info['status'] != 'AVAILABLE':
            self._delete_share_from_etcd(self._share_info['name'])
            return json.dumps({u"Err": ''})

        with self._fp_etcd.get_fpg_lock(
                self._backend, self._cpg_name, self._fpg_name):
            self._remove_quota()
            self._delete_share()

            # Decrement count only if it is Docker managed FPG
            if self._share_info.get('docker_managed'):
                self._decrement_share_cnt()

            # If shares are not present on FPG after this delete, then
            # delete the FPG too.
            # WARNING: THIS WILL DELETE LEGACY FPG TOO IF IT BECOMES EMPTY
            if not self._mediator.shares_present_on_fpg(self._fpg_name):
                self._delete_fpg()
                if self._share_info.get('docker_managed'):
                    self._remove_fpg_from_default_fpgs()
            # else:
            #     if self._share_info.get('docker_managed'):
            #         self._add_fpg_to_default_fpgs()
        return json.dumps({u"Err": ''})

    def unexecute(self):
        pass

    def _remove_fpg_from_default_fpgs(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            bkend_metadata = self._fp_etcd.get_backend_metadata(self._backend)
            default_fpgs = bkend_metadata.get('default_fpgs')
            if default_fpgs:
                fpg_list = default_fpgs.get(self._cpg_name)
                if self._fpg_name in fpg_list:
                    fpg_list.remove(self._fpg_name)
                    self._fp_etcd.save_backend_metadata(bkend_metadata)

    # def _add_fpg_to_default_fpgs(self):
    #     # TODO:Imran: Mark FPG as default FPG in FPG metadata
    #     with self._fp_etcd.get_file_backend_lock(self._backend):
    #         bkend_metadata = self._fp_etcd.get_backend_metadata(self._backend)
    #         default_fpgs = bkend_metadata.get('default_fpgs')
    #         if default_fpgs:
    #             fpg_list = default_fpgs.get(self._cpg_name)
    #             fpg_list.append(self._fpg_name)
    #         else:
    #             bkend_metadata['default_fpgs'] = {
    #                 self._cpg_name:[self._fpg_name]
    #             }
    #         self._fp_etcd.save_backend_metadata(bkend_metadata)

    def _remove_quota(self):
        try:
            share = self._etcd.get_share(self._share_info['name'])
            if 'quota_id' in share:
                quota_id = share.pop('quota_id')
                self._mediator.remove_quota(quota_id)
                self._etcd.save_share(share)
        except Exception as ex:
            LOG.error("ERROR: Remove quota failed for %s. %s"
                      % (self._share_info['name'], six.text_type(ex)))

    def _delete_share(self):
        share_name = self._share_info['name']
        LOG.info("cmd_deleteshare:remove_share: Removing %s..." % share_name)
        try:
            LOG.info("Deleting share %s from backend..." % share_name)
            if self._share_info.get('id'):
                self._mediator.delete_share(self._share_info['id'])
            LOG.info("Share %s deleted from backend" % share_name)
            LOG.info("Deleting file store %s from backend..." % share_name)
            self._mediator.delete_file_store(self._fpg_name, share_name)
            LOG.info("File store %s deleted from backend" % share_name)

        except Exception as e:
            msg = 'Failed to remove share %(share_name)s from backend: %(e)s'\
                  % ({'share_name': share_name, 'e': six.text_type(e)})
            LOG.error(msg)
            # Don't raise exception. Continue to delete share
            # raise exception.ShareBackendException(msg=msg)

        self._delete_share_from_etcd(share_name)

    def _delete_share_from_etcd(self, share_name):
        try:
            LOG.info("Removing share entry from ETCD: %s..." % share_name)
            self._etcd.delete_share(share_name)
            LOG.info("Removed share entry from ETCD: %s" % share_name)
        except KeyError:
            msg = 'Warning: Failed to delete share key: %s from ' \
                  'ETCD due to KeyError' % share_name
            LOG.error(msg)

    def _decrement_share_cnt(self):
        fpg = self._fp_etcd.get_fpg_metadata(self._backend,
                                             self._cpg_name,
                                             self._fpg_name)
        cnt = int(fpg['share_cnt']) - 1
        fpg['share_cnt'] = cnt
        fpg['reached_full_capacity'] = False
        self._fp_etcd.save_fpg_metadata(self._backend,
                                        self._cpg_name,
                                        self._fpg_name,
                                        fpg)
        return cnt

    def _delete_fpg(self):
        self._mediator.delete_fpg(self._fpg_name)
        self._fp_etcd.delete_fpg_metadata(
            self._backend, self._cpg_name, self._fpg_name
        )
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend
                )
            except Exception as ex:
                msg = "WARNING: Metadata for backend %s is not present" %\
                      self._backend
                LOG.warning(msg)
            else:
                # Release IP to server IP pool
                ips_in_use = backend_metadata['ips_in_use']
                # 'vfsIPs': [(IP1, Subnet1), (IP2, Subnet2)...],
                vfs_ip = self._share_info.get('vfsIPs')[0]
                ip_to_release = vfs_ip[0]
                ips_in_use.remove(ip_to_release)

                # Remove FPG from default FPG list
                default_fpgs = backend_metadata.get('default_fpgs')
                if default_fpgs:
                    fpg_list = default_fpgs.get(self._cpg_name)
                    if self._fpg_name in fpg_list:
                        LOG.info("Removing default FPG entry [cpg:%s,"
                                 "fpg:%s..."
                                 % (self._cpg_name, self._fpg_name))
                        fpg_list.remove(self._fpg_name)

                        # If last fpg got removed from the list, remove
                        # the CPG entry from default_fpgs
                        if not fpg_list:
                            del default_fpgs[self._cpg_name]

                # Update backend metadata
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)
