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

import json
import math
import uuid

from oslo_utils import importutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_service import loopingcall
from oslo_utils import units

from hpedockerplugin import exception
from hpedockerplugin.i18n import _, _LE, _LI, _LW

hpe3parclient = importutils.try_import("hpe3parclient")
if hpe3parclient:
    from hpe3parclient import client
    from hpe3parclient import exceptions as hpeexceptions

from hpedockerplugin.hpe import utils

LOG = logging.getLogger(__name__)

MIN_CLIENT_VERSION = '4.0.0'
DEDUP_API_VERSION = 30201120
FLASH_CACHE_API_VERSION = 30201200
COMPRESSION_API_VERSION = 30301215

hpe3par_opts = [
    cfg.StrOpt('hpe3par_api_url',
               default='',
               help="3PAR WSAPI Server Url like "
                    "https://<3par ip>:8080/api/v1",
               deprecated_name='hp3par_api_url'),
    cfg.StrOpt('hpe3par_username',
               default='',
               help="3PAR username with the 'edit' role",
               deprecated_name='hp3par_username'),
    cfg.StrOpt('hpe3par_password',
               default='',
               help="3PAR password for the user specified in hpe3par_username",
               secret=True,
               deprecated_name='hp3par_password'),
    cfg.ListOpt('hpe3par_cpg',
                default=["OpenStack"],
                help="List of the CPG(s) to use for volume creation",
                deprecated_name='hp3par_cpg'),
    cfg.ListOpt('hpe3par_snapcpg',
                default=[],
                help="List of the CPG(s) to use for snapshot creation",
                deprecated_name='hp3par_snapcpg'),
    cfg.BoolOpt('hpe3par_debug',
                default=False,
                help="Enable HTTP debugging to 3PAR",
                deprecated_name='hp3par_debug'),
    cfg.ListOpt('hpe3par_iscsi_ips',
                default=[],
                help="List of target iSCSI addresses to use.",
                deprecated_name='hp3par_iscsi_ips'),
    cfg.BoolOpt('hpe3par_iscsi_chap_enabled',
                default=False,
                help="Enable CHAP authentication for iSCSI connections.",
                deprecated_name='hp3par_iscsi_chap_enabled'),
    cfg.BoolOpt('strict_ssh_host_key_policy',
                default=False,
                help='Option to enable strict host key checking.  When '
                     'set to "True" the plugin will only connect to systems '
                     'with a host key present in the configured '
                     '"ssh_hosts_key_file".  When set to "False" the host key '
                     'will be saved upon first connection and used for '
                     'subsequent connections.  Default=False'),
    cfg.StrOpt('ssh_hosts_key_file',
               default='$state_path/ssh_known_hosts',
               help='File containing SSH host keys for the systems with which '
                    'the plugin needs to communicate.  OPTIONAL: '
                    'Default=$state_path/ssh_known_hosts'),
    cfg.BoolOpt('suppress_requests_ssl_warnings',
                default=False,
                help='Suppress requests library SSL certificate warnings.'),
]


CONF = cfg.CONF
CONF.register_opts(hpe3par_opts)


