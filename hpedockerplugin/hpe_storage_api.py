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
        volname = contents['Name']
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
        mount_conflict_delay = volume.DEFAULT_MOUNT_CONFLICT_DELAY
        cpg = None
        snap_cpg = None

        # Verify valid Opts arguments.
        valid_volume_create_opts = ['mount-volume', 'compression',
                                    'size', 'provisioning', 'flash-cache',
                                    'cloneOf', 'virtualCopyOf',
                                    'expirationHours', 'retentionHours',
                                    'qos-name',
                                    'mountConflictDelay',
                                    'cpg', 'snap-cpg']

        if ('Opts' in contents and contents['Opts']):
            for key in contents['Opts']:
                if key not in valid_volume_create_opts:
                    msg = (_('create volume/snapshot/clone failed, error is: '
                             '%(key)s is not a valid option. Valid options '
                             'are: %(valid)s') %
                           {'key': key,
                            'valid': valid_volume_create_opts, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

            # Populating the values
            if ('size' in contents['Opts'] and
                    contents['Opts']['size'] != ""):
                vol_size = int(contents['Opts']['size'])

            if ('provisioning' in contents['Opts'] and
                    contents['Opts']['provisioning'] != ""):
                vol_prov = str(contents['Opts']['provisioning'])

            if ('compression' in contents['Opts'] and
                    contents['Opts']['compression'] != ""):
                compression_val = str(contents['Opts']['compression'])

            if ('flash-cache' in contents['Opts'] and
                    contents['Opts']['flash-cache'] != ""):
                vol_flash = str(contents['Opts']['flash-cache'])

            if ('qos-name' in contents['Opts'] and
                    contents['Opts']['qos-name'] != ""):
                vol_qos = str(contents['Opts']['qos-name'])

            if ('mountConflictDelay' in contents['Opts'] and
                    contents['Opts']['mountConflictDelay'] != ""):
                mount_conflict_delay_str = str(contents['Opts']
                                               ['mountConflictDelay'])

            if ('cpg' in contents['Opts'] and
                        contents['Opts']['cpg'] != ""):
                cpg = str(contents['Opts']['cpg'])

            if ('snap-cpg' in contents['Opts'] and
                        contents['Opts']['snap-cpg'] != ""):
                snap_cpg = str(contents['Opts']['snap-cpg'])

                try:
                    mount_conflict_delay = int(mount_conflict_delay_str)
                except ValueError as ex:
                    return json.dumps({'Err': "Invalid value '%s' specified "
                                              "for mountConflictDelay. Please"
                                              "specify an integer value." %
                                              mount_conflict_delay_str})

            # mutually exclusive options check
            mutually_exclusive_list = ['virtualCopyOf', 'cloneOf', 'qos-name']
            input_list = contents['Opts'].keys()
            if (len(list(set(input_list) &
                         set(mutually_exclusive_list))) >= 2):
                msg = (_('%(exclusive)s cannot be specified at the same '
                         'time') % {'exclusive': mutually_exclusive_list, })
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

            if ('virtualCopyOf' in contents['Opts']):
                return self.volumedriver_create_snapshot(name,
                                                         mount_conflict_delay,
                                                         opts)
            elif ('cloneOf' in contents['Opts']):
                return self.volumedriver_clone_volume(name, opts)

        if compression_val is not None:
            if compression_val.lower() not in valid_compression_opts:
                msg = (_('create volume failed, error is:'
                         'passed compression parameter do not have a valid '
                         'value. Valid vaues are: %(valid)s') %
                       {'valid': valid_compression_opts, })
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

        return self._manager.create_volume(volname, vol_size,
                                           vol_prov, vol_flash,
                                           compression_val, vol_qos,
                                           mount_conflict_delay,
                                           cpg, snap_cpg)

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

    def volumedriver_create_snapshot(self, name, mount_conflict_delay,
                                     opts=None):
        # Repeating the validation here in anticipation that when
        # actual REST call for snapshot creation is added, this
        # function will have minimal impact
        contents = json.loads(name.content.getvalue())

        LOG.info("creating snapshot:\n%s" % json.dumps(contents, indent=2))

        if 'Name' not in contents:
            msg = (_('create snapshot failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

        src_vol_name = str(contents['Opts']['virtualCopyOf'])
        snapshot_name = contents['Name']

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
                                             retention_hrs,
                                             mount_conflict_delay)

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
