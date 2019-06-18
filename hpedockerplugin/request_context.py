import abc
import json
import re
import six
from collections import OrderedDict

from oslo_log import log as logging

import hpedockerplugin.exception as exception
from hpedockerplugin.hpe import volume
from hpedockerplugin.hpe import share

LOG = logging.getLogger(__name__)


class RequestContextBuilderFactory(object):
    def __init__(self, all_configs):
        self._all_configs = all_configs

        # if 'block' in all_configs:
        #     block_configs = all_configs['block']
        #     backend_configs = block_configs[1]
        #     self._vol_req_ctxt_creator = VolumeRequestContextBuilder(
        #         backend_configs)
        # else:
        #     self._vol_req_ctxt_creator = NullRequestContextBuilder(
        #         "ERROR: Volume driver not enabled. Please provide hpe.conf "
        #         "file to enable it")

        if 'file' in all_configs:
            file_configs = all_configs['file']
            f_backend_configs = file_configs[1]
            self._file_req_ctxt_builder = FileRequestContextBuilder(
                f_backend_configs)
        else:
            self._file_req_ctxt_builder = NullRequestContextBuilder(
                "ERROR: File driver not enabled. Please provide hpe_file.conf "
                "file to enable it")

    def get_request_context_builder(self):
        return self._file_req_ctxt_builder


class NullRequestContextBuilder(object):
    def __init__(self, msg):
        self._msg = msg

    def build_request_context(self, contents, def_backend_name):
        raise exception.InvalidInput(self._msg)


