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
from config import setupcfg

import hpedockerplugin.exception as exception
from hpedockerplugin.i18n import _, _LE, _LI
from klein import Klein
from hpedockerplugin.hpe import volume

import hpedockerplugin.backend_orchestrator as orchestrator

LOG = logging.getLogger(__name__)

DEFAULT_BACKEND_NAME = "DEFAULT"


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
        self.conf = setupcfg.CONF

        # TODO: make device_scan_attempts configurable
        # see nova/virt/libvirt/volume/iscsi.py
        self.orchestrator = orchestrator.Orchestrator(hpepluginconfig)

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

        return self.orchestrator.volumedriver_remove(volname)

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
        return self.orchestrator.volumedriver_unmount(volname,
                                                      vol_mount, mount_id)

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
        fs_owner = None
        fs_mode = None
        mount_conflict_delay = volume.DEFAULT_MOUNT_CONFLICT_DELAY

        current_backend = DEFAULT_BACKEND_NAME
        if ('Opts' in contents and contents['Opts']):
            # Verify valid Opts arguments.
            valid_compression_opts = ['true', 'false']
            valid_volume_create_opts = ['mount-volume', 'compression',
                                        'size', 'provisioning', 'flash-cache',
                                        'cloneOf', 'virtualCopyOf',
                                        'expirationHours', 'retentionHours',
                                        'qos-name', 'fsOwner', 'fsMode',
                                        'mountConflictDelay',
                                        'help', 'importVol', 'scheduleName',
                                        'scheduleFrequency', 'snapshotPrefix',
                                        'expHrs', 'retHrs', 'backend']

            for key in contents['Opts']:
                if key not in valid_volume_create_opts:
                    msg = (_('create volume/snapshot/clone failed, error is: '
                             '%(key)s is not a valid option. Valid options '
                             'are: %(valid)s') %
                           {'key': key,
                            'valid': valid_volume_create_opts, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

            # mutually exclusive options check
            mutually_exclusive_list = ['virtualCopyOf', 'cloneOf', 'qos-name']
            input_list = list(contents['Opts'].keys())
            if (len(list(set(input_list) &
                         set(mutually_exclusive_list))) >= 2):
                msg = (_('%(exclusive)s cannot be specified at the same '
                         'time') % {'exclusive': mutually_exclusive_list, })
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

            if 'importVol' in input_list:
                if not len(input_list) == 1:
                    msg = (_('%(input_list)s cannot be specified at the same '
                             'time') % {'input_list': input_list, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

                existing_ref = str(contents['Opts']['importVol'])
                return self.orchestrator.manage_existing(volname,
                                                         existing_ref)

            if ('help' in contents['Opts']):
                create_help_path = "./config/create_help.txt"
                create_help_file = open(create_help_path, "r")
                create_help_content = create_help_file.read()
                create_help_file.close()
                LOG.error(create_help_content)
                return json.dumps({u"Err": create_help_content})

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
                if compression_val is not None:
                    if compression_val.lower() not in valid_compression_opts:
                        msg = \
                            _('create volume failed, error is:'
                              'passed compression parameter'
                              ' do not have a valid value. '
                              ' Valid vaues are: %(valid)s') % {
                                'valid': valid_compression_opts}
                        LOG.error(msg)
                        return json.dumps({u'Err': six.text_type(msg)})

            if ('flash-cache' in contents['Opts'] and
                    contents['Opts']['flash-cache'] != ""):
                vol_flash = str(contents['Opts']['flash-cache'])

            if ('qos-name' in contents['Opts'] and
                    contents['Opts']['qos-name'] != ""):
                vol_qos = str(contents['Opts']['qos-name'])

            if ('fsOwner' in contents['Opts'] and
                    contents['Opts']['fsOwner'] != ""):
                fs_owner = contents['Opts']['fsOwner']
                try:
                    mode = fs_owner.split(':')
                    uid = mode[0]
                    gid = mode[1]
                    fs_uid = int(uid)
                    fs_gid = int(gid)
                except ValueError as ex:
                    return json.dumps({'Err': "Invalid value '%s' specified "
                                       "for fsOwner. Please "
                                       "specify a correct value." %
                                       fs_owner})
                except IndexError as ex:
                    return json.dumps({'Err': "Invalid value '%s' specified "
                                       "for fsOwner. Please "
                                       "specify both uid and gid." %
                                       fs_owner})

            if ('fsMode' in contents['Opts'] and
                    contents['Opts']['fsMode'] != ""):
                fs_mode_str = contents['Opts']['fsMode']
                try:
                    fs_mode = int(fs_mode_str)
                except ValueError as ex:
                    return json.dumps({'Err': "Invalid value '%s' specified "
                                       "for fsMode. Please "
                                       "specify an integer value." %
                                       fs_mode_str})
                if fs_mode_str[0] != '0':
                    return json.dumps({'Err': "Invalid value '%s' specified "
                                              "for fsMode. Please "
                                              "specify an octal value." %
                                              fs_mode_str})
                for mode in fs_mode_str:
                    if int(mode) > 7:
                        return json.dumps({'Err': "Invalid value '%s' "
                                           "specified for fsMode. Please "
                                           "specify an octal value." %
                                           fs_mode_str})
                fs_mode = fs_mode_str

            if ('mountConflictDelay' in contents['Opts'] and
                    contents['Opts']['mountConflictDelay'] != ""):
                mount_conflict_delay_str = str(contents['Opts']
                                               ['mountConflictDelay'])
                try:
                    mount_conflict_delay = int(mount_conflict_delay_str)
                except ValueError as ex:
                    return json.dumps({'Err': "Invalid value '%s' specified "
                                              "for mountConflictDelay. Please"
                                              "specify an integer value." %
                                              mount_conflict_delay_str})
            if ('backend' in contents['Opts'] and
                    contents['Opts']['backend'] != ""):
                current_backend = str(contents['Opts']['backend'])

            if ('virtualCopyOf' in contents['Opts']):
                return self.volumedriver_create_snapshot(name,
                                                         mount_conflict_delay,
                                                         opts)
            elif ('cloneOf' in contents['Opts']):
                return self.volumedriver_clone_volume(name, opts)

        return self.orchestrator.volumedriver_create(volname, vol_size,
                                                     vol_prov,
                                                     vol_flash,
                                                     compression_val,
                                                     vol_qos,
                                                     fs_owner, fs_mode,
                                                     mount_conflict_delay,
                                                     current_backend)

    def _check_schedule_frequency(self, schedFrequency):
        freq_sched = schedFrequency
        sched_list = freq_sched.split(' ')
        if len(sched_list) != 5:
            msg = (_('create schedule failed, error is:'
                     ' Improper string passed.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

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
        return self.orchestrator.clone_volume(src_vol_name, clone_name, size)

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

        has_schedule = False
        expiration_hrs = None
        schedFrequency = None
        schedName = None
        snapPrefix = None
        exphrs = None
        rethrs = None

        if 'Opts' in contents and contents['Opts'] and \
                'scheduleName' in contents['Opts']:
            has_schedule = True

        if 'Opts' in contents and contents['Opts'] and \
                'expirationHours' in contents['Opts']:
            expiration_hrs = int(contents['Opts']['expirationHours'])
            if has_schedule:
                msg = ('create schedule failed, error is: setting '
                       'expiration_hours for docker snapshot is not'
                       ' allowed while creating a schedule.')
                LOG.error(msg)
                response = json.dumps({'Err': msg})
                return response

        retention_hrs = None
        if 'Opts' in contents and contents['Opts'] and \
                'retentionHours' in contents['Opts']:
            retention_hrs = int(contents['Opts']['retentionHours'])

        if has_schedule:
            if 'scheduleFrequency' not in contents['Opts']:
                msg = ('create schedule failed, error is: user  '
                       'has not passed scheduleFrequency to create'
                       ' snapshot schedule.')
                LOG.error(msg)
                response = json.dumps({'Err': msg})
                return response
            else:
                schedFrequency = str(contents['Opts']['scheduleFrequency'])
                if 'expHrs' in contents['Opts']:
                    exphrs = int(contents['Opts']['expHrs'])
                if 'retHrs' in contents['Opts']:
                    rethrs = int(contents['Opts']['retHrs'])
                    if exphrs is not None:
                        if rethrs > exphrs:
                            msg = ('create schedule failed, error is: '
                                   'expiration hours cannot be greater than '
                                   'retention hours')
                            LOG.error(msg)
                            response = json.dumps({'Err': msg})
                            return response

                if 'scheduleName' not in contents['Opts'] or \
                        'snapshotPrefix' not in contents['Opts']:
                    msg = ('Please make sure that valid schedule name is '
                           'passed or please provide a 3 letter prefix for '
                           'this schedule ')
                    LOG.error(msg)
                    response = json.dumps({'Err': msg})
                    return response
                schedName = str(contents['Opts']['scheduleName'])
                snapPrefix = str(contents['Opts']['snapshotPrefix'])
            try:
                self._check_schedule_frequency(schedFrequency)
            except Exception as ex:
                msg = (_('Invalid schedule string is passed: %s ')
                       % six.text_type(ex))
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

        return self.orchestrator.create_snapshot(src_vol_name, schedName,
                                                 snapshot_name, snapPrefix,
                                                 expiration_hrs, exphrs,
                                                 retention_hrs, rethrs,
                                                 mount_conflict_delay,
                                                 has_schedule,
                                                 schedFrequency)

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

        return self.orchestrator.mount_volume(volname, vol_mount, mount_id)

    @app.route("/VolumeDriver.Path", methods=["POST"])
    def volumedriver_path(self, name):
        """
        Return the path of a locally mounted volume if possible.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']

        return self.orchestrator.get_path(volname)

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

        return self.orchestrator.get_volume_snap_details(volname, snapname,
                                                         qualified_name)

    @app.route("/VolumeDriver.List", methods=["POST"])
    def volumedriver_list(self, body):
        """
        Return a list of all volumes.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        return self.orchestrator.volumedriver_list()
