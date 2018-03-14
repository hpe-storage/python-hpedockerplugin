import uuid

DEFAULT_SIZE = 100
DEFAULT_PROV = "thin"
DEFAULT_FLASH_CACHE = None
DEFAULT_QOS = None
DEFAULT_MOUNT_VOLUME = "True"
DEFAULT_COMPRESSION_VAL = None
DEFAULT_MOUNT_CONFLICT_DELAY = 30

QOS_PRIORITY = {1: 'Low', 2: 'Normal', 3: 'High'}


def createvol(name, size=DEFAULT_SIZE, prov=DEFAULT_PROV,
              flash_cache=None, compression_val=None, qos=None,
              mount_conflict_delay=DEFAULT_MOUNT_CONFLICT_DELAY):
    volume = {}
    volume['id'] = str(uuid.uuid4())
    volume['name'] = volume['id']
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

    return volume