class RequestContextBuilder(object):
    def __init__(self, backend_configs):
        self._backend_configs = backend_configs

    def build_request_context(self, contents, def_backend_name):
        LOG.info("build_request_context: Entering...")
        self._validate_name(contents['Name'])

        req_ctxt_map = self._get_build_req_ctxt_map()

        if 'Opts' in contents and contents['Opts']:
            # self._validate_mutually_exclusive_ops(contents)
            self._validate_dependent_opts(contents)

            for op_name, req_ctxt_creator in req_ctxt_map.items():
                op_name = op_name.split(',')
                found = not (set(op_name) - set(contents['Opts'].keys()))
                if found:
                    return req_ctxt_creator(contents, def_backend_name)
        return self._default_req_ctxt_creator(contents)

    @staticmethod
    def _validate_name(vol_name):
        is_valid_name = re.match("^[A-Za-z0-9]+[A-Za-z0-9_-]+$", vol_name)
        if not is_valid_name:
            msg = 'Invalid volume name: %s is passed.' % vol_name
            raise exception.InvalidInput(reason=msg)

    @staticmethod
    def _get_int_option(options, option_name, default_val):
        opt = options.get(option_name)
        if opt and opt != '':
            try:
                opt = int(opt)
            except ValueError as ex:
                msg = "ERROR: Invalid value '%s' specified for '%s' option. " \
                      "Please specify an integer value." % (opt, option_name)
                LOG.error(msg)
                raise exception.InvalidInput(msg)
        else:
            opt = default_val
        return opt

    # This method does the following:
    # 1. Option specified
    #  - Some value:
    #    -- return if valid value else exception
    #  - Blank value:
    #    -- Return default if provided
    #       ELSE
    #    -- Throw exception if value_unset_exception is set
    # 2. Option NOT specified
    #   - Return default value
    @staticmethod
    def _get_str_option(options, option_name, default_val, valid_values=None,
                        value_unset_exception=False):
        opt = options.get(option_name)
        if opt:
            if opt != '':
                opt = str(opt)
                if valid_values and opt.lower() not in valid_values:
                    msg = "ERROR: Invalid value '%s' specified for '%s'" \
                          "option. Valid values are: %s" %\
                          (opt, option_name, valid_values)
                    LOG.error(msg)
                    raise exception.InvalidInput(msg)

                return opt

            if default_val:
                return default_val

            if value_unset_exception:
                return json.dumps({
                    'Err': "Value not set for option: %s" % opt
                })
        return default_val

    def _validate_dependent_opts(self, contents):
        pass

    # To be implemented by derived class
    @abc.abstractmethod
    def _get_build_req_ctxt_map(self):
        pass

    def _default_req_ctxt_creator(self, contents):
        pass

    @staticmethod
    def _validate_mutually_exclusive_ops(contents):
        mutually_exclusive_ops = ['virtualCopyOf', 'cloneOf', 'importVol',
                                  'replicationGroup']
        if 'Opts' in contents and contents['Opts']:
            received_opts = contents.get('Opts').keys()
            diff = set(mutually_exclusive_ops) - set(received_opts)
            if len(diff) < len(mutually_exclusive_ops) - 1:
                mutually_exclusive_ops.sort()
                msg = "Operations %s are mutually exclusive and cannot be " \
                      "specified together. Please check help for usage." % \
                      mutually_exclusive_ops
                raise exception.InvalidInput(reason=msg)

    @staticmethod
    def _check_valid_fsMode_string(value):
        valid_type = ['A', 'D', 'U', 'L']
        valid_flag = ['f', 'd', 'p', 'i', 'S', 'F', 'g']
        valid_perm1 = ['r', 'w', 'a', 'x', 'd', 'D', 't', 'T']
        valid_perm2 = ['n', 'N', 'c', 'C', 'o', 'y']
        valid_perm = valid_perm1 + valid_perm2
        type_flag_perm = value.split(':')
        if len(type_flag_perm) != 3:
            msg = "Incorrect value passed , please check correct "\
                  "format and values to be passed in help"
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        vtype = type_flag_perm[0]
        if vtype not in valid_type:
            msg = "Incorrect value passed for type of a mode, please check "\
                  "correct format and values to be passed."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        passed_vflag_len = len(list(type_flag_perm[1]))
        vflag = list(set(list(type_flag_perm[1])))
        if len(vflag) < passed_vflag_len:
            msg = "Duplicate characters for given flag are passed. "\
                  "Please correct the passed flag characters for fsMode."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        if set(vflag) - set(valid_flag):
            msg = "Invalid flag passed for the fsMode. Please "\
                  "pass the correct flag characters"
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        passed_vperm_len = len(list(type_flag_perm[2]))
        vperm = list(set(list(type_flag_perm[2])))
        if len(vperm) < passed_vperm_len:
            msg = "Duplicate characters for given permission are passed. "\
                  "Please correct the passed permissions for fsMode."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        if set(vperm) - set(valid_perm):
            msg = "Invalid characters for the permissions of fsMode are "\
                  "passed. Please remove the invalid characters."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        return True

    def _check_is_valid_acl_string(self, fsMode):
        fsMode_list = fsMode.split(',')
        if len(fsMode_list) != 3:
            msg = "Passed acl string is not valid. "\
                  "Pass correct acl string."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        for value in fsMode_list:
            self._check_valid_fsMode_string(value)
        return True

    @staticmethod
    def _is_valid_octal_num(fsMode):
        return re.match('^0[0-7]{3}$', fsMode)

    def _validate_fsMode(self, fsMode):
        is_valid_fs_mode = True
        if ':' in fsMode:
            is_valid_fs_mode = self._check_is_valid_acl_string(fsMode)
        else:
            is_valid_fs_mode = self._is_valid_octal_num(fsMode)
        if not is_valid_fs_mode:
            msg = "Invalid value passed for the fsMode."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)

    @staticmethod
    def _validate_fsOwner(fsOwner):
        fsOwner_list = fsOwner.split(':')
        if len(fsOwner_list) != 2:
            msg = "Invalid value specified for fsOwner Option."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)
        try:
            for val in fsOwner_list:
                int(val)
        except ValueError as ex:
            msg = "Please provide correct fsowner inforamtion. You have "\
                  "passed non integer values."
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)

    @staticmethod
    def _validate_opts(operation, contents, valid_opts, mandatory_opts=None):
        LOG.info("Validating options for operation '%s'" % operation)
        if 'Opts' in contents and contents['Opts']:
            received_opts = contents.get('Opts').keys()

            if mandatory_opts:
                diff = set(mandatory_opts) - set(received_opts)
                if diff:
                    # Print options in sorted manner
                    mandatory_opts.sort()
                    msg = "One or more mandatory options %s are missing " \
                          "for operation %s" % (mandatory_opts, operation)
                    LOG.error(msg)
                    raise exception.InvalidInput(reason=msg)

            diff = set(received_opts) - set(valid_opts)
            if diff:
                diff = list(diff)
                diff.sort()
                msg = "Invalid option(s) %s specified for operation %s. " \
                      "Please check help for usage." % \
                      (diff, operation)
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)


