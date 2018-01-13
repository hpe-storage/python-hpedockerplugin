import uuid

DEFAULT_SIZE = 100
DEFAULT_PROV = "thin"
DEFAULT_FLASH_CACHE = None
DEFAULT_QOS = None
DEFAULT_MOUNT_VOLUME = "True"
DEFAULT_COMPRESSION_VAL = None

QOS_PRIORITY = {1 : 'Low', 2 : 'Normal', 3 : 'High'}

VOL_COMPRESSION_STATE = {1 : 'YES', 2 : 'NO', 3 : 'OFF', 4 : 'NA'}
VOL_DEDUPLICATION_STATE = {1 : 'YES', 2 : 'NO', 3 : 'NA'}
VOL_COPY_TYPE = {1 : 'Base', 2 : 'Physical Copy', 3 : 'Virtual Copy'}
VOL_PROV_TYPE = {1 : 'full', 2 : 'thin', 3 : 'snapshot', 4 : 'peer', 5 : 'unknown', 6 : 'dedup', 7 : 'dds'}

def createvol(name, size=DEFAULT_SIZE, prov=DEFAULT_PROV,
              flash_cache=None, compression_val=None, qos=None, isclone=False):
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
    volume['isclone'] = isclone

    return volume
