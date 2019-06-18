import copy
import json
import sh
from sh import chmod
import six
import os
from threading import Thread

from oslo_log import log as logging
from oslo_utils import netutils

from hpedockerplugin.cmd.cmd_claimavailableip import ClaimAvailableIPCmd
from hpedockerplugin.cmd.cmd_createfpg import CreateFpgCmd
from hpedockerplugin.cmd.cmd_createvfs import CreateVfsCmd

from hpedockerplugin.cmd.cmd_initshare import InitializeShareCmd
from hpedockerplugin.cmd.cmd_createshare import CreateShareCmd
from hpedockerplugin.cmd import cmd_generate_fpg_vfs_names
from hpedockerplugin.cmd import cmd_setquota
from hpedockerplugin.cmd import cmd_deleteshare

import hpedockerplugin.exception as exception
import hpedockerplugin.fileutil as fileutil
import hpedockerplugin.hpe.array_connection_params as acp
from hpedockerplugin.i18n import _
from hpedockerplugin.hpe import hpe_3par_mediator
from hpedockerplugin import synchronization
from hpedockerplugin.hpe import utils

LOG = logging.getLogger(__name__)


class FileManager(object):
    def __init__(self, host_config, hpepluginconfig, etcd_util,
                 fp_etcd_client, node_id, backend_name):
        self._host_config = host_config
        self._hpepluginconfig = hpepluginconfig

        self._etcd = etcd_util
        self._fp_etcd_client = fp_etcd_client
        self._node_id = node_id
        self._backend = backend_name

        self._initialize_configuration()

        self._pwd_decryptor = utils.PasswordDecryptor(backend_name,
                                                      self._etcd)
        self._pwd_decryptor.decrypt_password(self.src_bkend_config)

        # TODO: When multiple backends come into picture, consider
        # lazy initialization of individual driver
        try:
            LOG.info("Initializing 3PAR driver...")
            self._primary_driver = self._initialize_driver(
                host_config, self.src_bkend_config)

            self._hpeplugin_driver = self._primary_driver
            LOG.info("Initialized 3PAR driver!")
        except Exception as ex:
            msg = "Failed to initialize 3PAR driver for array: %s!" \
                  "Exception: %s"\
                  % (self.src_bkend_config.hpe3par_api_url,
                     six.text_type(ex))
            LOG.info(msg)
            raise exception.HPEPluginStartPluginException(
                reason=msg)

    def get_backend(self):
        return self._backend

    def get_mediator(self):
        return self._hpeplugin_driver

    def get_file_etcd(self):
        return self._fp_etcd_client

    def get_etcd(self):
        return self._etcd

    def get_config(self):
        return self.src_bkend_config

    def _initialize_configuration(self):
        self.src_bkend_config = self._get_src_bkend_config()
        def_fpg_size = self.src_bkend_config.hpe3par_default_fpg_size
        if def_fpg_size:
            if def_fpg_size < 1 or def_fpg_size > 64:
                msg = "Configured hpe3par_default_fpg_size MUST be in the " \
                      "range 1 and 64. Specified value is %s" % def_fpg_size
                LOG.error(msg)
                raise exception.InvalidInput(msg)

    def _get_src_bkend_config(self):
        LOG.info("Getting source backend configuration...")
        hpeconf = self._hpepluginconfig
        config = acp.ArrayConnectionParams()
        for key in hpeconf.keys():
            value = getattr(hpeconf, key)
            config.__setattr__(key, value)

        LOG.info("Got source backend configuration!")
        return config

    def _initialize_driver(self, host_config, src_config):

        mediator = self._create_mediator(host_config, src_config)
        try:
            mediator.do_setup(timeout=30)
            # self.check_for_setup_error()
            return mediator
        except Exception as ex:
            msg = (_('hpeplugin_driver do_setup failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

    @staticmethod
    def _create_mediator(host_config, config):
        return hpe_3par_mediator.HPE3ParMediator(host_config, config)

    def create_share(self, share_name, **args):
        share_args = copy.deepcopy(args)
        # ====== TODO: Uncomment later ===============
        thread = Thread(target=self._create_share,
                        args=(share_name, share_args))

        # Process share creation on child thread
        thread.start()
        # ====== TODO: Uncomment later ===============

        # ======= TODO: Remove this later ========
        # import pdb
        # pdb.set_trace()
        # self._create_share(share_name, share_args)
        # ======= TODO: Remove this later ========

        # Return success
        return json.dumps({"Err": ""})

    def _get_existing_fpg(self, share_args):
        cpg_name = share_args['cpg']
        fpg_name = share_args['fpg']
        try:
            fpg_info = self._fp_etcd_client.get_fpg_metadata(
                self._backend,
                cpg_name, fpg_name
            )
            available_capacity = self._get_fpg_available_capacity(fpg_name)
            share_size_in_gib = share_args['size'] / 1024
            if available_capacity < share_size_in_gib:
                raise exception.FpgCapacityInsufficient(fpg=fpg_name)

        except exception.EtcdMetadataNotFound:
            LOG.info("Specified FPG %s not found in ETCD. Checking "
                     "if this is a legacy FPG..." % fpg_name)
            # Assume it's a legacy FPG, try to get details
            leg_fpg = self._hpeplugin_driver.get_fpg(fpg_name)
            LOG.info("FPG %s is a legacy FPG" % fpg_name)

            # CPG passed can be different than actual CPG
            # used for creating legacy FPG. Override default
            # or supplied CPG
            if cpg_name != leg_fpg['cpg']:
                msg = ("ERROR: Invalid CPG %s specified as an option or "
                       "configured in hpe.conf that doesn't match the parent "
                       "CPG %s of the specified legacy FPG %s. Please "
                       "specify CPG as '-o cpg=%s'" %
                       (cpg_name, fpg_name, leg_fpg['cpg'], leg_fpg['cpg']))
                LOG.error(msg)
                raise exception.InvalidInput(msg)

            # Get backend VFS information
            vfs_info = self._hpeplugin_driver.get_vfs(fpg_name)
            vfs_name = vfs_info['name']
            ip_info = vfs_info['IPInfo'][0]
            netmask = ip_info['netmask']
            ip = ip_info['IPAddr']

            fpg_info = {
                'ips': {netmask: [ip]},
                'fpg': fpg_name,
                'vfs': vfs_name,
            }

        fpg_data = {'fpg': fpg_info}
        yield fpg_data

        if fpg_data['result'] != 'DONE':
            LOG.error("Share could not be created on FPG %s" % fpg_name)
            raise exception.ShareCreationFailed(share_args['cpg'])

    def _get_fpg_available_capacity(self, fpg_name):
        LOG.info("Getting FPG %s from backend..." % fpg_name)
        backend_fpg = self._hpeplugin_driver.get_fpg(fpg_name)
        LOG.info("%s" % six.text_type(backend_fpg))
        LOG.info("Getting all quotas for FPG %s..." % fpg_name)
        quotas = self._hpeplugin_driver.get_quotas_for_fpg(fpg_name)
        used_capacity_GiB = 0
        for quota in quotas['members']:
            used_capacity_GiB += (quota['hardBlockMiB'] / 1024)
        fpg_total_capacity_GiB = backend_fpg['availCapacityGiB']
        LOG.info("Total capacity of FPG %s: %s GiB" %
                 (fpg_name, fpg_total_capacity_GiB))
        LOG.info("Capacity used on FPG %s is %s GiB" %
                 (fpg_name, used_capacity_GiB))
        fpg_avail_capacity = fpg_total_capacity_GiB - used_capacity_GiB
        LOG.info("Available capacity on FPG %s is %s GiB" %
                 (fpg_name, fpg_avail_capacity))
        return fpg_avail_capacity

    # If default FPG is full, it raises exception
    # EtcdMaxSharesPerFpgLimitException
    def _get_default_available_fpg(self, share_args):
        LOG.info("Getting default available FPG...")
        processing_done = False
        for fpg_name in self._get_current_default_fpg_name(share_args):
            try:
                fpg_available_capacity = self._get_fpg_available_capacity(
                    fpg_name
                )
                LOG.info("FPG available capacity in GiB: %s" %
                         fpg_available_capacity)
                # Share size in MiB - convert it to GiB
                share_size_in_gib = share_args['size'] / 1024

                # Yield only those default FPGs that have enough available
                # capacity to create the requested share
                if fpg_available_capacity >= share_size_in_gib:
                    LOG.info("Found default FPG with enough available "
                             "capacity %s GiB to create share of size %s GiB"
                             % (fpg_available_capacity, share_size_in_gib))
                    # Get backend VFS information
                    vfs_info = self._hpeplugin_driver.get_vfs(fpg_name)
                    vfs_name = vfs_info['name']
                    ip_info = vfs_info['IPInfo'][0]
                    netmask = ip_info['netmask']
                    ip = ip_info['IPAddr']

                    fpg_info = {
                        'ips': {netmask: [ip]},
                        'fpg': fpg_name,
                        'vfs': vfs_name,
                    }
                    fpg_data = {'fpg': fpg_info}
                    yield fpg_data

                    if fpg_data['result'] == 'DONE':
                        LOG.info("Share creation done using FPG %s" %
                                 fpg_name)
                        processing_done = True
                        break
                    else:
                        LOG.info("Share could not be created on FPG %s. "
                                 "Finding another default FPG with enough "
                                 "capacity to create share of size %s"
                                 % (fpg_name, share_size_in_gib))
                        continue

            except exception.FpgNotFound:
                LOG.warning("FPG %s present in ETCD but not found on backend. "
                            "Looking for next FPG" % fpg_name)
                continue

        # Default FPGs were there but none of them could satisfy the
        # requirement of creating share. New FPG must be created
        # hence raising exception to execute FPG creation flow
        if not processing_done:
            raise exception.EtcdDefaultFpgNotPresent(share_args['cpg'])

    # TODO:Imran: Backend metadata needs modification
    # Instead of one FPG, we need FPG listz
    # Backend metadata
    # {'default_fpgs': {
    #       cpg1: [fpg1, fpg2],
    #       cpg2: [fpg3]
    # }
    def _get_current_default_fpg_name(self, share_args):
        cpg_name = share_args['cpg']
        try:
            LOG.info("Fetching metadata for backend %s..." % self._backend)
            backend_metadata = self._fp_etcd_client.get_backend_metadata(
                self._backend)
            LOG.info("Backend metadata: %s" % backend_metadata)
            default_fpgs = backend_metadata.get('default_fpgs')
            if default_fpgs:
                LOG.info("Checking if default FPG present for CPG %s..." %
                         cpg_name)
                fpg_list = default_fpgs.get(cpg_name, [])
                for default_fpg in fpg_list:
                    LOG.info("Default FPG %s found for CPG %s" %
                             (default_fpg, cpg_name))
                    yield default_fpg
            else:
                LOG.info("Default FPG not found under backend %s for CPG %s"
                         % (self._backend, cpg_name))
                raise exception.EtcdDefaultFpgNotPresent(cpg=cpg_name)
        except exception.EtcdMetadataNotFound:
            LOG.info("Metadata not found for backend %s" % self._backend)
            raise exception.EtcdDefaultFpgNotPresent(cpg=cpg_name)

    def _unexecute(self, undo_cmds):
        for undo_cmd in reversed(undo_cmds):
            undo_cmd.unexecute()

    def _generate_default_fpg_vfs_names(self, share_args):
        # Default share creation - generate default names
        cmd = cmd_generate_fpg_vfs_names.GenerateFpgVfsNamesCmd(
            self._backend, share_args['cpg'],
            self._fp_etcd_client
        )
        LOG.info("_generate_default_fpg_vfs_names: Generating default "
                 "FPG VFS names")
        fpg_name, vfs_name = cmd.execute()
        LOG.info("_generate_default_fpg_vfs_names: Generated: %s, %s"
                 % (fpg_name, vfs_name))
        return fpg_name, vfs_name

    @staticmethod
    def _vfs_name_from_fpg_name(share_args):
        # Generate VFS name using specified FPG with "-o fpg" option
        fpg_name = share_args['fpg']
        vfs_name = fpg_name + '_vfs'
        LOG.info("Returning FPG and VFS names: %s, %s" % (fpg_name, vfs_name))
        return fpg_name, vfs_name

    def _create_fpg(self, share_args, undo_cmds):
        LOG.info("Generating FPG and VFS names...")
        cpg = share_args['cpg']
        fpg_name, vfs_name = self._vfs_name_from_fpg_name(share_args)
        LOG.info("Names generated: FPG=%s, VFS=%s" %
                 (fpg_name, vfs_name))
        LOG.info("Creating FPG %s using CPG %s" % (fpg_name, cpg))
        create_fpg_cmd = CreateFpgCmd(self, cpg, fpg_name, False)
        create_fpg_cmd.execute()
        LOG.info("FPG %s created successfully using CPG %s" %
                 (fpg_name, cpg))
        undo_cmds.append(create_fpg_cmd)
        return fpg_name, vfs_name

    def _create_default_fpg(self, share_args, undo_cmds):
        LOG.info("Generating FPG and VFS names...")
        cpg = share_args['cpg']
        while True:
            fpg_name, vfs_name = self._generate_default_fpg_vfs_names(
                share_args
            )
            LOG.info("Names generated: FPG=%s, VFS=%s" %
                     (fpg_name, vfs_name))
            LOG.info("Creating FPG %s using CPG %s" % (fpg_name, cpg))
            try:
                create_fpg_cmd = CreateFpgCmd(self, cpg, fpg_name, True)
                create_fpg_cmd.execute()
                LOG.info("FPG %s created successfully using CPG %s" %
                         (fpg_name, cpg))
                undo_cmds.append(create_fpg_cmd)
                return fpg_name, vfs_name
            except (exception.FpgCreationFailed,
                    exception.FpgAlreadyExists) as ex:
                LOG.info("FPG %s could not be created. Error: %s" %
                         (fpg_name, six.text_type(ex)))
                LOG.info("Retrying with new FPG name...")
                continue
            except exception.HPEPluginEtcdException as ex:
                raise ex
            except Exception as ex:
                LOG.error("Unknown exception caught while creating default "
                          "FPG: %s" % six.text_type(ex))

    def _create_share_on_fpg(self, share_args, fpg_getter,
                             fpg_creator, undo_cmds):
        share_name = share_args['name']
        LOG.info("Creating share %s..." % share_name)
        cpg = share_args['cpg']

        def __create_share_and_quota():
            LOG.info("Creating share %s..." % share_name)
            create_share_cmd = CreateShareCmd(
                self,
                share_args
            )
            create_share_cmd.execute()
            LOG.info("Share created successfully %s" % share_name)
            undo_cmds.append(create_share_cmd)

            LOG.info("Setting quota for share %s..." % share_name)
            set_quota_cmd = cmd_setquota.SetQuotaCmd(
                self,
                share_args['cpg'],
                share_args['fpg'],
                share_args['vfs'],
                share_args['name'],
                share_args['size']
            )
            set_quota_cmd.execute()
            LOG.info("Quota set for share successfully %s" % share_name)
            undo_cmds.append(set_quota_cmd)

        with self._fp_etcd_client.get_cpg_lock(self._backend, cpg):
            try:
                init_share_cmd = InitializeShareCmd(
                    self._backend, share_args, self._etcd
                )
                init_share_cmd.execute()
                # Since we would want the share to be shown in failed status
                # even in case of failure, cannot make this as part of undo
                # undo_cmds.append(init_share_cmd)

                fpg_gen = fpg_getter(share_args)
                while True:
                    try:
                        fpg_data = next(fpg_gen)
                        fpg_info = fpg_data['fpg']
                        share_args['fpg'] = fpg_info['fpg']
                        share_args['vfs'] = fpg_info['vfs']

                        # Only one IP per FPG is supported at the moment
                        # Given that, list can be dropped
                        subnet_ips_map = fpg_info['ips']
                        subnet, ips = next(iter(subnet_ips_map.items()))
                        share_args['vfsIPs'] = [(ips[0], subnet)]

                        __create_share_and_quota()

                        # Set result to success so that FPG generator can stop
                        fpg_data['result'] = 'DONE'
                    except exception.SetQuotaFailed:
                        fpg_data['result'] = 'IN_PROCESS'
                        self._unexecute(undo_cmds)
                        undo_cmds.clear()

                    except StopIteration:
                        # Let the generator take the call whether it wants to
                        # report failure or wants to create new default FPG
                        # for this share
                        fpg_data['result'] = 'FAILED'
                        undo_cmds.clear()
                        break
            except (exception.EtcdMaxSharesPerFpgLimitException,
                    exception.EtcdMetadataNotFound,
                    exception.EtcdDefaultFpgNotPresent,
                    exception.FpgNotFound):
                LOG.info("FPG not found under backend %s for CPG %s"
                         % (self._backend, cpg))
                # In all the above cases, default FPG is not present
                # and we need to create a new one
                try:
                    # Generate FPG and VFS names. This will also initialize
                    #  backend meta-data in case it doesn't exist
                    fpg_name, vfs_name = fpg_creator(share_args, undo_cmds)
                    share_args['fpg'] = fpg_name
                    share_args['vfs'] = vfs_name

                    LOG.info("Trying to claim free IP from IP pool for "
                             "backend %s..." % self._backend)
                    # Acquire IP even before FPG creation. This will save the
                    # time by not creating FPG in case IP pool is exhausted
                    claim_free_ip_cmd = ClaimAvailableIPCmd(
                        self._backend,
                        self.src_bkend_config,
                        self._fp_etcd_client,
                        self._hpeplugin_driver
                    )
                    ip, netmask = claim_free_ip_cmd.execute()
                    LOG.info("Acquired IP %s for VFS creation" % ip)
                    undo_cmds.append(claim_free_ip_cmd)

                    LOG.info("Creating VFS %s under FPG %s" %
                             (vfs_name, fpg_name))
                    create_vfs_cmd = CreateVfsCmd(
                        self, cpg, fpg_name, vfs_name, ip, netmask
                    )
                    create_vfs_cmd.execute()
                    LOG.info("VFS %s created successfully under FPG %s" %
                             (vfs_name, fpg_name))
                    undo_cmds.append(create_vfs_cmd)

                    LOG.info("Marking IP %s to be in use by VFS /%s/%s"
                             % (ip, fpg_name, vfs_name))
                    # Now that VFS has been created successfully, move the IP
                    # from locked-ip-list to ips-in-use list
                    claim_free_ip_cmd.mark_ip_in_use()
                    share_args['vfsIPs'] = [(ip, netmask)]

                    __create_share_and_quota()

                except (exception.IPAddressPoolExhausted,
                        exception.VfsCreationFailed,
                        exception.FpgCreationFailed,
                        exception.HPEDriverNonExistentCpg) as ex:
                    msg = "Share creation on new FPG failed. Reason: %s" \
                          % six.text_type(ex)
                    raise exception.ShareCreationFailed(reason=msg)

                except Exception as ex:
                    msg = "Unknown exception caught. Reason: %s" \
                          % six.text_type(ex)
                    raise exception.ShareCreationFailed(reason=msg)

            except (exception.FpgCapacityInsufficient,
                    exception.InvalidInput) as ex:
                msg = "Share creation failed. Reason: %s" % six.text_type(ex)
                raise exception.ShareCreationFailed(reason=msg)

            except Exception as ex:
                msg = "Unknown exception occurred while creating share " \
                      "on new FPG. Reason: %s" % six.text_type(ex)
                raise exception.ShareCreationFailed(reason=msg)

    @synchronization.synchronized_fp_share('{share_name}')
    def _create_share(self, share_name, share_args):
        # Check if share already exists
        try:
            self._etcd.get_share(share_name)
            return
        except exception.EtcdMetadataNotFound:
            pass

        # Make copy of args as we are going to modify it
        fpg_name = share_args.get('fpg')
        undo_cmds = []

        try:
            if fpg_name:
                self._create_share_on_fpg(
                    share_args,
                    self._get_existing_fpg,
                    self._create_fpg,
                    undo_cmds
                )
            else:
                self._create_share_on_fpg(
                    share_args,
                    self._get_default_available_fpg,
                    self._create_default_fpg,
                    undo_cmds
                )
        except exception.PluginException as ex:
            LOG.error(ex.msg)
            share_args['status'] = 'FAILED'
            share_args['detailedStatus'] = ex.msg
            self._etcd.save_share(share_args)
            self._unexecute(undo_cmds)

    def remove_share(self, share_name, share):
        if 'path_info' in share:
            msg = "Cannot delete share %s as it is in mounted state" \
                  % share_name
            LOG.error(msg)
            return json.dumps({'Err': msg})
        cmd = cmd_deleteshare.DeleteShareCmd(self, share)
        return cmd.execute()

    @staticmethod
    def _rm_implementation_details(db_share):
        LOG.info("Removing implementation details from share %s..."
                 % db_share['name'])
        db_share_copy = copy.deepcopy(db_share)
        db_share_copy.pop("nfsOptions")
        if 'quota_id' in db_share_copy:
            db_share_copy.pop("quota_id")
        db_share_copy.pop("id")
        db_share_copy.pop("readonly")
        db_share_copy.pop("comment")
        if 'path_info' in db_share_copy:
            db_share_copy.pop('path_info')

        LOG.info("Implementation details removed: %s" % db_share_copy)
        return db_share_copy

    def get_share_details(self, share_name, db_share):
        mountdir = ''
        devicename = ''
        if db_share['status'] == 'AVAILABLE':
            vfs_ip = db_share['vfsIPs'][0][0]
            share_path = "%s:/%s/%s/%s" % (vfs_ip,
                                           db_share['fpg'],
                                           db_share['vfs'],
                                           db_share['name'])
        else:
            share_path = None

        path_info = db_share.get('path_info')
        if path_info:
            mountdir = '['
            node_mnt_info = path_info.get(self._node_id)
            if node_mnt_info:
                for mnt_dir in node_mnt_info.values():
                    mountdir += mnt_dir + ', '
                mountdir += ']'
                devicename = share_path

        db_share_copy = FileManager._rm_implementation_details(db_share)
        db_share_copy['sharePath'] = share_path
        size_in_gib = "%d GiB" % (db_share_copy['size'] / 1024)
        db_share_copy['size'] = size_in_gib
        LOG.info("Returning share: %s" % db_share_copy)
        # use volinfo as volname could be partial match
        resp = {'Name': share_name,
                'Mountpoint': mountdir,
                'Devicename': devicename,
                'Status': db_share_copy}
        response = json.dumps({u"Err": '', u"Volume": resp})
        LOG.debug("Get share: \n%s" % str(response))
        return response

    def list_shares(self):
        db_shares = self._etcd.get_all_shares()

        if not db_shares:
            response = json.dumps({u"Err": ''})
            return response

        share_list = []
        for db_share in db_shares:
            path_info = db_share.get('share_path_info')
            if path_info is not None and 'mount_dir' in path_info:
                mountdir = path_info['mount_dir']
                devicename = path_info['path']
            else:
                mountdir = ''
                devicename = ''
            share = {'Name': db_share['name'],
                     'Devicename': devicename,
                     'size': db_share['size'],
                     'Mountpoint': mountdir,
                     'Status': db_share}
            share_list.append(share)

        response = json.dumps({u"Err": '', u"Volumes": share_list})
        return response

    @staticmethod
    def _is_share_not_mounted(share):
        return 'node_mount_info' not in share

    def _is_share_mounted_on_this_node(self, node_mount_info):
        return self._node_id in node_mount_info

    def _update_mount_id_list(self, share, mount_id):
        node_mount_info = share['node_mount_info']

        # Check if mount_id is unique
        if mount_id in node_mount_info[self._node_id]:
            LOG.info("Received duplicate mount-id: %s. Ignoring"
                     % mount_id)
            return

        LOG.info("Adding new mount-id %s to node_mount_info..."
                 % mount_id)
        node_mount_info[self._node_id].append(mount_id)
        LOG.info("Updating etcd with modified node_mount_info: %s..."
                 % node_mount_info)
        self._etcd.save_share(share)
        LOG.info("Updated etcd with modified node_mount_info: %s!"
                 % node_mount_info)

    def _get_mount_dir(self, share_name):
        if self._host_config.mount_prefix:
            mount_prefix = self._host_config.mount_prefix
        else:
            mount_prefix = None
        mnt_prefix = fileutil.mkfile_dir_for_mounting(mount_prefix)
        return "%s%s" % (mnt_prefix, share_name)

    def _create_mount_dir(self, mount_dir):
        LOG.info('Creating Directory %(mount_dir)s...',
                 {'mount_dir': mount_dir})
        sh.mkdir('-p', mount_dir)
        LOG.info('Directory: %(mount_dir)s successfully created!',
                 {'mount_dir': mount_dir})

    def mount_share(self, share_name, share, mount_id):
        if 'status' in share:
            if share['status'] == 'FAILED':
                msg = "Share %s is in FAILED state. Please remove it and " \
                      "create a new one and then retry mount" % share_name
                LOG.error(msg)
                return json.dumps({u"Err": msg})
            elif share['status'] == 'CREATING':
                msg = "Share %s is in CREATING state. Please wait for it " \
                      "to be in AVAILABLE state and then retry mount" \
                      % share_name
                LOG.error(msg)
                return json.dumps({u"Err": msg})
            elif share['status'] == 'AVAILABLE':
                msg = "Share %s is in AVAILABLE state. Attempting mount..." \
                      % share_name
                LOG.info(msg)
            else:
                msg = "ERROR: Share %s is in UNKNOWN state. Aborting " \
                      "mount..." % share_name
                LOG.error(msg)
                return json.dumps({u"Err": msg})

        fUser = None
        fGroup = None
        fMode = None
        fUName = None
        fGName = None
        is_first_call = False
        if share['fsOwner']:
            fOwner = share['fsOwner'].split(':')
            fUser = int(fOwner[0])
            fGroup = int(fOwner[1])
        if share['fsMode']:
            try:
                fMode = int(share['fsMode'])
            except ValueError:
                fMode = share['fsMode']
        fpg = share['fpg']
        vfs = share['vfs']
        file_store = share['name']
        vfs_ip, netmask = share['vfsIPs'][0]
        # If shareDir is not specified, share is mounted at file-store
        # level.
        share_path = "%s:/%s/%s/%s" % (vfs_ip,
                                       fpg,
                                       vfs,
                                       file_store)
        # {
        #   'path_info': {
        #     node_id1: {'mnt_id1': 'mnt_dir1', 'mnt_id2': 'mnt_dir2',...},
        #     node_id2: {'mnt_id2': 'mnt_dir2', 'mnt_id3': 'mnt_dir3',...},
        #   }
        # }
        mount_dir = self._get_mount_dir(mount_id)
        LOG.info("Mount directory for file is %s " % (mount_dir))
        path_info = share.get('path_info')
        if path_info:
            node_mnt_info = path_info.get(self._node_id)
            if node_mnt_info:
                node_mnt_info[mount_id] = mount_dir
            else:
                my_ip = netutils.get_my_ipv4()
                self._hpeplugin_driver.add_client_ip_for_share(share['id'],
                                                               my_ip)
                client_ips = share['clientIPs']
                client_ips.append(my_ip)
                # node_mnt_info not present
                node_mnt_info = {
                    self._node_id: {
                        mount_id: mount_dir
                    }
                }
                path_info.update(node_mnt_info)
        else:
            my_ip = netutils.get_my_ipv4()
            self._hpeplugin_driver.add_client_ip_for_share(share['id'],
                                                           my_ip)
            client_ips = share['clientIPs']
            client_ips.append(my_ip)

            # node_mnt_info not present
            node_mnt_info = {
                self._node_id: {
                    mount_id: mount_dir
                }
            }
            share['path_info'] = node_mnt_info
            if fUser or fGroup or fMode:
                LOG.info("Inside fUser or fGroup or fMode")
                is_first_call = True
                try:
                    fUName, fGName = self._hpeplugin_driver.usr_check(fUser,
                                                                      fGroup)
                    if fUName is None or fGName is None:
                        msg = ("Either user or group does not exist on 3PAR."
                               " Please create local users and group with"
                               " required user id and group id on 3PAR."
                               " Refer 3PAR cli user guide to create 3PAR"
                               " local users on 3PAR")
                        LOG.error(msg)
                        raise exception.UserGroupNotFoundOn3PAR(msg)
                except exception.UserGroupNotFoundOn3PAR as ex:
                    msg = six.text_type(ex)
                    LOG.error(msg)
                    response = json.dumps({u"Err": msg, u"Name": share_name,
                                           u"Mountpoint": mount_dir,
                                           u"Devicename": share_path})
                    return response

        self._create_mount_dir(mount_dir)
        LOG.info("Mounting share path %s to %s" % (share_path, mount_dir))
        sh.mount('-t', 'nfs', share_path, mount_dir)
        LOG.debug('Device: %(path)s successfully mounted on %(mount)s',
                  {'path': share_path, 'mount': mount_dir})
        if is_first_call:
            os.chown(mount_dir, fUser, fGroup)
            try:
                int(fMode)
                chmod(fMode, mount_dir)
            except ValueError:
                fUserId = share['id']
                try:
                    self._hpeplugin_driver.set_ACL(fMode, fUserId, fUName,
                                                   fGName)
                except exception.ShareBackendException as ex:
                    msg = (_("Exception raised for ACL setting,"
                             " but proceed. User is adviced to correct"
                             " the passed fsMode to suit its owner and"
                             " group requirement. Delete the share and "
                             " create new with correct fsMode value."
                             " Please also refer the logs for same. "
                             "Exception is  %s") % six.text_type(ex))
                    LOG.error(msg)
                    LOG.info("Unmounting the share,permissions are not set.")
                    sh.umount(mount_dir)
                    LOG.info("Removing the created directory.")
                    sh.rm('-rf', mount_dir)
                    LOG.error(msg)
                    response = json.dumps({u"Err": msg, u"Name": share_name,
                                           u"Mountpoint": mount_dir,
                                           u"Devicename": share_path})
                    return response
        self._etcd.save_share(share)
        response = json.dumps({u"Err": '', u"Name": share_name,
                               u"Mountpoint": mount_dir,
                               u"Devicename": share_path})
        return response

    def unmount_share(self, share_name, share, mount_id):
        # Start of volume fencing
        LOG.info('Unmounting share: %s' % share)
        # share = {
        #   'path_info': {
        #     node_id1: {'mnt_id1': 'mnt_dir1', 'mnt_id2': 'mnt_dir2',...},
        #     node_id2: {'mnt_id2': 'mnt_dir2', 'mnt_id3': 'mnt_dir3',...},
        #   }
        # }
        path_info = share.get('path_info')
        if path_info:
            node_mnt_info = path_info.get(self._node_id)
            if node_mnt_info:
                mount_dir = node_mnt_info.get(mount_id)
                if mount_dir:
                    LOG.info('Unmounting share: %s...' % mount_dir)
                    sh.umount(mount_dir)
                    LOG.info('Removing dir: %s...' % mount_dir)
                    sh.rm('-rf', mount_dir)
                    LOG.info("Removing mount-id '%s' from meta-data" %
                             mount_id)
                    del node_mnt_info[mount_id]

                # If this was the last mount of share share_name on
                # this node, remove my_ip from client-ip list
                if not node_mnt_info:
                    del path_info[self._node_id]
                    my_ip = netutils.get_my_ipv4()
                    LOG.info("Remove %s from client IP list" % my_ip)
                    client_ips = share['clientIPs']
                    client_ips.remove(my_ip)
                    self._hpeplugin_driver.remove_client_ip_for_share(
                        share['id'], my_ip)
                    # If this is the last node from where share is being
                    # unmounted, remove the path_info from share metadata
                    if not path_info:
                        del share['path_info']
                LOG.info('Share unmounted. Updating ETCD: %s' % share)
                self._etcd.save_share(share)
                LOG.info('Unmount DONE for share: %s, %s' %
                         (share_name, mount_id))
            else:
                LOG.error("ERROR: Node mount information not found in ETCD")
        else:
            LOG.error("ERROR: Path info missing from ETCD")
        response = json.dumps({u"Err": ''})
        return response
