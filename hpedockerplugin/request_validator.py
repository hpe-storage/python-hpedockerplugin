from collections import OrderedDict

from oslo_log import log as logging

import hpedockerplugin.exception as exception

LOG = logging.getLogger(__name__)


def validate_request(contents):
    operations_map = OrderedDict()
    operations_map['virtualCopyOf,scheduleName'] = \
        _validate_snapshot_schedule_opts
    operations_map['virtualCopyOf,scheduleFrequency'] = \
        _validate_snapshot_schedule_opts
    operations_map['virtualCopyOf,snaphotPrefix'] = \
        _validate_snapshot_schedule_opts
    operations_map['virtualCopyOf'] = \
        _validate_snapshot_opts
    operations_map['cloneOf'] = \
        _validate_clone_opts
    operations_map['importVol'] = \
        _validate_import_vol_opts
    operations_map['replicationGroup'] = \
        _validate_rcg_opts

    if 'Opts' in contents:
        _validate_mutually_exclusive_ops(contents)

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
            validate_create_volume_opts(contents)


def _validate_mutually_exclusive_ops(contents):
    mutually_exclusive_ops = ['virtualCopyOf', 'cloneOf', 'importVol',
                              'replicationGroup']
    if 'Opts' in contents:
        received_opts = contents.get('Opts').keys()
        diff = set(mutually_exclusive_ops) - set(received_opts)
        if len(diff) < len(mutually_exclusive_ops) - 1:
            mutually_exclusive_ops.sort()
            msg = "Operations %s are mutually exclusive and cannot " \
                  "be specified together. Please check help for usage." % \
                  mutually_exclusive_ops
            raise exception.InvalidInput(reason=msg)


def _validate_opts(operation, contents, valid_opts, mandatory_opts=None):
    if 'Opts' in contents:
        received_opts = contents.get('Opts').keys()

        if mandatory_opts:
            diff = set(mandatory_opts) - set(received_opts)
            if diff:
                # Print options in sorted manner
                mandatory_opts.sort()
                msg = "One or more mandatory options %s are missing for " \
                      "operation %s" % (mandatory_opts, operation)
                raise exception.InvalidInput(reason=msg)

        diff = set(received_opts) - set(valid_opts)
        if diff:
            diff = list(diff)
            diff.sort()
            msg = "Invalid option(s) %s specified for operation %s. " \
                  "Please check help for usage." % \
                  (diff, operation)
            raise exception.InvalidInput(reason=msg)


def validate_create_volume_opts(contents):
    valid_opts = ['compression', 'size', 'provisioning',
                  'flash-cache', 'qos-name', 'fsOwner',
                  'fsMode', 'mountConflictDelay', 'cpg',
                  'snapcpg', 'backend']
    _validate_opts("create volume", contents, valid_opts)


def _validate_clone_opts(contents):
    valid_opts = ['cloneOf', 'size', 'cpg', 'snapcpg']
    _validate_opts("clone volume", contents, valid_opts)


def _validate_snapshot_opts(contents):
    valid_opts = ['virtualCopyOf', 'retentionHours', 'expirationHours']
    _validate_opts("create snapshot", contents, valid_opts)


def _validate_snapshot_schedule_opts(contents):
    valid_opts = ['virtualCopyOf', 'retentionHours', 'scheduleFrequency',
                  'scheduleName', 'snapshotPrefix', 'expHrs', 'retHrs']
    mandatory_opts = ['scheduleName', 'snapshotPrefix', 'scheduleFrequency']
    _validate_opts("create snapshot schedule", contents,
                   valid_opts, mandatory_opts)


def _validate_import_vol_opts(contents):
    valid_opts = ['importVol']
    _validate_opts("import volume", contents, valid_opts)


def _validate_rcg_opts(contents):
    valid_opts = ['replicationGroup', 'size', 'provisioning',
                  'backend', 'mountConflictDelay']
    _validate_opts('create replicated volume', contents, valid_opts)
