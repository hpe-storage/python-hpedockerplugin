# Copyright (c) 2012 OpenStack Foundation
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

"""Volume-related Utilities and helpers."""

import six
import string
import uuid

from Crypto.Cipher import AES
from Crypto.Random import random

from oslo_log import log as logging
from oslo_serialization import base64

LOG = logging.getLogger(__name__)

# Default symbols to use for passwords. Avoids visually confusing characters.
# ~6 bits per symbol
DEFAULT_PASSWORD_SYMBOLS = ('23456789',  # Removed: 0,1
                            'ABCDEFGHJKLMNPQRSTUVWXYZ',   # Removed: I, O
                            'abcdefghijkmnopqrstuvwxyz')  # Removed: l


def generate_password(length=16, symbolgroups=DEFAULT_PASSWORD_SYMBOLS):
    """Generate a random password from the supplied symbol groups.
    At least one symbol from each group will be included. Unpredictable
    results if length is less than the number of symbol groups.
    Believed to be reasonably secure (with a reasonable password length!)
    """
    # NOTE(jerdfelt): Some password policies require at least one character
    # from each group of symbols, so start off with one random character
    # from each symbol group
    password = [random.choice(s) for s in symbolgroups]
    # If length < len(symbolgroups), the leading characters will only
    # be from the first length groups. Try our best to not be predictable
    # by shuffling and then truncating.
    random.shuffle(password)
    password = password[:length]
    length -= len(password)

    # then fill with random characters from all symbol groups
    symbols = ''.join(symbolgroups)
    password.extend([random.choice(symbols) for _i in range(length)])

    # finally shuffle to ensure first x characters aren't from a
    # predictable group
    random.shuffle(password)

    return ''.join(password)


def _encode_name(name):
    uuid_str = name.replace("-", "")
    vol_uuid = uuid.UUID('urn:uuid:%s' % uuid_str)
    vol_encoded = base64.encode_as_text(vol_uuid.bytes)

    # 3par doesn't allow +, nor /
    vol_encoded = vol_encoded.replace('+', '.')
    vol_encoded = vol_encoded.replace('/', '-')
    # strip off the == as 3par doesn't like those.
    vol_encoded = vol_encoded.replace('=', '')
    return vol_encoded


def _decode_name(name):

    name = name.replace('dcv-', '')
    name = name.replace('.', '+')
    name = name.replace('-', '/')
    name = name + "=="

    vol_decoded = uuid.UUID(bytes=base64.decode_as_bytes(name))
    return str(vol_decoded)


def get_vol_id(volume_name):
    """Get vol_id from 3PAR volume_name
       get 'acd437e7-f1bb-4e44-bfee-ff86510b900e'
       from 'dcv-rNQ35-G7TkS-7v.GUQuQDg'
       vol_id was created by uuid.uuid4()
    """
    volume_id = _decode_name(volume_name)
    return volume_id


def get_3par_vol_name(volume_id):
    """Get converted 3PAR volume name.

    Converts the openstack volume id from
    ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
    to
    dcv-7P.DD5jLTPWF7tcwnMF80g

    We convert the 128 bits of the uuid into a 24character long
    base64 encoded string to ensure we don't exceed the maximum
    allowed 31 character name limit on 3Par

    We strip the padding '=' and replace + with .
    and / with -
    """
    volume_name = _encode_name(volume_id)
    return "dcv-%s" % volume_name


def get_3par_name(volume_id, is_snap):
    volume_name = _encode_name(volume_id)
    if is_snap:
        return "dcs-%s" % volume_name
    else:
        return "dcv-%s" % volume_name


def get_3par_snap_name(snapshot_id):
    """Get converted 3PAR snapshot name.

    Converts the docker snapshot id from
    ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
    to
    dcs-7P.DD5jLTPWF7tcwnMF80g

    We convert the 128 bits of the uuid into a 24character long
    base64 encoded string to ensure we don't exceed the maximum
    allowed 31 character name limit on 3Par

    We strip the padding '=' and replace + with .
    and / with -
    """
    snapshot_name = _encode_name(snapshot_id)
    return "dcs-%s" % snapshot_name


def get_3par_vvs_name(volume_id):
    vvs_name = _encode_name(volume_id)
    return "vvs-%s" % vvs_name


def get_3par_rcg_name(id):
    rcg_name = _encode_name(id)
    return ("rcg-%s" % rcg_name)[:22]


def get_remote3par_rcg_name(id, array_id):
    return get_3par_rcg_name(id) + ".r" + (
        six.text_type(array_id))


class PasswordDecryptor(object):
    def __init__(self, backend_name, etcd):
        self._backend_name = backend_name
        self._etcd = etcd
        self._passphrase = self._get_passphrase()

    def _get_passphrase(self):
        try:
            passphrase = self._etcd.get_backend_key(self._backend_name)
            return passphrase
        except Exception as ex:
            LOG.info('Exception occurred %s ' % six.text_type(ex))
            LOG.info("Using PLAIN TEXT for backend '%s'" % self._backend_name)
        return None

    def decrypt_password(self, config):
        if self._passphrase and config:
            passphrase = self._key_check(self._passphrase)
            config.hpe3par_password = \
                self._decrypt(config.hpe3par_password, passphrase)
            config.san_password =  \
                self._decrypt(config.san_password, passphrase)

    def _key_check(self, key):
        KEY_LEN = len(key)
        padding_string = string.ascii_letters

        KEY = key
        if KEY_LEN < 16:
            KEY = key + padding_string[:16 - KEY_LEN]

        elif KEY_LEN > 16 and KEY_LEN < 24:
            KEY = key + padding_string[:24 - KEY_LEN]

        elif KEY_LEN > 24 and KEY_LEN < 32:
            KEY = key + padding_string[:32 - KEY_LEN]

        elif KEY_LEN > 32:
            KEY = key[:32]

        return KEY

    def _decrypt(self, encrypted, passphrase):
        aes = AES.new(passphrase, AES.MODE_CFB, '1234567812345678')
        decrypt_pass = aes.decrypt(base64.b64decode(encrypted))
        return decrypt_pass.decode('utf-8')
