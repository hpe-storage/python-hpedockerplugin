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
from os_brick.initiator import connector
from oslo_utils import netutils
import uuid
from i18n import _, _LE, _LI, _LW
import exception
import six

import json

from twisted.python.filepath import FilePath

import fileutil

from klein import Klein
from hpe import volume
from oslo_utils import importutils
import etcdutil as util

from twisted.internet import threads
from oslo_log import log as logging

import time

DEFAULT_SIZE = 100
DEFAULT_PROV = "thin"
DEFAULT_FLASH_CACHE = None

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

        self._etcd = util.EtcdUtil(
            self._hpepluginconfig.host_etcd_ip_address,
            self._hpepluginconfig.host_etcd_port_number,
            self._hpepluginconfig.host_etcd_client_cert,
            self._hpepluginconfig.host_etcd_client_key)

        # TODO: make use_multipath and device_scan_attempts configurable
        # see nova/virt/libvirt/volume/iscsi.py
        root_helper = 'sudo'
        self.connector = connector.InitiatorConnector.factory(
            'ISCSI', root_helper, use_multipath=False, device_scan_attempts=5,
            transport='default')

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
        volname = contents['Name']

        # Only 1 node in a multinode cluster can try to remove the volume.
        # Grab lock for volume name. If lock is inuse, just return with no
        # error.
        self._lock_volume(volname, 'Remove')

        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            # Just log an error, but don't fail the docker rm command
            msg = (_LE('Volume remove name not found %s'), volname)
            LOG.error(msg)
            self._unlock_volume(volname)
            return json.dumps({u"Err": ''})

        try:
            self.hpeplugin_driver.delete_volume(vol)
            LOG.info(_LI('volume: %(name)s,' 'was successfully deleted'),
                     {'name': volname})
        except Exception as ex:
            msg = (_LE('Err: Failed to remove volume %s, error is %s'),
                   volname, six.text_type(ex))
            LOG.error(msg)
            self._unlock_volume(volname)
            raise exception.HPEPluginRemoveException(reason=msg)

        try:
            self._etcd.delete_vol(vol)
        except KeyError:
            msg = (_LW('Warning: Failed to delete volume key: %s from '
                       'etcd due to KeyError'), volname)
            LOG.warning(msg)
            pass

        self._unlock_volume(volname)
        return json.dumps({u"Err": ''})

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
        use_multipath = False

        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, use_multipath, enforce_multipath=False)
        # unmount directory
        fileutil.umount_dir(mount_dir)
        # remove directory
        fileutil.remove_dir(mount_dir)

        # We're deferring the execution of the disconnect_volume as it can take
        # substantial
        # time (over 2 minutes) to cleanup the iscsi files
        if connection_info:
            LOG.info(_LI('call os brick to disconnect volume'))
            d = threads.deferToThread(self.connector.disconnect_volume,
                                      connection_info['data'], None)
            d.addCallbacks(self.disconnect_volume_callback,
                           self.disconnect_volume_error_callback)

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

    def _lock_volume(self, volname, op):
        try:
            self._etcd.try_lock_volname(volname)
        except Exception:
            LOG.debug('volume: %(name)s Volume %(op)s in progress',
                      {'name': volname}, {'op': op})
            response = json.dumps({u"Err": ''})
            return response

    def _unlock_volume(self, volname):
        try:
            self._etcd.try_unlock_volname(volname)
        except Exception as ex:
            LOG.debug('volume: %(name)s Unlock Volume Failed',
                      {'name': volname})
            response = json.dumps({u"Err": six.text_type(ex)})
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

        # Verify valid Opts arguments.
        valid_volume_create_opts = ['size', 'provisioning', 'flash-cache']
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

        vol_size = DEFAULT_SIZE
        if ('Opts' in contents and contents['Opts'] and
                'size' in contents['Opts']):
            vol_size = int(contents['Opts']['size'])

        vol_prov = DEFAULT_PROV
        if ('Opts' in contents and contents['Opts'] and
                'provisioning' in contents['Opts']):
            vol_prov = str(contents['Opts']['provisioning'])

        vol_flash = DEFAULT_FLASH_CACHE
        if ('Opts' in contents and contents['Opts'] and
                'flash-cache' in contents['Opts']):
            vol_flash = str(contents['Opts']['flash-cache'])

        LOG.debug('In volumedriver_create')

        # Grab lock for volume name. If lock is inuse, just return with no
        # error
        self._lock_volume(volname, 'Create')

        # NOTE: Since Docker passes user supplied names and not a unique
        # uuid, we can't allow duplicate volume names to exist.
        # TODO: Should confirm with Docker on how why they allow the
        # 'docker volume create" command to create duplicate volume names.
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            # Release lock and return
            self._unlock_volume(volname)
            return json.dumps({u"Err": ''})

        voluuid = str(uuid.uuid4())
        vol = volume.createvol(volname, voluuid, vol_size, vol_prov, vol_flash)

        try:
            self.hpeplugin_driver.create_volume(vol)
        except Exception as ex:
            msg = (_('create volume failed, error is: %s'), six.text_type(ex))
            LOG.error(msg)
            # Release lock and return
            # NOTE: if for some reason unlock fails, we'll lose this
            # create exception.
            self._unlock_volume(volname)
            return json.dumps({u"Err": six.text_type(ex)})

        response = json.dumps({u"Err": ''})
        try:
            # For now just track volume to uuid mapping internally
            # TODO: Save volume name and uuid mapping in etcd as well
            # This will make get_vol_byname more efficient
            self._etcd.save_vol(vol)
            LOG.debug('volume: %(name)s was successfully saved to etcd',
                      {'name': volname})
        except Exception as ex:
            msg = (_('save volume to etcd failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            response = json.dumps({u"Err": six.text_type(ex)})

        self._unlock_volume(volname)
        return response

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
        contents = {}
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            volid = vol['id']
        else:
            msg = (_LE('Volume mount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        # Get connector info from OS Brick
        # TODO: retrieve use_multipath and enforce_multipath from config file
        root_helper = 'sudo'
        use_multipath = False

        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, use_multipath, enforce_multipath=False)

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

        # mkdir for mounting the filesystem
        mount_dir = fileutil.mkdir_for_mounting(device_info['path'])
        LOG.debug('Directory: %(mount_dir)s, successfully created to mount: '
                  '%(mount)s',
                  {'mount_dir': mount_dir, 'mount': device_info['path']})

        # Create filesystem on the new device
        if fileutil.has_filesystem(path.path) is False:
            fileutil.create_filesystem(path.path)
            LOG.debug('filesystem successfully created on : %(path)s',
                      {'path': path.path})

        # mount the directory
        fileutil.mount_dir(path.path, mount_dir)
        LOG.debug('Device: %(path) successfully mounted on %(mount)s',
                  {'path': path.path, 'mount': mount_dir})

        # TODO: find out how to invoke mkfs so that it creates the filesystem
        # without the lost+found directory
        # KLUDGE!!!!!
        lostfound = mount_dir + '/lost+found'
        lfdir = FilePath(lostfound)
        if lfdir.exists and fileutil.remove_dir(lostfound):
            LOG.debug('Successfully removed : %(lost)s from mount: %(mount)s',
                      {'lost': lostfound, 'mount': mount_dir})

        path_info = {}
        path_info['name'] = volname
        path_info['path'] = path.path
        path_info['device_info'] = device_info
        path_info['connection_info'] = connection_info
        path_info['mount_dir'] = mount_dir

        self._etcd.update_vol(volid, 'path_info', json.dumps(path_info))

        response = json.dumps({u"Err": '', u"Mountpoint": mount_dir})
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

        path_name = ''
        path_info = self._etcd.get_vol_path_info(volname)

        if path_info is not None:
            path_name = path_info['mount_dir']

        response = json.dumps({u"Err": '', u"Mountpoint": path_name})
        return response

    @app.route("/VolumeDriver.Get", methods=["POST"])
    def volumedriver_get(self, name):
        """
        Return volume information.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        volinfo = self._etcd.get_vol_byname(volname)
        err = ''
        if volinfo is None:
            msg = (_LE('Volume Get: Volume name not found %s'), volname)
            LOG.warning(msg)
            response = json.dumps({u"Err": ""})
            return response

        path_info = self._etcd.get_vol_path_info(volname)
        if path_info is not None:
            mountdir = path_info['mount_dir']
        else:
            mountdir = ''

        volume = {'Name': volname,
                  'Mountpoint': mountdir,
                  'Status': {}}

        response = json.dumps({u"Err": err, u"Volume": volume})
        return response

    @app.route("/VolumeDriver.List", methods=["POST"])
    def volumedriver_list(self, body):
        """
        Return a list of all volumes.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        volumes = self._etcd.get_all_vols()

        if volumes is None:
            response = json.dumps({u"Err": ''})
            return response

        volumelist = []
        for volinfo in volumes.children:
            if volinfo.key != util.VOLUMEROOT:
                path_info = self._etcd.get_path_info_from_vol(volinfo.value)
                if path_info is not None and 'mount_dir' in path_info:
                    mountdir = path_info['mount_dir']
                else:
                    mountdir = ''
                info = json.loads(volinfo.value)
                volume = {'Name': info['display_name'],
                          'Mountpoint': mountdir}
                volumelist.append(volume)

        response = json.dumps({u"Err": '', u"Volumes": volumelist})
        return response
