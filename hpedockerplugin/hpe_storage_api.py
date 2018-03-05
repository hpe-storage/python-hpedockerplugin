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

from oslo_log import log as logging

import exception
from i18n import _, _LE, _LI
from klein import Klein
from hpe import volume
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

        # TODO: make device_scan_attempts configurable
        # see nova/virt/libvirt/volume/iscsi.py
        self._manager = mgr.VolumeManager(hpepluginconfig)

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

        vol_mount = volume.DEFAULT_MOUNT_VOLUME
        if ('Opts' in contents and contents['Opts'] and
                'mount-volume' in contents['Opts']):
            vol_mount = str(contents['Opts']['mount-volume'])

        mount_id = contents['ID']
        return self._manager.unmount_volume(volname, vol_mount, mount_id)

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

        vol_mount = volume.DEFAULT_MOUNT_VOLUME
        if ('Opts' in contents and contents['Opts'] and
                'mount-volume' in contents['Opts']):
            vol_mount = str(contents['Opts']['mount-volume'])

        mount_id = contents['ID']
        return self._manager.mount_volume(volname, vol_mount, mount_id)

    @app.route("/VolumeDriver.Path", methods=["POST"])
    def volumedriver_path(self, name):
        """
        Return the path of a locally mounted volume if possible.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
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
