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
import datetime

from oslo_log import log as logging

import hpedockerplugin.exception as exception
from hpedockerplugin.i18n import _, _LE, _LI
from klein import Klein
from hpedockerplugin.hpe import volume
from ratelimit import limits
from ratelimit.exception import RateLimitException
from backoff import on_exception, expo

import hpedockerplugin.backend_orchestrator as orchestrator
import hpedockerplugin.request_validator as req_validator
import hpedockerplugin.file_backend_orchestrator as f_orchestrator
import hpedockerplugin.request_router as req_router

LOG = logging.getLogger(__name__)


class VolumePlugin(object):
    """
    An implementation of the Docker Volumes Plugin API.

    """
    app = Klein()

    def __init__(self, reactor, all_configs):
        """
        :param IReactorTime reactor: Reactor time interface implementation.
        :param Ihpepluginconfig : hpedefaultconfig configuration
        """
        LOG.info(_LI('Initialize Volume Plugin'))

        self._reactor = reactor
        self.orchestrator = None
        if 'block' in all_configs:
            block_configs = all_configs['block']
            self._host_config = block_configs[0]
            self._backend_configs = block_configs[1]
            if 'DEFAULT' in self._backend_configs:
                self._def_backend_name = 'DEFAULT'
            elif 'DEFAULT_BLOCK' in self._backend_configs:
                self._def_backend_name = 'DEFAULT_BLOCK'
            else:
                msg = "ERROR: DEFAULT backend is not present for the BLOCK " \
                      "driver configuration. If DEFAULT backend has been " \
                      "configured for FILE driver, then DEFAULT_BLOCK " \
                      "backend MUST be configured for BLOCK driver in " \
                      "hpe.conf file."
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)
            if 'DEFAULT_FILE' in self._backend_configs:
                msg = "ERROR: 'DEFAULT_FILE' backend cannot be defined " \
                      "for BLOCK driver."
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

            self.orchestrator = orchestrator.VolumeBackendOrchestrator(
                self._host_config, self._backend_configs,
                self._def_backend_name)
            self._req_validator = req_validator.RequestValidator(
                self._backend_configs)

        self._file_orchestrator = None
        if 'file' in all_configs:
            file_configs = all_configs['file']
            self._f_host_config = file_configs[0]
            self._f_backend_configs = file_configs[1]

            if 'DEFAULT' in self._f_backend_configs:
                self._f_def_backend_name = 'DEFAULT'
            elif 'DEFAULT_FILE' in self._f_backend_configs:
                self._f_def_backend_name = 'DEFAULT_FILE'
            else:
                msg = "ERROR: DEFAULT backend is not present for the FILE " \
                      "driver configuration. If DEFAULT backend has been " \
                      "configured for BLOCK driver, then DEFAULT_FILE " \
                      "backend MUST be configured for FILE driver in " \
                      "hpe.conf file."
                raise exception.InvalidInput(reason=msg)

            if 'DEFAULT_BLOCK' in self._f_backend_configs:
                msg = "ERROR: 'DEFAULT_BLOCK' backend cannot be defined " \
                      "for FILE driver."
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

            self._file_orchestrator = f_orchestrator.FileBackendOrchestrator(
                self._f_host_config, self._f_backend_configs,
                self._f_def_backend_name)

        self._req_router = req_router.RequestRouter(
            vol_orchestrator=self.orchestrator,
            file_orchestrator=self._file_orchestrator,
            all_configs=all_configs)

    def is_backend_initialized(self, backend_name):
        if (backend_name not in self._backend_configs and
                backend_name not in self._f_backend_configs):
            return 'FAILED'

        if backend_name in self.orchestrator._manager:
            mgr_obj = self.orchestrator._manager[backend_name]
            return mgr_obj.get('backend_state')
        if backend_name in self._file_orchestrator._manager:
            mgr_obj = self._file_orchestrator._manager[backend_name]
            return mgr_obj.get('backend_state')
        return 'INITIALIZING'

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

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=25, period=30)
    @app.route("/VolumeDriver.Remove", methods=["POST"])
    def volumedriver_remove(self, name):
        """
        Remove a Docker volume.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        name = contents['Name']

        LOG.info("Routing remove request...")
        try:
            return self._req_router.route_remove_request(name)
        # If share is not found by this name, allow volume driver
        # to handle the request by passing the except clause
        except exception.EtcdMetadataNotFound:
            pass
        except exception.PluginException as ex:
            return json.dumps({"Err": ex.msg})
        except Exception as ex:
            msg = six.text_type(ex)
            LOG.error(msg)
            return json.dumps({"Err": msg})

        if self.orchestrator:
            try:
                return self.orchestrator.volumedriver_remove(name)
            except exception.PluginException as ex:
                return json.dumps({"Err": ex.msg})
            except Exception as ex:
                msg = six.text_type(ex)
                LOG.error(msg)
                return json.dumps({"Err": msg})

        return json.dumps({"Err": ""})

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=25, period=30)
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

        mount_id = contents['ID']

        try:
            return self._req_router.route_unmount_request(volname, mount_id)
        except exception.EtcdMetadataNotFound:
            pass

        if self.orchestrator:
            return self.orchestrator.volumedriver_unmount(
                volname, vol_mount, mount_id)
        return json.dumps({"Err": "Unmount failed: volume/file '%s' not found"
                                  % volname})

    @app.route("/VolumeDriver.Create", methods=["POST"])
    def volumedriver_create(self, request, opts=None):
        """
        Create a volume with the given name.

        :param unicode request: Request data
        :param dict opts: Options passed from Docker for the volume
            at creation. ``None`` if not supplied in the request body.
            Currently ignored. ``Opts`` is a parameter introduced in the
            v2 plugins API introduced in Docker 1.9, it is not supplied
            in earlier Docker versions.

        :return: Result indicating success.
        """
        contents = json.loads(request.content.getvalue())
        if 'Name' not in contents:
            msg = (_('create volume failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

        name = contents['Name']

        if ((self.orchestrator and
             self.orchestrator.volume_exists(name)) or
            (self._file_orchestrator and
             self._file_orchestrator.share_exists(name))):
            return json.dumps({'Err': ''})

        # Try to handle this as file persona operation
        if 'Opts' in contents and contents['Opts']:
            if 'filePersona' in contents['Opts']:
                try:
                    return self._req_router.route_create_request(
                        name, contents, self._file_orchestrator
                    )
                except exception.PluginException as ex:
                    LOG.error(six.text_type(ex))
                    return json.dumps({'Err': ex.msg})
                except Exception as ex:
                    LOG.error(six.text_type(ex))
                    return json.dumps({'Err': six.text_type(ex)})

        if not self.orchestrator:
            return json.dumps({"Err": "ERROR: Cannot create volume '%s'. "
                                      "Volume driver is not configured" %
                                      name})

        # Continue with volume creation operations
        try:
            self._req_validator.validate_request(contents)
        except exception.InvalidInput as ex:
            return json.dumps({"Err": ex.msg})

        vol_size = volume.DEFAULT_SIZE
        vol_prov = volume.DEFAULT_PROV
        vol_flash = volume.DEFAULT_FLASH_CACHE
        vol_qos = volume.DEFAULT_QOS
        compression_val = volume.DEFAULT_COMPRESSION_VAL
        valid_bool_opts = ['true', 'false']
        fs_owner = None
        fs_mode = None
        mount_conflict_delay = volume.DEFAULT_MOUNT_CONFLICT_DELAY
        cpg = None
        snap_cpg = None
        rcg_name = None

        current_backend = self._def_backend_name
        if 'Opts' in contents and contents['Opts']:
            # Verify valid Opts arguments.
            valid_volume_create_opts = [
                'compression', 'size', 'provisioning', 'flash-cache',
                'cloneOf', 'virtualCopyOf', 'expirationHours',
                'retentionHours', 'qos-name', 'fsOwner', 'fsMode',
                'mountConflictDelay', 'help', 'importVol', 'cpg',
                'snapcpg', 'scheduleName', 'scheduleFrequency',
                'snapshotPrefix', 'expHrs', 'retHrs', 'backend',
                'replicationGroup', 'manager'
            ]
            valid_snap_schedule_opts = ['scheduleName', 'scheduleFrequency',
                                        'snapshotPrefix', 'expHrs', 'retHrs']
            mutually_exclusive = [
                ['virtualCopyOf', 'cloneOf', 'qos-name', 'replicationGroup'],
                ['virtualCopyOf', 'cloneOf', 'backend']
            ]
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
            input_list = list(contents['Opts'].keys())
            for li in mutually_exclusive:
                if (len(list(set(input_list) & set(li))) >= 2):
                    msg = (_('%(exclusive)s cannot be specified at the same '
                             'time') % {'exclusive': li, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

            if ('backend' in contents['Opts'] and
                    contents['Opts']['backend'] != ""):
                current_backend = str(contents['Opts']['backend'])
                if current_backend == 'DEFAULT_FILE':
                    msg = 'Backend DEFAULT_FILE is reserved for File ' \
                          'Persona. Cannot specify it for Block operations'
                    LOG.error(msg)
                    return json.dumps({'Err': msg})

                # check if current_backend present in config file
                if current_backend in self._backend_configs:
                    # check if current_backend is initialised
                    if current_backend not in self.orchestrator._manager:
                        msg = 'Backend: %s having incorrect/missing some ' \
                              'configuration.' % current_backend
                        LOG.error(msg)
                        return json.dumps({u"Err": msg})
                else:
                    msg = 'Backend: %s not present in config.' \
                          % current_backend
                    LOG.error(msg)
                    return json.dumps({u"Err": msg})

            if 'importVol' in input_list:
                existing_ref = str(contents['Opts']['importVol'])
                return self.orchestrator.manage_existing(name,
                                                         existing_ref,
                                                         current_backend,
                                                         contents['Opts'])

            if 'help' in contents['Opts']:
                return self._process_help(contents['Opts']['help'])

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
                    if compression_val.lower() not in valid_bool_opts:
                        msg = \
                            _('create volume failed, error is:'
                              'passed compression parameter'
                              ' do not have a valid value. '
                              'Valid vaues are: %(valid)s') % {
                                'valid': valid_bool_opts}
                        LOG.error(msg)
                        return json.dumps({u'Err': six.text_type(msg)})

            if ('flash-cache' in contents['Opts'] and
                    contents['Opts']['flash-cache'] != ""):
                vol_flash = str(contents['Opts']['flash-cache'])
                if vol_flash is not None:
                    if vol_flash.lower() not in valid_bool_opts:
                        msg = \
                            _('create volume failed, error is:'
                              'passed flash-cache parameter'
                              ' do not have a valid value. '
                              'Valid vaues are: %(valid)s') % {
                                'valid': valid_bool_opts}
                        LOG.error(msg)
                        return json.dumps({u'Err': six.text_type(msg)})

            if ('qos-name' in contents['Opts'] and
                    contents['Opts']['qos-name'] != ""):
                vol_qos = str(contents['Opts']['qos-name'])
            if ('cpg' in contents['Opts'] and
                    contents['Opts']['cpg'] != ""):
                cpg = str(contents['Opts']['cpg'])

            if ('snapcpg' in contents['Opts'] and
                    contents['Opts']['snapcpg'] != ""):
                snap_cpg = str(contents['Opts']['snapcpg'])

            if ('fsOwner' in contents['Opts'] and
                    contents['Opts']['fsOwner'] != ""):
                fs_owner = contents['Opts']['fsOwner']
                try:
                    uid, gid = fs_owner.split(':')
                    int(uid)
                    int(gid)
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

            if ('virtualCopyOf' in contents['Opts']):
                if (('cpg' in contents['Opts'] and
                     contents['Opts']['cpg'] is not None) or
                    ('snapcpg' in contents['Opts'] and
                     contents['Opts']['snapcpg'] is not None)):
                    msg = (_('''Virtual copy creation failed, error is:
                           cpg or snap - cpg not allowed for
                           virtual copy creation. '''))
                    LOG.error(msg)
                    response = json.dumps({u"Err": msg})
                    return response
                schedule_opts = valid_snap_schedule_opts[1:]
                for s_o in schedule_opts:
                    if s_o in input_list:
                        if "scheduleName" not in input_list:
                            msg = (_('scheduleName is a mandatory parameter'
                                     ' for creating a snapshot schedule'))
                            LOG.error(msg)
                            response = json.dumps({u"Err": msg})
                            return response
                        break
                return self.volumedriver_create_snapshot(request,
                                                         mount_conflict_delay,
                                                         opts)
            elif 'cloneOf' in contents['Opts']:
                LOG.info('hpe_storage_api: clone options : %s' %
                         contents['Opts'])
                return self.volumedriver_clone_volume(request,
                                                      contents['Opts'])
            for i in input_list:
                if i in valid_snap_schedule_opts:
                    if 'virtualCopyOf' not in input_list:
                        msg = (_('virtualCopyOf is a mandatory parameter for'
                                 ' creating a snapshot schedule'))
                        LOG.error(msg)
                        response = json.dumps({u"Err": msg})
                        return response

            rcg_name = contents['Opts'].get('replicationGroup', None)

        if (cpg and rcg_name) or (snap_cpg and rcg_name):
            msg = "cpg/snap_cpg and replicationGroup options cannot be " \
                  "specified together"
            return json.dumps({u"Err": msg})

        # It is possible that the user configured replication in hpe.conf
        # but didn't specify any options. In that case too, this operation
        # must fail asking for "replicationGroup" parameter
        # Hence this validation must be done whether "Opts" is there or not
        try:
            self._validate_rcg_params(rcg_name, current_backend)
        except exception.InvalidInput as ex:
            return json.dumps({u"Err": ex.msg})

        return self.orchestrator.volumedriver_create(name, vol_size,
                                                     vol_prov,
                                                     vol_flash,
                                                     compression_val,
                                                     vol_qos,
                                                     fs_owner, fs_mode,
                                                     mount_conflict_delay,
                                                     cpg, snap_cpg,
                                                     current_backend,
                                                     rcg_name)

    def _process_help(self, help):
        LOG.info("Working on help content generation...")
        if help == 'backends':

            line = "=" * 54
            spaces = ' ' * 42
            resp = "\n%s\nNAME%sSTATUS\n%s\n" % (line, spaces, line)

            printable_len = 45
            for k, v in self.orchestrator._manager.items():
                backend_state = v['backend_state']
                padding = (printable_len - len(k)) * ' '
                resp += "%s%s  %s\n" % (k, padding, backend_state)
            return json.dumps({u'Err': resp})
        else:
            create_help_path = "./config/create_help.txt"
            create_help_file = open(create_help_path, "r")
            create_help_content = create_help_file.read()
            create_help_file.close()
            LOG.error(create_help_content)
            return json.dumps({u"Err": create_help_content})

    def _validate_rcg_params(self, rcg_name, backend_name):
        LOG.info("Validating RCG: %s, backend name: %s..." % (rcg_name,
                                                              backend_name))
        hpepluginconfig = self._backend_configs[backend_name]
        replication_device = hpepluginconfig.replication_device

        LOG.info("Replication device: %s" % six.text_type(replication_device))

        if rcg_name and not replication_device:
            msg = "Request to create replicated volume cannot be fulfilled " \
                  "without defining 'replication_device' entry defined in " \
                  "hpe.conf for the backend '%s'. Please add it and execute " \
                  "the request again." % backend_name
            raise exception.InvalidInput(reason=msg)

        if replication_device and not rcg_name:
            LOG.info("'%s' is a replication enabled backend. "
                     "'replicationGroup' is not specified in the create "
                     "volume command. Proceeding to create a regular "
                     "volume without remote copy "
                     "capabilities." % (backend_name))

        if rcg_name and replication_device:

            def _check_valid_replication_mode(mode):
                valid_modes = ['synchronous', 'asynchronous', 'streaming']
                if mode.lower() not in valid_modes:
                    msg = "Unknown replication mode '%s' specified. Valid " \
                          "values are 'synchronous | asynchronous | " \
                          "streaming'" % mode
                    raise exception.InvalidInput(reason=msg)

            rep_mode = replication_device['replication_mode'].lower()
            _check_valid_replication_mode(rep_mode)
            if replication_device.get('quorum_witness_ip'):
                if rep_mode.lower() != 'synchronous':
                    msg = "For Peer Persistence, replication mode must be " \
                          "synchronous"
                    raise exception.InvalidInput(reason=msg)

            sync_period = replication_device.get('sync_period')
            if sync_period and rep_mode == 'synchronous':
                msg = "'sync_period' can be defined only for 'asynchronous'" \
                      " and 'streaming' replicate modes"
                raise exception.InvalidInput(reason=msg)

            if (rep_mode == 'asynchronous' or rep_mode == 'streaming')\
                    and sync_period:
                try:
                    sync_period = int(sync_period)
                except ValueError as ex:
                    msg = "Non-integer value '%s' not allowed for " \
                          "'sync_period'. %s" % (
                              replication_device.sync_period, ex)
                    raise exception.InvalidInput(reason=msg)
                else:
                    SYNC_PERIOD_LOW = 300
                    SYNC_PERIOD_HIGH = 31622400
                    if sync_period < SYNC_PERIOD_LOW or \
                       sync_period > SYNC_PERIOD_HIGH:
                        msg = "'sync_period' must be between 300 and " \
                              "31622400 seconds."
                        raise exception.InvalidInput(reason=msg)

    def _check_schedule_frequency(self, schedFrequency):
        freq_sched = schedFrequency
        sched_list = freq_sched.split(' ')
        if len(sched_list) != 5:
            msg = (_('create schedule failed, error is:'
                     ' Improper string passed.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

    def volumedriver_clone_volume(self, name, clone_opts=None):
        # Repeating the validation here in anticipation that when
        # actual REST call for clone is added, this
        # function will have minimal impact
        contents = json.loads(name.content.getvalue())
        if 'Name' not in contents:
            msg = (_('clone volume failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)
        cpg = None
        size = None
        snap_cpg = None
        if ('Opts' in contents and contents['Opts'] and
                'size' in contents['Opts']):
            size = int(contents['Opts']['size'])
        if ('Opts' in contents and contents['Opts'] and
                'cpg' in contents['Opts']):
            cpg = str(contents['Opts']['cpg'])

        if ('Opts' in contents and contents['Opts'] and
                'snapcpg' in contents['Opts']):
            snap_cpg = str(contents['Opts']['snapcpg'])

        src_vol_name = str(contents['Opts']['cloneOf'])
        clone_name = contents['Name']
        LOG.info('hpe_storage_api - volumedriver_clone_volume '
                 'clone_options 1 : %s ' % clone_opts)

        return self.orchestrator.clone_volume(src_vol_name, clone_name, size,
                                              cpg, snap_cpg, clone_opts)

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

        retention_hrs = None
        if 'Opts' in contents and contents['Opts'] and \
                'retentionHours' in contents['Opts']:
            retention_hrs = int(contents['Opts']['retentionHours'])

        if has_schedule:
            if 'expirationHours' in contents['Opts'] or \
                    'retentionHours' in contents['Opts']:
                msg = ('create schedule failed, error is : setting '
                       'expirationHours or retentionHours for docker base '
                       'snapshot is not allowed while creating a schedule')
                LOG.error(msg)
                response = json.dumps({'Err': msg})
                return response

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
                           'passed and please provide max 15 letter prefix '
                           'for the scheduled snapshot names ')
                    LOG.error(msg)
                    response = json.dumps({'Err': msg})
                    return response
                if ('scheduleName' in contents['Opts'] and
                        contents['Opts']['scheduleName'] == ""):
                    msg = ('Please make sure that valid schedule name is '
                           'passed ')
                    LOG.error(msg)
                    response = json.dumps({'Err': msg})
                    return response
                if ('snapshotPrefix' in contents['Opts'] and
                        contents['Opts']['snapshotPrefix'] == ""):
                    msg = ('Please provide a 3 letter prefix for scheduled '
                           'snapshot names ')
                    LOG.error(msg)
                    response = json.dumps({'Err': msg})
                    return response
                schedName = str(contents['Opts']['scheduleName'])
                if schedName == "auto":
                    schedName = self.generate_schedule_with_timestamp()

                snapPrefix = str(contents['Opts']['snapshotPrefix'])

                schedNameLength = len(schedName)
                snapPrefixLength = len(snapPrefix)
                if schedNameLength > 31 or snapPrefixLength > 15:
                    msg = ('Please provide a schedlueName with max 31 '
                           'characters and snapshotPrefix with max '
                           'length of 15 characters')
                    LOG.error(msg)
                    response = json.dumps({'Err': msg})
                    return response
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

    def generate_schedule_with_timestamp(self):
        current_time = datetime.datetime.now()
        current_time_str = str(current_time)
        space_replaced = current_time_str.replace(' ', '_')
        colon_replaced = space_replaced.replace(':', '_')
        hypen_replaced = colon_replaced.replace('-', '_')
        scheduleNameGenerated = hypen_replaced
        LOG.info(' Schedule Name auto generated is %s' % scheduleNameGenerated)
        return scheduleNameGenerated

    @on_exception(expo, RateLimitException, max_tries=8)
    @limits(calls=25, period=30)
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

        mount_id = contents['ID']

        try:
            return self._req_router.route_mount_request(volname, mount_id)
        except exception.EtcdMetadataNotFound:
            pass

        if self.orchestrator:
            try:
                return self.orchestrator.mount_volume(volname,
                                                      vol_mount,
                                                      mount_id)
            except Exception as ex:
                return json.dumps({'Err': six.text_type(ex)})

        return json.dumps({"Err": "ERROR: Cannot mount volume '%s'. "
                                  "Volume driver is not configured" %
                                  volname})

    @app.route("/VolumeDriver.Path", methods=["POST"])
    def volumedriver_path(self, name):
        """
        Return the path of a locally mounted volume if possible.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']

        try:
            return self._req_router.route_get_path_request(volname)
        except exception.EtcdMetadataNotFound:
            pass

        if self.orchestrator:
            return self.orchestrator.get_path(volname)

        return json.dumps({u"Err": '', u"Mountpoint": ''})

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

        # Check if share exists by this name. If so return its details
        # else allow volume driver to process the request
        try:
            return self._req_router.get_object_details(volname)
        except exception.EtcdMetadataNotFound:
            pass

        if self.orchestrator:
            return self.orchestrator.get_volume_snap_details(volname,
                                                             snapname,
                                                             qualified_name)
        return json.dumps({u"Err": '', u"Volume": ''})

    @app.route("/VolumeDriver.List", methods=["POST"])
    def volumedriver_list(self, body):
        """
        Return a list of all volumes.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        share_list = self._req_router.list_objects()

        volume_list = []
        if self.orchestrator:
            volume_list = self.orchestrator.volumedriver_list()

        final_list = share_list + volume_list
        if not final_list:
            return json.dumps({u"Err": ''})

        return json.dumps({u"Err": '', u"Volumes": final_list})