class FileRequestContextBuilder(RequestContextBuilder):
    def __init__(self, backend_configs):
        super(FileRequestContextBuilder, self).__init__(backend_configs)

    def _get_build_req_ctxt_map(self):
        build_req_ctxt_map = OrderedDict()
        # If share-dir is specified, file-store MUST be specified
        build_req_ctxt_map['filePersona,help'] = self._create_help_req_ctxt
        build_req_ctxt_map['filePersona'] = \
            self._create_share_req_ctxt
        # build_req_ctxt_map['persona,cpg'] = \
        #     self._create_share_req_ctxt
        # build_req_ctxt_map['persona,cpg,size'] = \
        #     self._create_share_req_ctxt
        # build_req_ctxt_map['persona,cpg,size,fpg_name'] = \
        #     self._create_share_req_ctxt
        # build_req_ctxt_map['virtualCopyOf,shareName'] = \
        #     self._create_snap_req_ctxt
        # build_req_ctxt_map['updateShare'] = \
        #     self._create_update_req_ctxt
        return build_req_ctxt_map

    def _create_share_req_params(self, name, options, def_backend_name):
        LOG.info("_create_share_req_params: Entering...")
        # import pdb
        # pdb.set_trace()
        backend = self._get_str_option(options, 'backend', def_backend_name)

        if backend == 'DEFAULT_BLOCK':
            msg = 'Backend DEFAULT_BLOCK is reserved for Block ' \
                  'operations. Cannot specify it for File operations'
            LOG.error(msg)
            raise exception.InvalidInput(msg)

        config = self._backend_configs.get(backend)
        if not config:
            raise exception.InvalidInput(
                'ERROR: Backend %s is not configured for File Persona'
                % backend
            )
        cpg = self._get_str_option(options, 'cpg', config.hpe3par_cpg[0])
        fpg = self._get_str_option(options, 'fpg', None)
        fsMode = self._get_str_option(options, 'fsMode', None)
        fsOwner = self._get_str_option(options, 'fsOwner', None)
        if fsMode:
            self._validate_fsMode(fsMode)

        if fsOwner:
            self._validate_fsOwner(fsOwner)

        size_gib = self._get_int_option(options, 'size', 1024)
        # Default share size or quota in MiB which is 1TiB
        size = size_gib * 1024

        fpg_size_gib = int(config.hpe3par_default_fpg_size) * 1024

        if size_gib > fpg_size_gib:
            raise exception.InvalidInput(
                "ERROR: Share size cannot be greater than the FPG size. "
                "Either specify hpe3par_default_fpg_size >= %s GiB or "
                "specify option '-o size' < %s GiB"
                % (size_gib, fpg_size_gib))

        # TODO: This check would be required when VFS needs to be created.
        # NOT HERE
        # if not ip_subnet and not config.hpe3par_ip_pool:
        #     raise exception.InvalidInput(
        #         "ERROR: Unable to create share as neither 'ipSubnet' "
        #         "option specified not IP address pool hpe3par_ip_pool "
        #         "configured in configuration file specified")

        readonly_str = self._get_str_option(options, 'readonly', 'false')
        readonly = str.lower(readonly_str)
        if readonly == 'true':
            readonly = True
        elif readonly == 'false':
            readonly = False
        else:
            raise exception.InvalidInput(
                'ERROR: Invalid value "%s" supplied for "readonly" option. '
                'Valid values are case insensitive ["true", "false"]'
                % readonly_str)

        nfs_options = self._get_str_option(options, 'nfsOptions', None)
        comment = self._get_str_option(options, 'comment', None)

        share_details = share.create_metadata(backend, cpg, fpg, name, size,
                                              readonly=readonly,
                                              nfs_options=nfs_options,
                                              comment=comment, fsMode=fsMode,
                                              fsOwner=fsOwner)
        LOG.info("_create_share_req_params: %s" % share_details)
        return share_details

    def _create_share_req_ctxt(self, contents, def_backend_name):
        LOG.info("_create_share_req_ctxt: Entering...")
        valid_opts = ('backend', 'filePersona', 'cpg', 'fpg',
                      'size', 'mountConflictDelay', 'fsMode', 'fsOwner')
        mandatory_opts = ('filePersona',)
        self._validate_opts("create share", contents, valid_opts,
                            mandatory_opts)
        share_args = self._create_share_req_params(contents['Name'],
                                                   contents['Opts'],
                                                   def_backend_name)
        ctxt = {'orchestrator': 'file',
                'operation': 'create_share',
                'kwargs': share_args}
        LOG.info("_create_share_req_ctxt: Exiting: %s" % ctxt)
        return ctxt

    def _create_help_req_ctxt(self, contents, def_backend_name):
        LOG.info("_create_help_req_ctxt: Entering...")
        valid_opts = ('filePersona', 'help', 'mountConflictDelay')
        self._validate_opts("create help content for share", contents,
                            valid_opts, mandatory_opts=None)
        options = contents['Opts']
        if options:
            value = self._get_str_option(options, 'help', None)
            if not value:
                return {
                    'orchestrator': 'file',
                    'operation': 'create_share_help',
                    'kwargs': {}
                }

            if value == 'backends':
                return {
                    'orchestrator': 'file',
                    'operation': 'get_backends_status',
                    'kwargs': {}
                }
            else:
                raise exception.InvalidInput(
                    "ERROR: Invalid value %s for option 'help' specified."
                    % value)
        LOG.info("_create_help_req_ctxt: Exiting...")

    def _create_snap_req_ctxt(self, contents):
        pass

    def _create_update_req_ctxt(self, contents):
        pass


