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

from oslo_config import cfg
from hpedockerplugin.i18n import _

from sh import iscsiadm

volume_opts = [
    cfg.StrOpt('iscsi_ip_address',
               default='my_ip',
               help='The IP address that the iSCSI daemon is listening on'),
    cfg.PortOpt('iscsi_port',
                default=3260,
                help='The port that the iSCSI daemon is listening on'),
    cfg.BoolOpt('use_chap_auth',
                default=False,
                help='Option to enable/disable CHAP authentication for '
                     'targets.'),
    cfg.StrOpt('chap_username',
               default='',
               help='CHAP user name.'),
    cfg.StrOpt('chap_password',
               default='',
               help='Password for specified CHAP account name.',
               secret=True),
]

# TODO: How do we include san module and register san_opts
# We want to limit the amount of extra stuff we take from
# OpenStack, so just define san_opts here.
san_opts = [
    cfg.StrOpt('san_ip',
               default='',
               help='IP address of SAN controller'),
    cfg.StrOpt('san_login',
               default='admin',
               help='Username for SAN controller'),
    cfg.StrOpt('san_password',
               default='',
               help='Password for SAN controller',
               secret=True),
    cfg.StrOpt('san_private_key',
               default='',
               help='Filename of private key to use for SSH authentication'),
    cfg.PortOpt('san_ssh_port',
                default=22,
                help='SSH port to use with SAN'),
    cfg.IntOpt('ssh_conn_timeout',
               default=30,
               help="SSH connection timeout in seconds"),
]


CONF = cfg.CONF
CONF.register_opts(volume_opts)
CONF.register_opts(san_opts)


def _do_iscsi_discovery(volume, targetip):
    # TODO(justinsb): Deprecate discovery and use stored info
    # NOTE(justinsb): Discovery won't work with CHAP-secured targets (?)

    volume_name = volume['name']

    try:
        out = iscsiadm('iscsiadm', '-m', 'discovery',
                       '-t', 'sendtargets', '-p', targetip)

    except Exception as e:
        print("Error from iscsiadm -m discovery: %s" % (targetip))
        print('exception is : %s' % (e))
        raise

    for target in out.splitlines():
        if (targetip in target and
                volume_name in target):
            return target
    return None


"""
Leveraged _get_iscsi_properties from Cinder driver
Removed encryption and CHAP support for now.
"""


def _get_iscsi_properties(volume, targetip):
    """Gets iscsi configuration

    We ideally get saved information in the volume entity, but fall back
    to discovery if need be. Discovery may be completely removed in future
    The properties are:

    :target_discovered:    boolean indicating whether discovery was used

    :target_iqn:    the IQN of the iSCSI target

    :target_portal:    the portal of the iSCSI target

    :target_lun:    the lun of the iSCSI target

    :volume_id:    the id of the volume (currently used by xen)

    :auth_method:, :auth_username:, :auth_password:

        the authentication details. Right now, either auth_method is not
        present meaning no authentication, or auth_method == `CHAP`
        meaning use CHAP with the specified credentials.

    :access_mode:    the volume access mode allow client used
                     ('rw' or 'ro' currently supported)

    :discard:    boolean indicating if discard is supported

    In some of drivers that support multiple connections (for multipath
    and for single path with failover on connection failure), it returns
    :target_iqns, :target_portals, :target_luns, which contain lists of
    multiple values. The main portal information is also returned in
    :target_iqn, :target_portal, :target_lun for backward compatibility.

    Note that some of drivers don't return :target_portals even if they
    support multipath. Then the connector should use sendtargets discovery
    to find the other portals if it supports multipath.
    """

    properties = {}

    location = volume['provider_location']

    if location:
        # provider_location is the same format as iSCSI discovery output
        properties['target_discovered'] = False
    else:
        location = _do_iscsi_discovery(volume, targetip)

        if not location:
            msg = (_("Could not find iSCSI export for volume %s")
                   % (volume['name']))
            raise msg

        print("ISCSI Discovery: Found %s" % (location))
        properties['target_discovered'] = True

    results = location.split(" ")
    portals = results[0].split(",")[0].split(";")
    iqn = results[1]
    nr_portals = len(portals)

    try:
        lun = int(results[2])
        # TODO: Validate StoreVirtual LUN number is part of location details,
        # after target IP
    except (IndexError, ValueError):
        lun = 0

    if nr_portals > 1:
        properties['target_portals'] = portals
        properties['target_iqns'] = [iqn] * nr_portals
        properties['target_luns'] = [lun] * nr_portals
    properties['target_portal'] = portals[0]
    properties['target_iqn'] = iqn
    properties['target_lun'] = lun

    properties['volume_id'] = volume['id']

    auth = volume['provider_auth']
    if auth:
        (auth_method, auth_username, auth_secret) = auth.split()

        properties['auth_method'] = auth_method
        properties['auth_username'] = auth_username
        properties['auth_password'] = auth_secret

    geometry = volume.get('provider_geometry', None)
    if geometry:
        (physical_block_size, logical_block_size) = geometry.split()
        properties['physical_block_size'] = physical_block_size
        properties['logical_block_size'] = logical_block_size

    encryption_key_id = volume.get('encryption_key_id', None)
    properties['encrypted'] = encryption_key_id is not None

    return properties
