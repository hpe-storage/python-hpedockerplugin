import base64
import copy
import json
import socket
import string
import os
import sh
import six
import uuid
from Crypto.Cipher import AES
from threading import Thread

from oslo_log import log as logging
from oslo_utils import netutils

from hpedockerplugin.cmd import cmd_createshare
from hpedockerplugin.cmd import cmd_generate_fpg_vfs_names
from hpedockerplugin.cmd import cmd_setquota
from hpedockerplugin.cmd import cmd_deleteshare

import hpedockerplugin.exception as exception
import hpedockerplugin.fileutil as fileutil
import hpedockerplugin.hpe.array_connection_params as acp
from hpedockerplugin.i18n import _, _LE, _LI, _LW
from hpedockerplugin.hpe import hpe_3par_mediator
from hpedockerplugin import synchronization

LOG = logging.getLogger(__name__)


class FileManager(object):
    def __init__(self, host_config, hpepluginconfig, etcd_util,
                 fp_etcd_client, node_id, backend_name='DEFAULT'):
        self._host_config = host_config
        self._hpepluginconfig = hpepluginconfig
        self._my_ip = netutils.get_my_ipv4()

        self._etcd = etcd_util
        self._fp_etcd_client = fp_etcd_client
        self._node_id = node_id
        self._backend = backend_name

        self._initialize_configuration()

        self._decrypt_password(self.src_bkend_config,
                               self.tgt_bkend_config,
                               backend_name)

        # TODO: When multiple backends come into picture, consider
        # lazy initialization of individual driver
        try:
            LOG.info("Initializing 3PAR driver...")
            self._primary_driver = self._initialize_driver(
                host_config, self.src_bkend_config, self.tgt_bkend_config)

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

        # If replication enabled, then initialize secondary driver
        if self.tgt_bkend_config:
            LOG.info("Replication enabled!")
            try:
                LOG.info("Initializing 3PAR driver for remote array...")
                self._remote_driver = self._initialize_driver(
                    host_config, self.tgt_bkend_config,
                    self.src_bkend_config)
            except Exception as ex:
                msg = "Failed to initialize 3PAR driver for remote array %s!" \
                      "Exception: %s"\
                      % (self.tgt_bkend_config.hpe3par_api_url,
                         six.text_type(ex))
                LOG.info(msg)
                raise exception.HPEPluginStartPluginException(reason=msg)

        # self._initialize_default_metadata()

    def get_backend(self):
        return self._backend

    def get_mediator(self):
        return self._hpeplugin_driver

    def get_file_etcd(self):
        return self._fp_etcd_client

    def get_etcd(self):
        return self._etcd

    def get_config(self):
        return self._hpepluginconfig

    # Create metadata for the backend if it doesn't exist
    def _initialize_default_metadata(self):
        try:
            metadata = self._fp_etcd_client.get_backend_metadata(self._backend)
        except exception.EtcdBackendMetadataDoesNotExist:
            metadata = {
                'cpg_fpg_map': {
                    'used_ips': [],
                    'counter': 0,
                    'default_fpgs': {self.src_bkend_config.hpe3par_cpg: None}
                }
            }
            self._fp_etcd_client.save_backend_metadata(metadata)

    def _initialize_configuration(self):
        self.src_bkend_config = self._get_src_bkend_config()
        self.tgt_bkend_config = None

    def _get_src_bkend_config(self):
        LOG.info("Getting source backend configuration...")
        hpeconf = self._hpepluginconfig
        config = acp.ArrayConnectionParams()
        for key in hpeconf.keys():
            value = getattr(hpeconf, key)
            config.__setattr__(key, value)

        LOG.info("Got source backend configuration!")
        return config

    def _initialize_driver(self, host_config, src_config, tgt_config):

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

    def _create_share_on_fpg(self, fpg_name, share_args):
        try:
            cmd = cmd_createshare.CreateShareOnExistingFpgCmd(
                self, share_args
            )
            return cmd.execute()
        except exception.FpgNotFound:
            # User wants to create FPG by name fpg_name
            vfs_name = fpg_name + '_vfs'
            share_args['vfs'] = vfs_name
            cmd = cmd_createshare.CreateShareOnNewFpgCmd(
                self, share_args
            )
            return cmd.execute()

    def _create_share_on_default_fpg(self, cpg_name, share_args):
        try:
            cmd = cmd_createshare.CreateShareOnDefaultFpgCmd(
                self, share_args
            )
            return cmd.execute()
        except (exception.EtcdMaxSharesPerFpgLimitException,
                exception.EtcdDefaultFpgNotPresent) as ex:
            cmd = cmd_generate_fpg_vfs_names.GenerateFpgVfsNamesCmd(
                self._backend, cpg_name, self._fp_etcd_client
            )
            fpg_name, vfs_name = cmd.execute()

            share_args['fpg'] = fpg_name
            share_args['vfs'] = vfs_name
            cmd = cmd_createshare.CreateShareOnNewFpgCmd(
                self, share_args, make_default_fpg=True
            )
            return cmd.execute()

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
        cpg_name = share_args.get('cpg')

        try:
            if fpg_name:
                self._create_share_on_fpg(fpg_name, share_args)
            else:
                self._create_share_on_default_fpg(cpg_name, share_args)

            cmd = cmd_setquota.SetQuotaCmd(self, share_args['cpg'],
                                           share_args['fpg'],
                                           share_args['vfs'],
                                           share_args['name'],
                                           share_args['size'])
            try:
                cmd.execute()
            except Exception:
                self._etcd.delete_share({
                    'name': share_name
                })
                raise
        except Exception as ex:
            self._etcd.delete_share({
                'name': share_name
            })
            raise

    def remove_share(self, share_name, share):
        cmd = cmd_deleteshare.DeleteShareCmd(self, share)
        return cmd.execute()

    def remove_snapshot(self, share_name, snapname):
        pass

    def get_share_details(self, share_name, db_share):
        # db_share = self._etcd.get_vol_byname(share_name,
        #                                      name_key1='shareName',
        #                                      name_key2='shareName')
        # LOG.info("Share details: %s", db_share)
        # if db_share is None:
        #     msg = (_LE('Share Get: Share name not found %s'), share_name)
        #     LOG.warning(msg)
        #     response = json.dumps({u"Err": ""})
        #     return response

        err = ''
        mountdir = ''
        devicename = ''

        path_info = db_share.get('share_path_info')
        if path_info is not None:
            mountdir = path_info['mount_dir']
            devicename = path_info['path']

        # use volinfo as volname could be partial match
        share = {'Name': share_name,
                 'Mountpoint': mountdir,
                 'Devicename': devicename,
                 'Status': db_share}
        response = json.dumps({u"Err": err, u"Volume": share})
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

    def _get_host_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]

    def mount_share(self, share_name, share, mount_id):
        if 'status' in share:
            if share['status'] == 'FAILED':
                LOG.error("Share not present")

        client_ip = self._get_host_ip()
        self._hpeplugin_driver.add_client_ip_for_share(share['id'],
                                                       client_ip)
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

        # {'path_info': {'/opt/hpe/data/hpedocker-<share_name>':['mnt_id1, 'mnt_id2'...]}}
        if 'share_path_info' in share:
            path_info = share['share_path_info']
            mount_dir, mount_ids = next(iter(path_info.items()))
            mount_ids.append(mount_id)
            self._etcd.save_share(share)
        else:
            LOG.info("Inside mount share... getting share by name: %s" %
                     share_name)

            mount_dir = "%s%s" % (fileutil.prefix, share_name)

            # TODO: Check instead if mount entry is there and based on that
            # decide
            # if os.path.exists(mount_dir):
            #     msg = "Mount path %s already in use" % mount_dir
            #     raise exception.HPEPluginMountException(reason=msg)

            LOG.info('Creating Directory %(mount_dir)s...',
                     {'mount_dir': mount_dir})
            sh.mkdir('-p', mount_dir)
            LOG.info('Directory: %(mount_dir)s successfully created!',
                     {'mount_dir': mount_dir})

            LOG.info("Mounting share path %s to %s" % (share_path, mount_dir))
            sh.mount('-t', 'nfs', share_path, mount_dir)
            LOG.debug('Device: %(path)s successfully mounted on %(mount)s',
                      {'path': share_path, 'mount': mount_dir})

            # if 'fsOwner' in share and share['fsOwner']:
            #     fs_owner = share['fsOwner'].split(":")
            #     uid = int(fs_owner[0])
            #     gid = int(fs_owner[1])
            #     os.chown(mount_dir, uid, gid)
            #
            # if 'fsMode' in share and share['fsMode']:
            #     mode = str(share['fsMode'])
            #     chmod(mode, mount_dir)

            share['path_info'] = {mount_dir: [mount_id]}
            self._etcd.save_share(share)
        response = json.dumps({u"Err": '', u"Name": share_name,
                               u"Mountpoint": mount_dir,
                               u"Devicename": share_path})
        return response

    def unmount_share(self, share_name, share, mount_id):
        # Start of volume fencing
        LOG.info('Unmounting share: %s' % share)
        path_info = share.get('share_path_info')
        if path_info:
            mount_path, mount_ids = next(iter(path_info.items()))
            if mount_id in mount_ids:
                LOG.info("Removing mount-id '%s' from meta-data" % mount_id)
                mount_ids.remove(mount_id)

            if not mount_ids:
                LOG.info('Unmounting share: %s...' % mount_path)
                sh.umount(mount_path)
                LOG.info('Removing dir: %s...' % mount_path)
                sh.rm('-rf', mount_path)
                del share['share_path_info']
                LOG.info('Share unmounted. Updating ETCD: %s' % share)
                self._etcd.save_share(share)

                self._hpeplugin_driver.removed_client_ip_for_share(
                    share['id'], self._get_host_ip())
            else:
                LOG.info('Updated ETCD mount-id list: %s' % mount_ids)
                self._etcd.save_share(share)

        response = json.dumps({u"Err": ''})
        LOG.info('Unmount DONE for share: %s, %s' % (share_name, mount_id))
        return response

    def import_share(self, volname, existing_ref, backend='DEFAULT',
                     manage_opts=None):
        pass

    @staticmethod
    def _rollback(rollback_list):
        for undo_action in reversed(rollback_list):
            LOG.info(undo_action['msg'])
            try:
                undo_action['undo_func'](**undo_action['params'])
            except Exception as ex:
                # TODO: Implement retry logic
                LOG.exception('Ignoring exception: %s' % ex)
                pass

    def _decrypt(self, encrypted, passphrase):
        aes = AES.new(passphrase, AES.MODE_CFB, '1234567812345678')
        decrypt_pass = aes.decrypt(base64.b64decode(encrypted))
        return decrypt_pass.decode('utf-8')

    def _decrypt_password(self, src_bknd, trgt_bknd, backend_name):
        try:
            passphrase = self._etcd.get_pass_phrase(backend_name)
        except Exception as ex:
            LOG.info('Exception occurred %s ' % ex)
            LOG.info("Using PLAIN TEXT for backend '%s'" % backend_name)
        else:
            passphrase = self.key_check(passphrase)
            src_bknd.hpe3par_password = \
                self._decrypt(src_bknd.hpe3par_password, passphrase)
            src_bknd.san_password =  \
                self._decrypt(src_bknd.san_password, passphrase)
            if trgt_bknd:
                trgt_bknd.hpe3par_password = \
                    self._decrypt(trgt_bknd.hpe3par_password, passphrase)
                trgt_bknd.san_password = \
                    self._decrypt(trgt_bknd.san_password, passphrase)

    def key_check(self, key):
        KEY_LEN = len(key)
        padding_string = string.ascii_letters

        if KEY_LEN < 16:
            KEY = key + padding_string[:16 - KEY_LEN]

        elif KEY_LEN > 16 and KEY_LEN < 24:
            KEY = key + padding_string[:24 - KEY_LEN]

        elif KEY_LEN > 24 and KEY_LEN < 32:
            KEY = key + padding_string[:32 - KEY_LEN]

        elif KEY_LEN > 32:
            KEY = key[:32]

        return KEY
