volume = {}
volume['id'] = ''
volume['name'] = ''
volume['host'] = ''
volume['size'] = ''
volume['availability_zone'] = ''
volume['status'] = ''
volume['attach_status'] = ''
volume['display_name'] = ''
volume['volume_id'] = ''
volume['volume_type'] = ''
volume['volume_attachment'] = ''
volume['provisioning'] = ''
volume['flash_cache'] = ''
volume['compression'] = ''


def createvol(name, uuid, size, prov, flash_cache, compression_val):
    volume['id'] = uuid
    volume['name'] = uuid
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
    volume['compression'] = compression_val

    return volume
