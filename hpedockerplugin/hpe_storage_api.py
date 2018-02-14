# (c) Copyright [2016] Hewlett Packard Enterprise Development LP
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
An HTTP API implementing the Docker Volumes Plugin API.

See https://github.com/docker/docker/tree/master/docs/extend for details.
"""
import json
import six
import re

from os_brick.initiator import connector
from oslo_log import log as logging
from oslo_utils import netutils
from twisted.python.filepath import FilePath

import exception
import fileutil
from i18n import _, _LE, _LI
from klein import Klein
from hpe import volume
from oslo_utils import importutils
import etcdutil as util
import volume_manager as mgr

LOG = logging.getLogger(__name__)


class VolumePlugin(object):
    """
    An implementation of the Docker Volumes Plugin API.

    """
    app = Klein()

    def __init__(self, reactor, hpepluginconfig):
        """
        :param IReactorTime reactor: Reactor time interface implementation.
        :param Ihpepluginconfig : hpedefaultconfig configuration
        """
        LOG.info(_LI('Initialize Volume Plugin'))

        self._reactor = reactor
        self._hpepluginconfig = hpepluginconfig
        hpeplugin_driver = hpepluginconfig.hpedockerplugin_driver

        protocol = 'ISCSI'

        if 'HPE3PARFCDriver' in hpeplugin_driver:
            protocol = 'FIBRE_CHANNEL'

        self.hpeplugin_driver = \
            importutils.import_object(hpeplugin_driver, self._hpepluginconfig)

        if self.hpeplugin_driver is None:
            msg = (_('hpeplugin_driver import driver failed'))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

        try:
            self.hpeplugin_driver.do_setup()
            self.hpeplugin_driver.check_for_setup_error()
        except Exception as ex:
            msg = (_('hpeplugin_driver do_setup failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

        self._voltracker = {}
        self._path_info = []
        self._my_ip = netutils.get_my_ipv4()

        self._etcd = self._get_etcd_util()

        # TODO: make device_scan_attempts configurable
        # see nova/virt/libvirt/volume/iscsi.py

        # Override the settings of use_multipath, enforce_multipath
        # This will be a workaround until Issue #50 is fixed.
        msg = (_('Overriding the value of multipath flags to True'))
        LOG.info(msg)
        self.use_multipath = True
        self.enforce_multipath = True

        self.connector = self._get_connector(protocol)
        self._manager = mgr.VolumeManager(self.hpeplugin_driver,
                                          self._etcd)

    def _get_connector(self, protocol):
        root_helper = 'sudo'
        return connector.InitiatorConnector.factory(
            protocol, root_helper, use_multipath=self.use_multipath,
            device_scan_attempts=5, transport='default')

    def _get_etcd_util(self):
        return util.EtcdUtil(
            self._hpepluginconfig.host_etcd_ip_address,
            self._hpepluginconfig.host_etcd_port_number,
            self._hpepluginconfig.host_etcd_client_cert,
            self._hpepluginconfig.host_etcd_client_key)

    def disconnect_volume_callback(self, connector_info):
        LOG.info(_LI('In disconnect_volume_callback: connector info is %s'),
                 json.dumps(connector_info))

    def disconnect_volume_error_callback(self, connector_info):
        LOG.info(_LI('In disconnect_volume_error_callback: '
                     'connector info is %s'), json.dumps(connector_info))

    @app.route("/Plugin.Activate", methods=["POST"])
    def plugin_activate(self, ignore_body=True):
        """
        Return which Docker plugin APIs this object supports.
        """
        LOG.info(_LI('In Plugin Activate'))
        return json.dumps({u"Implements": [u"VolumeDriver"]})

    @app.route("/VolumeDriver.Remove", methods=["POST"])
    def volumedriver_remove(self, name):
        """
        Remove a Docker volume.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        obj_to_remove = contents['Name']
        tokens = obj_to_remove.split('/')
        token_cnt = len(tokens)
        LOG.debug("volumedriver_remove - obj_to_remove: %s" %
                  obj_to_remove)
        if token_cnt > 2:
            msg = (_LE("invalid volume or snapshot name %s"
                       % obj_to_remove))
            LOG.error(msg)
            response = json.dumps({u"Err": msg})
            return response

        if token_cnt == 2:
            volname = tokens[0]
            snapname = tokens[1]
            # We don't want to insert remove-snapshot code within
            # remove-volume code for two reasons:
            # 1. We want to avoid regression in existing remove-volume
            # 2. In the future, if docker engine provides snapshot
            #    support, this code should have minimum impact
            return self._manager.remove_snapshot(volname, snapname)
        else:
            volname = tokens[0]

        return self._manager.remove_volume(volname)

    @app.route("/VolumeDriver.Unmount", methods=["POST"])
    def volumedriver_unmount(self, name):
        """
        The Docker container is no longer using the given volume,
        so unmount it.
        NOTE: Since Docker will automatically call Unmount if the Mount
        fails, make sure we properly handle partially completed Mounts.

        :param unicode name: The name of the volume.
        :return: Result indicating success.
        """
        LOG.info(_LI('In volumedriver_unmount'))
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            volid = vol['id']
        else:
            msg = (_LE('Volume unmount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginUMountException(reason=msg)

        vol_mount = volume.DEFAULT_MOUNT_VOLUME
        if ('Opts' in contents and contents['Opts'] and
                'mount-volume' in contents['Opts']):
            vol_mount = str(contents['Opts']['mount-volume'])

        path_info = self._etcd.get_vol_path_info(volname)
        if path_info:
            path_name = path_info['path']
            connection_info = path_info['connection_info']
            mount_dir = path_info['mount_dir']
        else:
            msg = (_LE('Volume unmount path info not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginUMountException(reason=msg)

        # Get connector info from OS Brick
        # TODO: retrieve use_multipath and enforce_multipath from config file
        root_helper = 'sudo'

        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, multipath=self.use_multipath,
            enforce_multipath=self.enforce_multipath)

        # Determine if we need to unmount a previously mounted volume
        if vol_mount is volume.DEFAULT_MOUNT_VOLUME:
            # unmount directory
            fileutil.umount_dir(mount_dir)
            # remove directory
            fileutil.remove_dir(mount_dir)

        # Changed asynchronous disconnect_volume to sync call
        # since it causes a race condition between unmount and
        # mount operation on the same volume. This scenario is
        # more noticed in case of repeated mount & unmount
        # operations on the same volume. Refer Issue #64
        if connection_info:
            LOG.info(_LI('sync call os brick to disconnect volume'))
            self.connector.disconnect_volume(connection_info['data'], None)
            LOG.info(_LI('end of sync call to disconnect volume'))

        try:
            # Call driver to terminate the connection
            self.hpeplugin_driver.terminate_connection(vol, connector_info)
            LOG.info(_LI('connection_info: %(connection_info)s, '
                         'was successfully terminated'),
                     {'connection_info': json.dumps(connection_info)})
        except Exception as ex:
            msg = (_LE('connection info termination failed %s'),
                   six.text_type(ex))
            LOG.error(msg)
            # Not much we can do here, so just continue on with unmount
            # We need to ensure we update etcd path_info so the stale
            # path does not stay around
            # raise exception.HPEPluginUMountException(reason=msg)

        # TODO: Create path_info list as we can mount the volume to multiple
        # hosts at the same time.
        self._etcd.update_vol(volid, 'path_info', None)

        LOG.info(_LI('path for volume: %(name)s, was successfully removed: '
                     '%(path_name)s'), {'name': volname,
                                        'path_name': path_name})

        response = json.dumps({u"Err": ''})
        return response

    @app.route("/VolumeDriver.Create", methods=["POST"])
    def volumedriver_create(self, name, opts=None):
        """
        Create a volume with the given name.

        :param unicode name: The name of the volume.
        :param dict opts: Options passed from Docker for the volume
            at creation. ``None`` if not supplied in the request body.
            Currently ignored. ``Opts`` is a parameter introduced in the
            v2 plugins API introduced in Docker 1.9, it is not supplied
            in earlier Docker versions.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        if 'Name' not in contents:
            msg = (_('create volume failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)
        volname = contents['Name']

        is_valid_name = re.match("^[A-Za-z0-9]+[A-Za-z0-9_-]+$", volname)
        if not is_valid_name:
            msg = 'Invalid volume name: %s is passed.' % volname
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        vol_size = volume.DEFAULT_SIZE
        vol_prov = volume.DEFAULT_PROV
        vol_flash = volume.DEFAULT_FLASH_CACHE
        vol_qos = volume.DEFAULT_QOS
        compression_val = volume.DEFAULT_COMPRESSION_VAL
        valid_compression_opts = ['true', 'false']

        # Verify valid Opts arguments.
        valid_volume_create_opts = ['mount-volume', 'compression',
                                    'size', 'provisioning', 'flash-cache',
                                    'cloneOf', 'snapshotOf', 'expirationHours',
                                    'retentionHours', 'promote', 'qos-name']

        if ('Opts' in contents and contents['Opts']):
            for key in contents['Opts']:
                if key not in valid_volume_create_opts:
                    msg = (_('create volume failed, error is: '
                             '%(key)s is not a valid option. Valid options '
                             'are: %(valid)s') %
                           {'key': key,
                            'valid': valid_volume_create_opts, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

            # Populating the values
            if ('size' in contents['Opts']):
                vol_size = int(contents['Opts']['size'])

            if ('provisioning' in contents['Opts']):
                vol_prov = str(contents['Opts']['provisioning'])

            if ('compression' in contents['Opts']):
                compression_val = str(contents['Opts']['compression'])

            if ('flash-cache' in contents['Opts']):
                vol_flash = str(contents['Opts']['flash-cache'])

            if ('qos-name' in contents['Opts']):
                vol_qos = str(contents['Opts']['qos-name'])

            # check for valid promoteSnap option and return the result
            if ('promote' in contents['Opts'] and len(contents['Opts']) == 1):
                return self.revert_to_snapshot(name, opts)
            elif ('promote' in contents['Opts']):
                msg = (_('while reverting volume to snapshot status only '
                         'valid option is promote=<vol_name>'))
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

            # mutually exclusive options check
            mutually_exclusive_list = ['snapshotOf', 'cloneOf', 'qos-name',
                                       'promote']
            input_list = contents['Opts'].keys()
            if (len(list(set(input_list) &
                         set(mutually_exclusive_list))) >= 2):
                msg = (_('%(exclusive)s cannot be specified at the same '
                         'time') % {'exclusive': mutually_exclusive_list, })
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

            if ('snapshotOf' in contents['Opts']):
                return self.volumedriver_create_snapshot(name, opts)
            elif ('cloneOf' in contents['Opts']):
                return self.volumedriver_clone_volume(name, opts)

        if compression_val is not None:
            if compression_val.lower() not in valid_compression_opts:
                msg = (_('create volume failed, error is:'
                         'passed compression parameterdo not have a valid '
                         'value. Valid vaues are: %(valid)s') %
                       {'valid': valid_compression_opts, })
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

        return self._manager.create_volume(volname, vol_size,
                                           vol_prov, vol_flash,
                                           compression_val, vol_qos)

    def volumedriver_clone_volume(self, name, opts=None):
        # Repeating the validation here in anticipation that when
        # actual REST call for clone is added, this
        # function will have minimal impact
        contents = json.loads(name.content.getvalue())
        if 'Name' not in contents:
            msg = (_('clone volume failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

        size = None
        if ('Opts' in contents and contents['Opts'] and
                'size' in contents['Opts']):
            size = int(contents['Opts']['size'])

        src_vol_name = str(contents['Opts']['cloneOf'])
        clone_name = contents['Name']
        return self._manager.clone_volume(src_vol_name, clone_name, size)

    def volumedriver_create_snapshot(self, name, opts=None):
        # Repeating the validation here in anticipation that when
        # actual REST call for snapshot creation is added, this
        # function will have minimal impact
        contents = json.loads(name.content.getvalue())

        LOG.info("creating snapshot:\n%s" % json.dumps(contents, indent=2))

        if 'Name' not in contents:
            msg = (_('create snapshot failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

        src_vol_name = str(contents['Opts']['snapshotOf'])
        snapshot_name = contents['Name']

        # Verify valid Opts arguments.
        valid_volume_create_opts = ['snapshotOf', 'expirationHours',
                                    'retentionHours']
        if 'Opts' in contents and contents['Opts']:
            for key in contents['Opts']:
                if key not in valid_volume_create_opts:
                    msg = (_('create snapshot failed, error is: '
                             '%(key)s is not a valid option. Valid options '
                             'are: %(valid)s') %
                           {'key': key,
                            'valid': valid_volume_create_opts, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

        expiration_hrs = None
        if 'Opts' in contents and contents['Opts'] and \
                'expirationHours' in contents['Opts']:
            expiration_hrs = int(contents['Opts']['expirationHours'])

        retention_hrs = None
        if 'Opts' in contents and contents['Opts'] and \
                'retentionHours' in contents['Opts']:
            retention_hrs = int(contents['Opts']['retentionHours'])
        return self._manager.create_snapshot(src_vol_name,
                                             snapshot_name,
                                             expiration_hrs,
                                             retention_hrs)

    @app.route("/VolumeDriver.Mount", methods=["POST"])
    def volumedriver_mount(self, name):
        """
        Mount the volume
        Mount the volume

        NOTE: If for any reason the mount request fails, Docker
        will automatically call uMount. So, just make sure uMount
        can handle partially completed Mount requests.

        :param unicode name: The name of the volume.

        :return: Result that includes the mountpoint.
        """
        LOG.debug('In volumedriver_mount')

        # TODO: use persistent storage to lookup volume for deletion
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            volid = vol['id']
        else:
            msg = (_LE('Volume mount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        vol_mount = volume.DEFAULT_MOUNT_VOLUME
        if ('Opts' in contents and contents['Opts'] and
                'mount-volume' in contents['Opts']):
            vol_mount = str(contents['Opts']['mount-volume'])

        # Get connector info from OS Brick
        # TODO: retrieve use_multipath and enforce_multipath from config file
        root_helper = 'sudo'

        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, multipath=self.use_multipath,
            enforce_multipath=self.enforce_multipath)

        try:
            # Call driver to initialize the connection
            self.hpeplugin_driver.create_export(vol, connector_info)
            connection_info = \
                self.hpeplugin_driver.initialize_connection(
                    vol, connector_info)
            LOG.debug('connection_info: %(connection_info)s, '
                      'was successfully retrieved',
                      {'connection_info': json.dumps(connection_info)})
        except Exception as ex:
            msg = (_('connection info retrieval failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        # Call OS Brick to connect volume
        try:
            device_info = self.connector.\
                connect_volume(connection_info['data'])
        except Exception as ex:
            msg = (_('OS Brick connect volume failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        # Make sure the path exists
        path = FilePath(device_info['path']).realpath()
        if path.exists is False:
            msg = (_('path: %s,  does not exist'), path)
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        LOG.debug('path for volume: %(name)s, was successfully created: '
                  '%(device)s realpath is: %(realpath)s',
                  {'name': volname, 'device': device_info['path'],
                   'realpath': path.path})

        # Create filesystem on the new device
        if fileutil.has_filesystem(path.path) is False:
            fileutil.create_filesystem(path.path)
            LOG.debug('filesystem successfully created on : %(path)s',
                      {'path': path.path})

        # Determine if we need to mount the volume
        if vol_mount == volume.DEFAULT_MOUNT_VOLUME:
            # mkdir for mounting the filesystem
            mount_dir = fileutil.mkdir_for_mounting(device_info['path'])
            LOG.debug('Directory: %(mount_dir)s, '
                      'successfully created to mount: '
                      '%(mount)s',
                      {'mount_dir': mount_dir, 'mount': device_info['path']})

            # mount the directory
            fileutil.mount_dir(path.path, mount_dir)
            LOG.debug('Device: %(path) successfully mounted on %(mount)s',
                      {'path': path.path, 'mount': mount_dir})

            # TODO: find out how to invoke mkfs so that it creates the
            # filesystem without the lost+found directory
            # KLUDGE!!!!!
            lostfound = mount_dir + '/lost+found'
            lfdir = FilePath(lostfound)
            if lfdir.exists and fileutil.remove_dir(lostfound):
                LOG.debug('Successfully removed : '
                          '%(lost)s from mount: %(mount)s',
                          {'lost': lostfound, 'mount': mount_dir})
        else:
            mount_dir = ''

        path_info = {}
        path_info['name'] = volname
        path_info['path'] = path.path
        path_info['device_info'] = device_info
        path_info['connection_info'] = connection_info
        path_info['mount_dir'] = mount_dir

        self._etcd.update_vol(volid, 'path_info', json.dumps(path_info))

        response = json.dumps({u"Err": '', u"Name": volname,
                               u"Mountpoint": mount_dir,
                               u"Devicename": path.path})
        return response

    @app.route("/VolumeDriver.Path", methods=["POST"])
    def volumedriver_path(self, name):
        """
        Return the path of a locally mounted volume if possible.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        volinfo = self._etcd.get_vol_byname(volname)
        if volinfo is None:
            msg = (_LE('Volume Path: Volume name not found %s'), volname)
            LOG.warning(msg)
            response = json.dumps({u"Err": "No Mount Point",
                                   u"Mountpoint": ""})
            return response
        return self._manager.get_path(volname)

    @app.route("/VolumeDriver.Capabilities", methods=["POST"])
    def volumedriver_getCapabilities(self, body):
        capability = {"Capabilities": {"Scope": "global"}}
        response = json.dumps(capability)
        return response

    @app.route("/VolumeDriver.Get", methods=["POST"])
    def volumedriver_get(self, name):
        """
        Return volume information.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        qualified_name = contents['Name']
        tokens = qualified_name.split('/')
        token_cnt = len(tokens)

        if token_cnt > 2:
            msg = (_LE("invalid volume or snapshot name %s"
                       % qualified_name))
            LOG.error(msg)
            response = json.dumps({u"Err": msg})
            return response

        volname = tokens[0]
        snapname = None
        if token_cnt == 2:
            snapname = tokens[1]

        return self._manager.get_volume_snap_details(
            volname, snapname, qualified_name)

    @app.route("/VolumeDriver.List", methods=["POST"])
    def volumedriver_list(self, body):
        """
        Return a list of all volumes.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        return self._manager.list_volumes()

    def revert_to_snapshot(self, name, opts=None):
        contents = json.loads(name.content.getvalue())
        if 'Name' not in contents:
            msg = (_('revert snapshot failed, error is : Name is required'))
            LOG.errpr(msg)
            raise exception.HPEPluginCreateException(reason=msg)
        snapname = contents['Name']
        volumename = str(contents['Opts']['promote'])
        return self._manager.revert_to_snapshot(volumename, snapname)
