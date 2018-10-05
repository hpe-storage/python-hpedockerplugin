import uuid
from hpedockerplugin.hpe import utils

DEFAULT_SIZE = 100
DEFAULT_PROV = "thin"
DEFAULT_FLASH_CACHE = None
DEFAULT_QOS = None
DEFAULT_MOUNT_VOLUME = "True"
DEFAULT_COMPRESSION_VAL = None
DEFAULT_MOUNT_CONFLICT_DELAY = 30
DEFAULT_TO_SNAP_TYPE = False
DEFAULT_SCHEDULE = False

QOS_PRIORITY = {1: 'Low', 2: 'Normal', 3: 'High'}
RCG_ROLE = {1: 'Primary', 2: 'Secondary'}
PROVISIONING = {1: 'full', 2: 'thin', 6: 'dedup'}
COMPRESSION = {1: 'true'}
COPYTYPE = {1: 'base', 2: 'physical', 3: 'virtual'}


def createvol(name, size=DEFAULT_SIZE, prov=DEFAULT_PROV,
              flash_cache=None, compression_val=None, qos=None,
              mount_conflict_delay=DEFAULT_MOUNT_CONFLICT_DELAY,
              is_snap=DEFAULT_TO_SNAP_TYPE, cpg=None, snap_cpg=None,
              has_schedule=DEFAULT_SCHEDULE, current_backend='DEFAULT',
              rcg_info=None):
    volume = {}
    volume['id'] = str(uuid.uuid4())
    volume['name'] = volume['id']
    volume['3par_vol_name'] = utils.get_3par_name(volume['id'],
                                                  is_snap)
    volume['host'] = ''
    volume['size'] = size
    volume['availability_zone'] = ''
    volume['status'] = ''
    volume['attach_status'] = ''
    volume['display_name'] = name
    volume['volume_id'] = ''
    volume['volume_type'] = None
    volume['volume_attachment'] = None
    volume['provider_location'] = None
    volume['path_info'] = None
    volume['provisioning'] = prov
    volume['flash_cache'] = flash_cache
    volume['qos_name'] = qos
    volume['compression'] = compression_val
    volume['snapshots'] = []
    volume['mount_conflict_delay'] = mount_conflict_delay
    volume['is_snap'] = is_snap
    volume['backend'] = current_backend
    volume['snap_metadata'] = None
    volume['cpg'] = cpg
    volume['snap_cpg'] = snap_cpg
    volume['has_schedule'] = has_schedule
    volume['rcg_info'] = rcg_info
    return volume
