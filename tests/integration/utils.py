#    (c) Copyright 2012-2016 Hewlett Packard Enterprise Development LP
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import random
import uuid
from oslo_serialization import base64

def encode_name(name):
    uuid_str = name.replace("-", "")
    vol_uuid = uuid.UUID('urn:uuid:%s' % uuid_str)
    vol_encoded = base64.encode_as_text(vol_uuid.bytes)

    # 3par doesn't allow +, nor /
    vol_encoded = vol_encoded.replace('+', '.')
    vol_encoded = vol_encoded.replace('/', '-')
    # strip off the == as 3par doesn't like those.
    vol_encoded = vol_encoded.replace('=', '')
    return vol_encoded


def get_3par_vol_name(volume_id):
    """Get converted 3PAR volume name.

    Converts the openstack volume id from
    ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
    to
    osv-7P.DD5jLTPWF7tcwnMF80g

    We convert the 128 bits of the uuid into a 24character long
    base64 encoded string to ensure we don't exceed the maximum
    allowed 31 character name limit on 3Par

    We strip the padding '=' and replace + with .
    and / with -
    """
    volume_name = encode_name(volume_id)
    return "dcv-%s" % volume_name


def get_3par_snapshot_name(snapshot_id):
    """Get converted 3PAR snapshot name.

     Converts the openstack snapshot id from
     ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
     to
     oss-7P.DD5jLTPWF7tcwnMF80g

     We convert the 128 bits of the uuid into a 24character long
     base64 encoded string to ensure we don't exceed the maximum
     allowed 31 character name limit on 3Par

     We strip the padding '=' and replace + with .
     and / with -
     """
    snapshot_name = encode_name(snapshot_id)
    return "dcs-%s" % snapshot_name


def get_3par_unmanaged_vol_name(volume_id):
    """Get converted 3PAR volume name.

    Converts the openstack volume id from
    ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
    to
    osv-7P.DD5jLTPWF7tcwnMF80g

    We convert the 128 bits of the uuid into a 24character long
    base64 encoded string to ensure we don't exceed the maximum
    allowed 31 character name limit on 3Par

    We strip the padding '=' and replace + with .
    and / with -
    """
    volume_name = encode_name(volume_id)
    return "unm-%s" % volume_name


def get_3par_unmanaged_ss_name(snapshot_id):
    """Get converted 3PAR snapshot name.

     Converts the openstack snapshot id from
     ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
     to
     oss-7P.DD5jLTPWF7tcwnMF80g

     We convert the 128 bits of the uuid into a 24character long
     base64 encoded string to ensure we don't exceed the maximum
     allowed 31 character name limit on 3Par

     We strip the padding '=' and replace + with .
     and / with -
     """
    snapshot_name = encode_name(snapshot_id)
    return "ums-%s" % snapshot_name


def get_3par_vvset_name(id):
    """Get converted 3PAR VVSET name.

     Converts the openstack snapshot id from
     ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
     to
     oss-7P.DD5jLTPWF7tcwnMF80g

     We convert the 128 bits of the uuid into a 24character long
     base64 encoded string to ensure we don't exceed the maximum
     allowed 31 character name limit on 3Par

     We strip the padding '=' and replace + with .
     and / with -
     """
    vvset_name = encode_name(id)
    return "vvs-%s" % vvset_name


def make_unique(name):
    """
    Suffixes input string str with '_' and a random number
    between 100000 and 999999
    :param str: 
    :return: 
    """
    return '_'.join([name, str(random.randint(100000, 999999))])