# TODO: This is work in progress - can be taken up later if agreed upon
class VolumeRequestContextBuilder(RequestContextBuilder):
    def __init__(self, backend_configs):
        super(VolumeRequestContextBuilder, self).__init__(backend_configs)

    def _get_build_req_ctxt_map(self):
        build_req_ctxt_map = OrderedDict()
        build_req_ctxt_map['virtualCopyOf,scheduleName'] = \
            self._create_snap_schedule_req_ctxt,
        build_req_ctxt_map['virtualCopyOf,scheduleFrequency'] = \
            self._create_snap_schedule_req_ctxt
        build_req_ctxt_map['virtualCopyOf,snaphotPrefix'] = \
            self._create_snap_schedule_req_ctxt
        build_req_ctxt_map['virtualCopyOf'] = \
            self._create_snap_req_ctxt
        build_req_ctxt_map['cloneOf'] = \
            self._create_clone_req_ctxt
        build_req_ctxt_map['importVol'] = \
            self._create_import_vol_req_ctxt
        build_req_ctxt_map['replicationGroup'] = \
            self._create_rcg_req_ctxt
        build_req_ctxt_map['help'] = self._create_help_req_ctxt
        return build_req_ctxt_map

    def _default_req_ctxt_creator(self, contents):
        return self._create_vol_create_req_ctxt(contents)

    @staticmethod
    def _validate_mutually_exclusive_ops(contents):
        mutually_exclusive_ops = ['virtualCopyOf', 'cloneOf', 'importVol',
                                  'replicationGroup']
        if 'Opts' in contents and contents['Opts']:
            received_opts = contents.get('Opts').keys()
            diff = set(mutually_exclusive_ops) - set(received_opts)
            if len(diff) < len(mutually_exclusive_ops) - 1:
                mutually_exclusive_ops.sort()
                msg = "Operations %s are mutually exclusive and cannot be " \
                      "specified together. Please check help for usage." % \
                      mutually_exclusive_ops
                raise exception.InvalidInput(reason=msg)

    @staticmethod
    def _validate_opts(operation, contents, valid_opts, mandatory_opts=None):
        if 'Opts' in contents and contents['Opts']:
            received_opts = contents.get('Opts').keys()

            if mandatory_opts:
                diff = set(mandatory_opts) - set(received_opts)
                if diff:
                    # Print options in sorted manner
                    mandatory_opts.sort()
                    msg = "One or more mandatory options %s are missing " \
                          "for operation %s" % (mandatory_opts, operation)
                    raise exception.InvalidInput(reason=msg)

            diff = set(received_opts) - set(valid_opts)
            if diff:
                diff = list(diff)
                diff.sort()
                msg = "Invalid option(s) %s specified for operation %s. " \
                      "Please check help for usage." % \
                      (diff, operation)
                raise exception.InvalidInput(reason=msg)

    def _create_vol_create_req_ctxt(self, contents):
        valid_opts = ['compression', 'size', 'provisioning',
                      'flash-cache', 'qos-name', 'fsOwner',
                      'fsMode', 'mountConflictDelay', 'cpg',
                      'snapcpg', 'backend']
        self._validate_opts("create volume", contents, valid_opts)
        return {'operation': 'create_volume',
                '_vol_orchestrator': 'volume'}

    def _create_clone_req_ctxt(self, contents):
        valid_opts = ['cloneOf', 'size', 'cpg', 'snapcpg',
                      'mountConflictDelay']
        self._validate_opts("clone volume", contents, valid_opts)
        return {'operation': 'clone_volume',
                'orchestrator': 'volume'}

    def _create_snap_req_ctxt(self, contents):
        valid_opts = ['virtualCopyOf', 'retentionHours', 'expirationHours',
                      'mountConflictDelay', 'size']
        self._validate_opts("create snapshot", contents, valid_opts)
        return {'operation': 'create_snapshot',
                '_vol_orchestrator': 'volume'}

    def _create_snap_schedule_req_ctxt(self, contents):
        valid_opts = ['virtualCopyOf', 'scheduleFrequency', 'scheduleName',
                      'snapshotPrefix', 'expHrs', 'retHrs',
                      'mountConflictDelay', 'size']
        mandatory_opts = ['scheduleName', 'snapshotPrefix',
                          'scheduleFrequency']
        self._validate_opts("create snapshot schedule", contents,
                            valid_opts, mandatory_opts)
        return {'operation': 'create_snapshot_schedule',
                'orchestrator': 'volume'}

    def _create_import_vol_req_ctxt(self, contents):
        valid_opts = ['importVol', 'backend', 'mountConflictDelay']
        self._validate_opts("import volume", contents, valid_opts)

        # Replication enabled backend cannot be used for volume import
        backend = contents['Opts'].get('backend', 'DEFAULT')
        if backend == '':
            backend = 'DEFAULT'

        try:
            config = self._backend_configs[backend]
        except KeyError:
            backend_names = list(self._backend_configs.keys())
            backend_names.sort()
            msg = "ERROR: Backend '%s' doesn't exist. Available " \
                  "backends are %s. Please use " \
                  "a valid backend name and retry." % \
                  (backend, backend_names)
            raise exception.InvalidInput(reason=msg)

        if config.replication_device:
            msg = "ERROR: Import volume not allowed with replication " \
                  "enabled backend '%s'" % backend
            raise exception.InvalidInput(reason=msg)

        volname = contents['Name']
        existing_ref = str(contents['Opts']['importVol'])
        manage_opts = contents['Opts']
        return {'orchestrator': 'volume',
                'operation': 'import_volume',
                'args': (volname,
                         existing_ref,
                         backend,
                         manage_opts)}

    def _create_rcg_req_ctxt(self, contents):
        valid_opts = ['replicationGroup', 'size', 'provisioning',
                      'backend', 'mountConflictDelay', 'compression']
        self._validate_opts('create replicated volume', contents, valid_opts)

        # It is possible that the user configured replication in hpe.conf
        # but didn't specify any options. In that case too, this operation
        # must fail asking for "replicationGroup" parameter
        # Hence this validation must be done whether "Opts" is there or not
        options = contents['Opts']
        backend = self._get_str_option(options, 'backend', 'DEFAULT')
        create_vol_args = self._get_create_volume_args(options)
        rcg_name = create_vol_args['replicationGroup']
        try:
            self._validate_rcg_params(rcg_name, backend)
        except exception.InvalidInput as ex:
            return json.dumps({u"Err": ex.msg})

        return {'operation': 'create_volume',
                'orchestrator': 'volume',
                'args': create_vol_args}

    def _get_fs_owner(self, options):
        val = self._get_str_option(options, 'fsOwner', None)
        if val:
            fs_owner = val.split(':')
            if len(fs_owner) != 2:
                msg = "Invalid value '%s' specified for fsOwner. Please " \
                      "specify a correct value." % val
                raise exception.InvalidInput(msg)
            return fs_owner
        return None

    def _get_fs_mode(self, options):
        fs_mode_str = self._get_str_option(options, 'fsMode', None)
        if fs_mode_str:
            try:
                int(fs_mode_str)
            except ValueError as ex:
                msg = "Invalid value '%s' specified for fsMode. Please " \
                      "specify an integer value." % fs_mode_str
                raise exception.InvalidInput(msg)

            if fs_mode_str[0] != '0':
                msg = "Invalid value '%s' specified for fsMode. Please " \
                      "specify an octal value." % fs_mode_str
                raise exception.InvalidInput(msg)

            for mode in fs_mode_str:
                if int(mode) > 7:
                    msg = "Invalid value '%s' specified for fsMode. Please " \
                          "specify an octal value." % fs_mode_str
                    raise exception.InvalidInput(msg)
        return fs_mode_str

    def _get_create_volume_args(self, options):
        ret_args = dict()
        ret_args['size'] = self._get_int_option(
            options, 'size', volume.DEFAULT_SIZE)
        ret_args['provisioning'] = self._get_str_option(
            options, 'provisioning', volume.DEFAULT_PROV,
            ['full', 'thin', 'dedup'])
        ret_args['flash-cache'] = self._get_str_option(
            options, 'flash-cache', volume.DEFAULT_FLASH_CACHE,
            ['true', 'false'])
        ret_args['qos-name'] = self._get_str_option(
            options, 'qos-name', volume.DEFAULT_QOS)
        ret_args['compression'] = self._get_str_option(
            options, 'compression', volume.DEFAULT_COMPRESSION_VAL,
            ['true', 'false'])
        ret_args['fsOwner'] = self._get_fs_owner(options)
        ret_args['fsMode'] = self._get_fs_mode(options)
        ret_args['mountConflictDelay'] = self._get_int_option(
            options, 'mountConflictDelay',
            volume.DEFAULT_MOUNT_CONFLICT_DELAY)
        ret_args['cpg'] = self._get_str_option(options, 'cpg', None)
        ret_args['snapcpg'] = self._get_str_option(options, 'snapcpg', None)
        ret_args['replicationGroup'] = self._get_str_option(
            options, 'replicationGroup', None)

        return ret_args

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
            backend_names = list(self._backend_configs.keys())
            backend_names.sort()

            msg = "'%s' is a replication enabled backend. " \
                  "Request to create replicated volume cannot be fulfilled " \
                  "without specifying 'replicationGroup' option in the " \
                  "request. Please either specify 'replicationGroup' or use " \
                  "a normal backend and execute the request again. List of " \
                  "backends defined in hpe.conf: %s" % (backend_name,
                                                        backend_names)
            raise exception.InvalidInput(reason=msg)

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

    @staticmethod
    def _validate_name(vol_name):
        is_valid_name = re.match("^[A-Za-z0-9]+[A-Za-z0-9_-]+$", vol_name)
        if not is_valid_name:
            msg = 'Invalid volume name: %s is passed.' % vol_name
            raise exception.InvalidInput(reason=msg)