class HPE3PARCommon(object):
    """Class that contains common code for the 3PAR drivers.

    Version history:

    .. code-block:: none

        0.0.1 - Initial version of 3PAR common created.
        0.0.2 - Added the ability to choose volume provisionings.
        0.0.3 - Added support for flash cache.
        0.0.4 - Added support for compression CRUD operation.
        0.0.5 - Added support for snapshot and clone.
        0.0.6 - Added support for reverting volume to snapshot state.

    """

    VERSION = "0.0.6"

    # TODO(Ramy): move these to the 3PAR Client
    VLUN_TYPE_EMPTY = 1
    VLUN_TYPE_PORT = 2
    VLUN_TYPE_HOST = 3
    VLUN_TYPE_MATCHED_SET = 4
    VLUN_TYPE_HOST_SET = 5

    THIN = 2
    DEDUP = 6
    CONVERT_TO_THIN = 1
    CONVERT_TO_FULL = 2
    CONVERT_TO_DEDUP = 3

    # License values for reported capabilities
    COMPRESSION_LIC = "Compression"

    # Valid values for volume type extra specs
    # The first value in the list is the default value
    valid_prov_values = ['thin', 'full', 'dedup']
    valid_persona_values = ['2 - Generic-ALUA',
                            '1 - Generic',
                            '3 - Generic-legacy',
                            '4 - HPUX-legacy',
                            '5 - AIX-legacy',
                            '6 - EGENERA',
                            '7 - ONTAP-legacy',
                            '8 - VMware',
                            '9 - OpenVMS',
                            '10 - HPUX',
                            '11 - WindowsServer']
    hpe_qos_keys = ['minIOPS', 'maxIOPS', 'minBWS', 'maxBWS', 'latency',
                    'priority']
    qos_priority_level = {'low': 1, 'normal': 2, 'high': 3}
    hpe3par_valid_keys = ['cpg', 'snap_cpg', 'provisioning', 'persona', 'vvs',
                          'flash_cache']

    def __init__(self, config):
        self.config = config
        self.client = None
        self.uuid = uuid.uuid4()

    def get_version(self):
        return self.VERSION

    def check_flags(self, options, required_flags):
        for flag in required_flags:
            if not getattr(options, flag, None):
                msg = _('%s is not set') % flag
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

    def _create_client(self):
        cl = client.HPE3ParClient(
            self.config.hpe3par_api_url,
            suppress_ssl_warnings=CONF.suppress_requests_ssl_warnings)
        client_version = hpe3parclient.version

        if client_version < MIN_CLIENT_VERSION:
            ex_msg = (_('Invalid hpe3parclient version found (%(found)s). '
                        'Version %(minimum)s or greater required. Run "pip'
                        ' install --upgrade python-3parclient" to upgrade'
                        ' the hpe3parclient.')
                      % {'found': client_version,
                         'minimum': MIN_CLIENT_VERSION})
            LOG.error(ex_msg)
            raise exception.InvalidInput(reason=ex_msg)

        return cl

    def client_login(self):
        try:
            LOG.debug("Connecting to 3PAR")
            self.client.login(self.config.hpe3par_username,
                              self.config.hpe3par_password)
        except hpeexceptions.HTTPUnauthorized as ex:
            msg = (_("Failed to Login to 3PAR (%(url)s) because %(err)s") %
                   {'url': self.config.hpe3par_api_url, 'err': ex})
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)

        known_hosts_file = CONF.ssh_hosts_key_file
        policy = "AutoAddPolicy"
        if CONF.strict_ssh_host_key_policy:
            policy = "RejectPolicy"
        self.client.setSSHOptions(
            self.config.san_ip,
            self.config.san_login,
            self.config.san_password,
            port=self.config.san_ssh_port,
            conn_timeout=self.config.ssh_conn_timeout,
            privatekey=self.config.san_private_key,
            missing_key_policy=policy,
            known_hosts_file=known_hosts_file)

    def client_logout(self):
        LOG.debug("Disconnect from 3PAR REST and SSH %s", self.uuid)
        self.client.logout()

    def do_setup(self):
        if hpe3parclient is None:
            msg = _('You must install hpe3parclient before using 3PAR'
                    ' drivers. Run "pip install python-3parclient" to'
                    ' install the hpe3parclient.')
            raise exception.VolumeBackendAPIException(data=msg)
        try:
            self.client = self._create_client()
            wsapi_version = self.client.getWsApiVersion()
            self.API_VERSION = wsapi_version['build']
        except hpeexceptions.UnsupportedVersion as ex:
            raise exception.InvalidInput(ex)

        if self.config.hpe3par_debug:
            self.client.debug_rest(True)

    def check_for_setup_error(self):
        LOG.info(_LI("HPE3PARCommon %(common_ver)s,"
                     "hpe3parclient %(rest_ver)s"),
                 {"common_ver": self.VERSION,
                  "rest_ver": hpe3parclient.get_version_string()})

        self.client_login()
        try:
            cpg_names = self.config.hpe3par_cpg
            for cpg_name in cpg_names:
                self.validate_cpg(cpg_name)

        finally:
            self.client_logout()

    def validate_cpg(self, cpg_name):
        try:
            self.client.getCPG(cpg_name)
        except hpeexceptions.HTTPNotFound:
            err = (_("CPG (%s) doesn't exist on array") % cpg_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err)

    def get_domain(self, cpg_name):
        try:
            cpg = self.client.getCPG(cpg_name)
        except hpeexceptions.HTTPNotFound:
            err = (_("Failed to get domain because CPG (%s) doesn't "
                     "exist on array.") % cpg_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err)

        if 'domain' in cpg:
            return cpg['domain']
        return None

    def _capacity_from_size(self, vol_size):
        # because 3PAR volume sizes are in Mebibytes.
        if int(vol_size) == 0:
            capacity = units.Gi  # default: 1GiB
        else:
            capacity = vol_size * units.Gi

        capacity = int(math.ceil(capacity / units.Mi))
        return capacity

    def _delete_3par_host(self, hostname):
        self.client.deleteHost(hostname)

    def _create_3par_vlun(self, volume, hostname, nsp, lun_id=None):
        try:
            location = None
            auto = True

            if lun_id is not None:
                auto = False

            if nsp is None:
                location = self.client.createVLUN(volume, hostname=hostname,
                                                  auto=auto, lun=lun_id)
            else:
                port = self.build_portPos(nsp)
                location = self.client.createVLUN(volume, hostname=hostname,
                                                  auto=auto, portPos=port,
                                                  lun=lun_id)

            vlun_info = None
            if location:
                # The LUN id is returned as part of the location URI
                vlun = location.split(',')
                vlun_info = {'volume_name': vlun[0],
                             'lun_id': int(vlun[1]),
                             'host_name': vlun[2],
                             }
                if len(vlun) > 3:
                    vlun_info['nsp'] = vlun[3]

            return vlun_info

        except hpeexceptions.HTTPBadRequest as e:
            if 'must be in the same domain' in e.get_description():
                LOG.error(e.get_description())
                raise exception.Invalid3PARDomain(err=e.get_description())

    def _safe_hostname(self, hostname):
        """We have to use a safe hostname length for 3PAR host names."""
        try:
            index = hostname.index('.')
        except ValueError:
            # couldn't find it
            index = len(hostname)

        # we'll just chop this off for now.
        if index > 31:
            index = 31

        return hostname[:index]

    def _get_3par_host(self, hostname):
        return self.client.getHost(hostname)

    def get_ports(self):
        return self.client.getPorts()

    def get_qos_detail(self, vvset):
        return self.client.queryQoSRule(vvset)

    def get_active_target_ports(self):
        ports = self.get_ports()
        target_ports = []
        for port in ports['members']:
            if (
                port['mode'] == self.client.PORT_MODE_TARGET and
                port['linkState'] == self.client.PORT_STATE_READY
            ):
                port['nsp'] = self.build_nsp(port['portPos'])
                target_ports.append(port)

        return target_ports

    def get_active_fc_target_ports(self):
        ports = self.get_active_target_ports()
        fc_ports = []
        for port in ports:
            if port['protocol'] == self.client.PORT_PROTO_FC:
                fc_ports.append(port)

        return fc_ports

    def get_active_iscsi_target_ports(self):
        ports = self.get_active_target_ports()
        iscsi_ports = []
        for port in ports:
            if port['protocol'] == self.client.PORT_PROTO_ISCSI:
                iscsi_ports.append(port)

        return iscsi_ports

    def _get_vlun(self, volume_name, hostname, lun_id=None, nsp=None):
        """find a VLUN on a 3PAR host."""
        vluns = self.client.getHostVLUNs(hostname)
        found_vlun = None
        for vlun in vluns:
            if volume_name in vlun['volumeName']:
                if lun_id is not None:
                    if vlun['lun'] == lun_id:
                        if nsp:
                            port = self.build_portPos(nsp)
                            if vlun['portPos'] == port:
                                found_vlun = vlun
                                break
                        else:
                            found_vlun = vlun
                            break
                else:
                    found_vlun = vlun
                    break

        if found_vlun is None:
            LOG.info(_LI("3PAR vlun %(name)s not found on host %(host)s"),
                     {'name': volume_name, 'host': hostname})
        return found_vlun

    def create_vlun(self, volume, host, nsp=None, lun_id=None):
        """Create a VLUN.

        In order to export a volume on a 3PAR box, we have to create a VLUN.
        """
        volume_name = utils.get_3par_vol_name(volume['id'])
        vlun_info = self._create_3par_vlun(volume_name, host['name'], nsp,
                                           lun_id=lun_id)
        return self._get_vlun(volume_name,
                              host['name'],
                              vlun_info['lun_id'],
                              nsp)

    def delete_vlun(self, volume, hostname):
        volume_name = utils.get_3par_vol_name(volume['id'])
        vluns = self.client.getHostVLUNs(hostname)

        # When deleting VLUNs, you simply need to remove the template VLUN
        # and any active VLUNs will be automatically removed.  The template
        # VLUN are marked as active: False

        volume_vluns = []

        for vlun in vluns:
            if volume_name in vlun['volumeName']:
                # template VLUNs are 'active' = False
                if not vlun['active']:
                    volume_vluns.append(vlun)

        if not volume_vluns:
            msg = (
                _LW("3PAR vlun for volume %(name)s not found on "
                    "host %(host)s"), {'name': volume_name, 'host': hostname})
            LOG.warning(msg)
            return

        # VLUN Type of MATCHED_SET 4 requires the port to be provided
        for vlun in volume_vluns:
            if 'portPos' in vlun:
                self.client.deleteVLUN(volume_name, vlun['lun'],
                                       hostname=hostname,
                                       port=vlun['portPos'])
            else:
                self.client.deleteVLUN(volume_name, vlun['lun'],
                                       hostname=hostname)

        # Determine if there are other volumes attached to the host.
        # This will determine whether we should try removing host from host set
        # and deleting the host.
        vluns = []
        try:
            vluns = self.client.getHostVLUNs(hostname)
        except hpeexceptions.HTTPNotFound:
            LOG.debug("All VLUNs removed from host %s", hostname)
            pass

        for vlun in vluns:
            if volume_name not in vlun['volumeName']:
                # Found another volume
                break
        else:
            # We deleted the last vlun, so try to delete the host too.
            # This check avoids the old unnecessary try/fail when vluns exist
            # but adds a minor race condition if a vlun is manually deleted
            # externally at precisely the wrong time. Worst case is leftover
            # host, so it is worth the unlikely risk.

            try:
                self._delete_3par_host(hostname)
            except Exception as ex:
                # Any exception down here is only logged.  The vlun is deleted.

                # If the host is in a host set, the delete host will fail and
                # the host will remain in the host set.  This is desired
                # because docker was not responsible for the host set
                # assignment.  The host set could be used outside of docker
                # for future needs (e.g. export volume to host set).

                # The log info explains why the host was left alone.
                LOG.info(_LI("3PAR vlun for volume '%(name)s' was deleted, "
                             "but the host '%(host)s' was not deleted "
                             "because: %(reason)s"),
                         {'name': volume_name, 'host': hostname,
                          'reason': ex.get_description()})

    def _get_key_value(self, hpe3par_keys, key, default=None):
        if hpe3par_keys is not None and key in hpe3par_keys:
            return hpe3par_keys[key]
        else:
            return default

    def _check_license_enabled(self, valid_licenses, license_to_check,
                               capability):
        """Check a license against valid licenses on the array."""

        LOG.info(_LI(" license_to_check and valid_licenses are"
                     " '%(license_to_check)s' \n  '%(valid_licenses)s' "),
                 {'license_to_check': license_to_check,
                  'valid_licenses': valid_licenses})
        if valid_licenses:
            for license in valid_licenses:
                if license_to_check in license.get('name'):
                    return True
            LOG.debug(("'%(capability)s' requires a '%(license)s' "
                       "license which is not installed.") %
                      {'capability': capability,
                       'license': license_to_check})
        return False

    def _get_keys_by_volume_type(self, volume_type):
        hpe3par_keys = {}
        specs = volume_type.get('extra_specs')
        for key, value in specs.items():
            if ':' in key:
                fields = key.split(':')
                key = fields[1]
            if key in self.hpe3par_valid_keys:
                hpe3par_keys[key] = value
        return hpe3par_keys

    def get_cpg(self, volume, allowSnap=False):
        volume_name = utils.get_3par_vol_name(volume['id'])
        vol = self.client.getVolume(volume_name)
        if 'userCPG' in vol:
            return vol['userCPG']
        elif allowSnap:
            return vol['snapCPG']
        return None

    def _get_3par_vol_comment(self, volume_name):
        vol = self.client.getVolume(volume_name)
        if 'comment' in vol:
            return vol['comment']
        return None

    def get_compression_policy(self, compression_val):
        compression_support = False
        info = self.client.getStorageSystemInfo()
        if 'licenseInfo' in info:
            if 'licenses' in info['licenseInfo']:
                valid_licenses = info['licenseInfo']['licenses']
                compression_support = self._check_license_enabled(
                    valid_licenses, self.COMPRESSION_LIC, "Compression")
            # here check the WSAPI version
        if self.API_VERSION < COMPRESSION_API_VERSION:
            err = (_("Compression policy requires "
                     "WSAPI version '%(compression_version)s' "
                     "version '%(version)s' is installed.") %
                   {'compression_version': COMPRESSION_API_VERSION,
                    'version': self.API_VERSION})
            LOG.error(err)
            raise exception.InvalidInput(reason=err)
        else:
            if compression_val.lower() == 'true':
                if not compression_support:
                    msg = _('Compression is not supported on '
                            'underlying hardware')
                    LOG.error(msg)
                    raise exception.InvalidInput(reason=msg)
                return True
            else:
                return False
        return None

    def create_volume(self, volume):
        LOG.debug('CREATE VOLUME (%(disp_name)s: %(vol_name)s %(id)s on '
                  '%(host)s)',
                  {'disp_name': volume['display_name'],
                   'vol_name': volume['name'],
                   'id': utils.get_3par_vol_name(volume['id']),
                   'host': volume['host']})
        try:
            comments = {'volume_id': volume['id'],
                        'name': volume['name'],
                        'type': 'Docker'}

            name = volume.get('display_name', None)
            if name:
                comments['display_name'] = name

            # TODO(leeantho): Choose the first CPG for now. In the future
            # support selecting different CPGs if multiple are provided.
            cpg = self.config.hpe3par_cpg[0]

            # check for valid provisioning type
            prov_value = volume['provisioning']
            if prov_value not in self.valid_prov_values:
                err = (_("Must specify a valid provisioning type %(valid)s, "
                         "value '%(prov)s' is invalid.") %
                       {'valid': self.valid_prov_values,
                        'prov': prov_value})
                LOG.error(err)
                raise exception.InvalidInput(reason=err)

            tpvv = True
            tdvv = False
            fullprovision = False

            if prov_value == "full":
                tpvv = False
            elif prov_value == "dedup":
                tpvv = False
                tdvv = True

            if tdvv and (self.API_VERSION < DEDUP_API_VERSION):
                err = (_("Dedup is a valid provisioning type, "
                         "but requires WSAPI version '%(dedup_version)s' "
                         "version '%(version)s' is installed.") %
                       {'dedup_version': DEDUP_API_VERSION,
                        'version': self.API_VERSION})
                LOG.error(err)
                raise exception.InvalidInput(reason=err)

            extras = {'comment': json.dumps(comments),
                      'tpvv': tpvv, }

            if len(self.config.hpe3par_snapcpg):
                extras['snapCPG'] = self.config.hpe3par_snapcpg[0]
            else:
                extras['snapCPG'] = cpg

                # Only set the dedup option if the backend supports it.
            if self.API_VERSION >= DEDUP_API_VERSION:
                extras['tdvv'] = tdvv

            capacity = self._capacity_from_size(volume['size'])

            if (tpvv is False and tdvv is False):
                fullprovision = True

            compression_val = volume['compression']   # None/true/False
            compression = None

            if compression_val is not None:
                compression = self.get_compression_policy(compression_val)

            if compression is True:
                if not fullprovision and capacity >= 16384:
                    extras['compression'] = compression
                else:
                    err = (_("To create compression enabled volume, size of "
                             "the volume should be atleast 16GB. Fully "
                             "provisioned volume can not be compressed. "
                             "Please re enter requested volume size or "
                             "provisioning type. "))
                    LOG.error(err)
                    raise exception.InvalidInput(reason=err)
            if compression is not None:
                extras['compression'] = compression

            volume_name = utils.get_3par_vol_name(volume['id'])
            self.client.createVolume(volume_name, cpg, capacity, extras)

            # check for qos
            vvs_name = volume.get('qos_name')

            # Check if flash cache needs to be enabled
            flash_cache = self.get_flash_cache_policy(volume['flash_cache'])

            if vvs_name or flash_cache is not None:
                try:
                    self._add_volume_to_volume_set(volume, volume_name,
                                                   cpg, flash_cache, vvs_name)
                except exception.InvalidInput as ex:
                    # Delete the volume if unable to add it to the volume set
                    self.client.deleteVolume(volume_name)
                    LOG.error(_LE("Exception: %s"), ex)
                    raise exception.PluginException(ex)
        except hpeexceptions.HTTPConflict:
            msg = _("Volume (%s) already exists on array") % volume_name
            LOG.error(msg)
            raise exception.Duplicate(msg)
        except hpeexceptions.HTTPBadRequest as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise exception.Invalid(ex.get_description())
        except exception.InvalidInput as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise
        except exception.PluginException as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise
        except Exception as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise exception.PluginException(ex)

    def delete_volume(self, volume, is_snapshot=False):
        try:
            if is_snapshot:
                volume_name = utils.get_3par_snap_name(volume['id'])
            else:
                volume_name = utils.get_3par_vol_name(volume['id'])
            # Try and delete the volume, it might fail here because
            # the volume is part of a volume set which will have the
            # volume set name in the error.
            try:
                self.client.deleteVolume(volume_name)
            except hpeexceptions.HTTPBadRequest as ex:
                if ex.get_code() == 29:
                    if self.client.isOnlinePhysicalCopy(volume_name):
                        LOG.debug("Found an online copy for %(volume)s",
                                  {'volume': volume_name})
                        # the volume is in process of being cloned.
                        # stopOnlinePhysicalCopy will also delete
                        # the volume once it stops the copy.
                        self.client.stopOnlinePhysicalCopy(volume_name)
                    else:
                        LOG.error(_LE("Exception: %s"), ex)
                        raise
                else:
                    LOG.error(_LE("Exception: %s"), ex)
                    raise
            except hpeexceptions.HTTPConflict as ex:
                if ex.get_code() == 34:
                    # This is a special case which means the
                    # volume is part of a volume set.
                    vvset_name = self.client.findVolumeSet(volume_name)
                    LOG.debug("Returned vvset_name = %s", vvset_name)
                    if vvset_name is not None and \
                       vvset_name.startswith('vvs-'):
                        # We have a single volume per volume set, so
                        # remove the volume set.
                        self.client.deleteVolumeSet(
                            utils.get_3par_vvs_name(volume['id']))
                    elif vvset_name is not None:
                        # We have a pre-defined volume set just remove the
                        # volume and leave the volume set.
                        self.client.removeVolumeFromVolumeSet(vvset_name,
                                                              volume_name)
                    self.client.deleteVolume(volume_name)
                elif (ex.get_code() == 151 or ex.get_code() == 32):
                    # the volume is being operated on in a background
                    # task on the 3PAR.
                    # TODO(walter-boring) do a retry a few times.
                    # for now lets log a better message
                    msg = _("The volume is currently busy on the 3PAR"
                            " and cannot be deleted at this time. "
                            "You can try again later.")
                    LOG.error(msg)
                    raise exception.VolumeIsBusy(message=msg)
                else:
                    LOG.error(_LE("Exception: %s"), ex)
                    raise exception.VolumeIsBusy(message=ex.get_description())

        except hpeexceptions.HTTPNotFound as ex:
            LOG.warning(_LW("Delete volume id not found. Ex: %(msg)s"),
                        {'msg': ex})
        except hpeexceptions.HTTPForbidden as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise exception.NotAuthorized(ex.get_description())
        except hpeexceptions.HTTPConflict as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise exception.VolumeIsBusy(message=ex.get_description())
        except Exception as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise exception.PluginException(ex)

    def _get_3par_hostname_from_wwn_iqn(self, wwns, iqns):
        if wwns is not None and not isinstance(wwns, list):
            wwns = [wwns]
        if iqns is not None and not isinstance(iqns, list):
            iqns = [iqns]

        out = self.client.getHosts()
        hosts = out['members']
        for host in hosts:
            if 'iSCSIPaths' in host and iqns is not None:
                iscsi_paths = host['iSCSIPaths']
                for iscsi in iscsi_paths:
                    for iqn in iqns:
                        if iqn == iscsi['name']:
                            return host['name']

            if 'FCPaths' in host and wwns is not None:
                fc_paths = host['FCPaths']
                for fc in fc_paths:
                    for wwn in wwns:
                        if wwn == fc['wwn']:
                            return host['name']

    def terminate_connection(self, volume, hostname, wwn=None, iqn=None):
        """Driver entry point to unattach a volume from an instance."""
        # does 3par know this host by a different name?
        hosts = None
        if wwn:
            hosts = self.client.queryHost(wwns=wwn)
        elif iqn:
            hosts = self.client.queryHost(iqns=[iqn])

        if hosts and hosts['members'] and 'name' in hosts['members'][0]:
            hostname = hosts['members'][0]['name']

        try:
            self.delete_vlun(volume, hostname)
            return
        except hpeexceptions.HTTPNotFound as e:
            if 'host does not exist' in e.get_description():
                # use the wwn to see if we can find the hostname
                hostname = self._get_3par_hostname_from_wwn_iqn(wwn, iqn)
                # no 3par host, re-throw
                if hostname is None:
                    LOG.error(_LE("Exception: %s"), e)
                    raise
            else:
                # not a 'host does not exist' HTTPNotFound exception, re-throw
                LOG.error(_LE("Exception: %s"), e)
                raise

        # try again with name retrieved from 3par
        self.delete_vlun(volume, hostname)

    def build_nsp(self, portPos):
        return '%s:%s:%s' % (portPos['node'],
                             portPos['slot'],
                             portPos['cardPort'])

    def build_portPos(self, nsp):
        split = nsp.split(":")
        portPos = {}
        portPos['node'] = int(split[0])
        portPos['slot'] = int(split[1])
        portPos['cardPort'] = int(split[2])
        return portPos

    def find_existing_vlun(self, volume, host):
        """Finds an existing VLUN for a volume on a host.

        Returns an existing VLUN's information. If no existing VLUN is found,
        None is returned.

        :param volume: A dictionary describing a volume.
        :param host: A dictionary describing a host.
        """
        existing_vlun = None
        try:
            vol_name = utils.get_3par_vol_name(volume['id'])
            host_vluns = self.client.getHostVLUNs(host['name'])

            # The first existing VLUN found will be returned.
            for vlun in host_vluns:
                if vlun['volumeName'] == vol_name:
                    existing_vlun = vlun
                    break
        except hpeexceptions.HTTPNotFound:
            # ignore, no existing VLUNs were found
            LOG.debug("No existing VLUNs were found for host/volume "
                      "combination: %(host)s, %(vol)s",
                      {'host': host['name'],
                       'vol': vol_name})
            pass
        return existing_vlun

    def find_existing_vluns(self, volume, host):
        existing_vluns = []
        try:
            vol_name = utils.get_3par_vol_name(volume['id'])
            host_vluns = self.client.getHostVLUNs(host['name'])

            for vlun in host_vluns:
                if vlun['volumeName'] == vol_name:
                    existing_vluns.append(vlun)
        except hpeexceptions.HTTPNotFound:
            # ignore, no existing VLUNs were found
            LOG.debug("No existing VLUNs were found for host/volume "
                      "combination: %(host)s, %(vol)s",
                      {'host': host['name'],
                       'vol': vol_name})
            pass
        return existing_vluns

    def get_flash_cache_policy(self, flash_cache):
        if flash_cache is not None:
            # If requested, see if supported on back end
            if self.API_VERSION < FLASH_CACHE_API_VERSION:
                err = (_("Flash Cache Policy requires "
                         "WSAPI version '%(fcache_version)s' "
                         "version '%(version)s' is installed.") %
                       {'fcache_version': FLASH_CACHE_API_VERSION,
                        'version': self.API_VERSION})
                LOG.error(err)
                raise exception.InvalidInput(reason=err)
            else:
                if flash_cache.lower() == 'true':
                    return self.client.FLASH_CACHE_ENABLED
                else:
                    return self.client.FLASH_CACHE_DISABLED

        return None

    def _set_flash_cache_policy_in_vvs(self, flash_cache, vvs_name):
        # Update virtual volume set
        if flash_cache:
            try:
                self.client.modifyVolumeSet(vvs_name,
                                            flashCachePolicy=flash_cache)
                LOG.info(_LI("Flash Cache policy set to %s"), flash_cache)
            except Exception as ex:
                LOG.error(_LE("Error setting Flash Cache policy "
                              "to %s - exception"), flash_cache)
                exception.PluginException(ex)

    def _add_volume_to_volume_set(self, volume, volume_name,
                                  cpg, flash_cache, vvs_name=None):
        if vvs_name is not None:
            try:
                if flash_cache is not None:
                    self._set_flash_cache_policy_in_vvs(flash_cache, vvs_name)
                self.client.addVolumeToVolumeSet(vvs_name, volume_name)
            except Exception as ex:
                msg = _("Failed to set flash-cache policy or add volume to"
                        "VV set %s - %s.") % (vvs_name, ex)
                LOG.error(msg)
                self.client.deleteVolume(volume_name)
                raise exception.PluginException(ex)
        else:
            vvs_name = utils.get_3par_vvs_name(volume['id'])
            domain = self.get_domain(cpg)
            self.client.createVolumeSet(vvs_name, domain)
            try:
                self._set_flash_cache_policy_in_vvs(flash_cache, vvs_name)
                self.client.addVolumeToVolumeSet(vvs_name, volume_name)
            except Exception as ex:
                # Cleanup the volume set if unable to create the qos rule
                # or flash cache policy or add the volume to the volume set
                self.client.deleteVolumeSet(vvs_name)
                raise exception.PluginException(ex)

    def _get_prioritized_host_on_3par(self, host, hosts, hostname):
        # Check whether host with wwn/iqn of initiator present on 3par
        if hosts and hosts['members'] and 'name' in hosts['members'][0]:
            # Retrieving 'host' and 'hosts' from 3par using hostname
            # and wwn/iqn respectively. Compare hostname of 'host' and 'hosts',
            # if they do not match it means 3par has a pre-existing host
            # with some other name.
            if host['name'] != hosts['members'][0]['name']:
                hostname = hosts['members'][0]['name']
                LOG.info(("Prioritize the host retrieved from wwn/iqn "
                          "Hostname : %(hosts)s  is used instead "
                          "of Hostname: %(host)s"),
                         {'hosts': hostname,
                          'host': host['name']})
                host = self._get_3par_host(hostname)
                return host, hostname

        return host, hostname

    def revert_snap_to_vol(self, volume, snapshot):
        try:
            optional = {}
            snapshot_name = utils.get_3par_snap_name(snapshot['id'])
            volume_name = utils.get_3par_vol_name(volume['id'])
            if self.client.isOnlinePhysicalCopy(volume_name):
                LOG.info("Found an online copy for %(volume)s. ",
                         {'volume': volume_name})
                optional['online'] = True            
            self.client.promoteVirtualCopy(snapshot_name, optional=optional)
            LOG.info("Volume %(volume)s successfully reverted to"
                     " %(snapname)s.", {'volume': volume_name,
                                     'snapname': snapshot_name})
        except hpeexceptions.HTTPForbidden as ex:
            LOG.error("Exception: %s", ex)
            raise exception.RevertSnapshotException()
        except hpeexceptions.HTTPConflict as ex:
            LOG.error("Exception: %s", ex)
            raise exception.RevertSnapshotException()

    def create_snapshot(self, snapshot):
        LOG.info("Create Snapshot\n%s", json.dumps(snapshot, indent=2))

        try:
            snap_name = utils.get_3par_snap_name(snapshot['id'])
            vol_name = utils.get_3par_vol_name(snapshot['volume_id'])

            extra = {'volume_name': snapshot['volume_name']}
            vol_id = snapshot.get('volume_id', None)
            if vol_id:
                extra['volume_id'] = vol_id

            try:
                extra['display_name'] = snapshot['display_name']
            except AttributeError:
                pass

            try:
                extra['description'] = snapshot['display_description']
            except AttributeError:
                pass

            optional = {'comment': json.dumps(extra),
                        'readOnly': True}
            if snapshot['expirationHours']:
                optional['expirationHours'] = snapshot['expirationHours']
            if snapshot['retentionHours']:
                optional['retentionHours'] = snapshot['retentionHours']

            self.client.createSnapshot(snap_name, vol_name, optional)
        except hpeexceptions.HTTPForbidden as ex:
            LOG.error("Exception: %s", ex)
            raise exception.NotAuthorized()
        except hpeexceptions.HTTPNotFound as ex:
            LOG.error("Exception: %s", ex)
            raise exception.NotFound()

    def create_cloned_volume(self, dst_volume, src_vref):
        LOG.info("Create clone of volume\n%s", json.dumps(src_vref, indent=2))
        try:
            dst_3par_vol_name = utils.get_3par_vol_name(dst_volume['id'])
            src_3par_vol_name = utils.get_3par_vol_name(src_vref['id'])
            # back_up_process = False
            vol_chap_enabled = False

            # Check whether a volume is ISCSI and CHAP enabled on it.
            if self.config.hpe3par_iscsi_chap_enabled:
                try:
                    vol_chap_enabled = self.client.getVolumeMetaData(
                        src_3par_vol_name, 'HPQ-docker-CHAP-name')['value']
                except hpeexceptions.HTTPNotFound:
                    LOG.debug("CHAP is not enabled on volume %(vol)s ",
                              {'vol': src_vref['id']})
                    vol_chap_enabled = False

            # if the sizes of the 2 volumes are the same and except backup
            # process for ISCSI volume with chap enabled on it.
            # we can do an online copy, which is a background process
            # on the 3PAR that makes the volume instantly available.
            # We can't resize a volume, while it's being copied.
            if dst_volume['size'] == src_vref['size'] and not \
                    (vol_chap_enabled):
                LOG.info("Creating a clone of volume, using online copy.")

                cpg = self.config.hpe3par_cpg[0]
                snap_cpg = cpg
                if len(self.config.hpe3par_snapcpg):
                    snap_cpg = self.config.hpe3par_snapcpg[0]

                # check for valid provisioning type
                prov_value = src_vref['provisioning']
                prov_map = {"full": {"tpvv": False, "tdvv": False},
                            "thin": {"tpvv": True, "tdvv": False},
                            "dedup": {"tpvv": False, "tdvv": True}}
                tpvv = prov_map[prov_value]['tpvv']
                tdvv = prov_map[prov_value]['tdvv']

                compression_val = src_vref['compression']  # None/true/False
                compression = None
                if compression_val is not None:
                    compression = (compression_val.lower() == 'true')

                # make the 3PAR copy the contents.
                # can't delete the original until the copy is done.
                self._copy_volume(src_3par_vol_name, dst_3par_vol_name,
                                  cpg=cpg, snap_cpg=snap_cpg,
                                  tpvv=tpvv, tdvv=tdvv,
                                  compression=compression)

                # check for qos
                vvs_name = src_vref.get('qos_name')

                # Check if flash cache needs to be enabled
                flash_cache = \
                    self.get_flash_cache_policy(src_vref['flash_cache'])

                if vvs_name or flash_cache is not None:
                    try:
                        self._add_volume_to_volume_set(dst_volume,
                                                       dst_3par_vol_name,
                                                       cpg, flash_cache,
                                                       vvs_name)
                    except exception.InvalidInput as ex:
                        # Delete volume if unable to add it to volume set
                        self.client.deleteVolume(dst_3par_vol_name)
                        LOG.error(_LE("Exception: %s"), ex)
                        raise exception.PluginException(ex)
            else:
                # The size of the new volume is different, so we have to
                # copy the volume and wait.  Do the resize after the copy
                # is complete.
                LOG.debug("Creating a clone of volume, using offline copy.")

                # we first have to create the destination volume
                model_update = self.create_volume(dst_volume)

                optional = {'priority': 1}
                body = self.client.copyVolume(src_3par_vol_name,
                                              dst_3par_vol_name, None,
                                              optional=optional)
                task_id = body['taskid']

                task_status = self._wait_for_task_completion(task_id)
                if task_status['status'] is not self.client.TASK_DONE:
                    dbg = {'status': task_status, 'id': dst_volume['id']}
                    msg = _('copy volume task failed: create_cloned_volume '
                            'id=%(id)s, status=%(status)s.') % dbg
                    LOG.error(msg)
                    raise exception.PluginException(msg)
                else:
                    LOG.debug('Copy volume completed: create_cloned_volume: '
                              'id=%s.', dst_volume['id'])

                return model_update

        except hpeexceptions.HTTPForbidden:
            raise exception.NotAuthorized()
        except hpeexceptions.HTTPNotFound:
            raise exception.NotFound()
        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.PluginException(ex)

    def _copy_volume(self, src_name, dest_name, cpg, snap_cpg=None,
                     tpvv=True, tdvv=False, compression=None):
        # Virtual volume sets are not supported with the -online option
        LOG.info('Creating clone of a volume %(src)s to %(dest)s.',
                 {'src': src_name, 'dest': dest_name})

        optional = {'tpvv': tpvv, 'online': True}
        if snap_cpg is not None:
            optional['snapCPG'] = snap_cpg

        if self.API_VERSION >= DEDUP_API_VERSION:
            optional['tdvv'] = tdvv

        if (compression is not None and
                self.API_VERSION >= COMPRESSION_API_VERSION):
            optional['compression'] = compression

        body = self.client.copyVolume(src_name, dest_name, cpg, optional)
        return body['taskid']

    def _wait_for_task_completion(self, task_id):
        """This waits for a 3PAR background task complete or fail.

        This looks for a task to get out of the 'active' state.
        """
        # Wait for the physical copy task to complete
        def _wait_for_task(task_id):
            status = self.client.getTask(task_id)
            LOG.debug("3PAR Task id %(id)s status = %(status)s",
                      {'id': task_id,
                       'status': status['status']})
            if status['status'] is not self.client.TASK_ACTIVE:
                self._task_status = status
                raise loopingcall.LoopingCallDone()

        self._task_status = None
        timer = loopingcall.FixedIntervalLoopingCall(
            _wait_for_task, task_id)
        timer.start(interval=1).wait()

        return self._task_status

    def get_snapshots_by_vol(self, vol_id):
        bkend_vol_name = utils.get_3par_vol_name(vol_id)
        cpg_name = self.config.hpe3par_cpg[0]
        if len(self.config.hpe3par_snapcpg):
            cpg_name = self.config.hpe3par_snapcpg[0]
        LOG.debug("Querying snapshots for %s in %s cpg "
                   %(bkend_vol_name,cpg_name))
        return self.client.getSnapshotsOfVolume(cpg_name, bkend_vol_name)
