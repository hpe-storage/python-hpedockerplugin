import re
from collections import OrderedDict

from oslo_log import log as logging

import hpedockerplugin.exception as exception

LOG = logging.getLogger(__name__)


class RequestValidator(object):

    def __init__(self, backend_configs):
        self._backend_configs = backend_configs

    def validate_request(self, contents):
        self._validate_name(contents['Name'])

        operations_map = OrderedDict()
        operations_map['virtualCopyOf,scheduleName'] = \
            self._validate_snapshot_schedule_opts
        operations_map['virtualCopyOf,scheduleFrequency'] = \
            self._validate_snapshot_schedule_opts
        operations_map['virtualCopyOf,snaphotPrefix'] = \
            self._validate_snapshot_schedule_opts
        operations_map['virtualCopyOf'] = \
            self._validate_snapshot_opts
        operations_map['cloneOf'] = \
            self._validate_clone_opts
        operations_map['importVol'] = \
            self._validate_import_vol_opts
        operations_map['replicationGroup'] = \
            self._validate_rcg_opts
        operations_map['help'] = self._validate_help_opt

        if 'Opts' in contents and contents['Opts']:
            self._validate_mutually_exclusive_ops(contents)

            validated = False
            for op_name, validator in operations_map.items():
                op_name = op_name.split(',')
                found = not (set(op_name) - set(contents['Opts'].keys()))
                if found:
                    validator(contents)
                    validated = True
                    break

            # Validate regular volume options
            if not validated:
                self._validate_create_volume_opts(contents)

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

    def _validate_create_volume_opts(self, contents):
        valid_opts = ['compression', 'size', 'provisioning',
                      'flash-cache', 'qos-name', 'fsOwner',
                      'fsMode', 'mountConflictDelay', 'cpg',
                      'snapcpg', 'backend', 'manager']
        self._validate_opts("create volume", contents, valid_opts)

    def _validate_clone_opts(self, contents):
        valid_opts = ['cloneOf', 'size', 'cpg', 'snapcpg',
                      'mountConflictDelay', 'manager']
        self._validate_opts("clone volume", contents, valid_opts)

    def _validate_snapshot_opts(self, contents):
        valid_opts = ['virtualCopyOf', 'retentionHours', 'expirationHours',
                      'mountConflictDelay', 'size', 'manager']
        self._validate_opts("create snapshot", contents, valid_opts)

    def _validate_snapshot_schedule_opts(self, contents):
        valid_opts = ['virtualCopyOf', 'scheduleFrequency', 'scheduleName',
                      'snapshotPrefix', 'expHrs', 'retHrs',
                      'mountConflictDelay', 'size', 'manager']
        mandatory_opts = ['scheduleName', 'snapshotPrefix',
                          'scheduleFrequency']
        self._validate_opts("create snapshot schedule", contents,
                            valid_opts, mandatory_opts)

    def _validate_import_vol_opts(self, contents):
        valid_opts = ['importVol', 'backend', 'mountConflictDelay',
                      'manager']
        self._validate_opts("import volume", contents, valid_opts)

        # Replication enabled backend cannot be used for volume import
        if 'Opts' in contents and contents['Opts']:
            backend_name = contents['Opts'].get('backend', None)
            if not backend_name:
                backend_name = 'DEFAULT'
            try:
                self._backend_configs[backend_name]
            except KeyError:
                backend_names = list(self._backend_configs.keys())
                backend_names.sort()
                msg = "ERROR: Backend '%s' doesn't exist. Available " \
                      "backends are %s. Please use " \
                      "a valid backend name and retry." % \
                      (backend_name, backend_names)
                raise exception.InvalidInput(reason=msg)

    def _validate_rcg_opts(self, contents):
        valid_opts = ['replicationGroup', 'size', 'provisioning',
                      'backend', 'mountConflictDelay', 'compression',
                      'manager']
        self._validate_opts('create replicated volume', contents, valid_opts)

    def _validate_help_opt(self, contents):
        valid_opts = ['help']
        self._validate_opts('display help', contents, valid_opts)

    @staticmethod
    def _validate_name(vol_name):
        is_valid_name = re.match("^[A-Za-z0-9]+[A-Za-z0-9_-]+$", vol_name)
        if not is_valid_name:
            msg = 'Invalid volume name: %s is passed.' % vol_name
            raise exception.InvalidInput(reason=msg)
