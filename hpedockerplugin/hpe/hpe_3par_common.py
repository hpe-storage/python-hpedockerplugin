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
import six
import uuid

from oslo_utils import importutils
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import units

from hpedockerplugin import exception
from hpedockerplugin.hpe import utils
from hpedockerplugin.i18n import _, _LE, _LI, _LW

hpe3parclient = importutils.try_import("hpe3parclient")
if hpe3parclient:
    from hpe3parclient import client
    from hpe3parclient import exceptions as hpeexceptions

LOG = logging.getLogger(__name__)

MIN_CLIENT_VERSION = '4.0.0'
DEDUP_API_VERSION = 30201120
FLASH_CACHE_API_VERSION = 30201200
COMPRESSION_API_VERSION = 30301215
REMOTE_COPY_API_VERSION = 30202290
TIME_OUT = 30

CONF = cfg.CONF


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

    SYNC = 1
    PERIODIC = 2
    STREAMING = 4
    DEFAULT_SYNC_PERIOD = 900
    RCG_STARTED = 3
    RCG_STOPPED = 5
    ROLE_PRIMARY = 1
    ROLE_SECONDARY = 2

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

    def __init__(self, host_config, src_bkend_config, tgt_bkend_config=None):
        self._host_config = host_config
        self.src_bkend_config = src_bkend_config
        self.tgt_bkend_config = tgt_bkend_config
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

    def _create_client(self, timeout=TIME_OUT):
        try:
            suppress_ssl_warnings = \
                CONF.suppress_requests_ssl_warnings
            cl = client.HPE3ParClient(
                self.src_bkend_config.hpe3par_api_url, timeout=timeout,
                suppress_ssl_warnings=suppress_ssl_warnings)
        except Exception as ex:
            msg = (_('Failed to connect to the array using %(url)s.'
                     'Please ensure the following \n'
                     '1.Value of IP and port specified for '
                     'hpe3par_api_url in hpe.conf is correct and \n'
                     '2. The array is reachable from the host.\n')
                   % {'url': self.src_bkend_config.hpe3par_api_url})
            LOG.error(msg)
            raise exception.ConnectionError(ex)

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
            self.client.login(self.src_bkend_config.hpe3par_username,
                              self.src_bkend_config.hpe3par_password)
        except hpeexceptions.HTTPUnauthorized as ex:
            msg = (_("Failed to Login to 3PAR (%(url)s) because %(err)s") %
                   {'url': self.src_bkend_config.hpe3par_api_url, 'err': ex})
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)

        known_hosts_file = self._host_config.ssh_hosts_key_file

        policy = "AutoAddPolicy"
        if self._host_config.strict_ssh_host_key_policy:
            policy = "RejectPolicy"
        self.client.setSSHOptions(
            self.src_bkend_config.san_ip,
            self.src_bkend_config.san_login,
            self.src_bkend_config.san_password,
            port=self.src_bkend_config.san_ssh_port,
            conn_timeout=self.src_bkend_config.ssh_conn_timeout,
            privatekey=self.src_bkend_config.san_private_key,
            missing_key_policy=policy,
            known_hosts_file=known_hosts_file)

    def client_logout(self):
        LOG.debug("Disconnect from 3PAR REST and SSH %s", self.uuid)
        self.client.logout()

    def do_setup(self, timeout=TIME_OUT):
        if hpe3parclient is None:
            msg = _('You must install hpe3parclient before using 3PAR'
                    ' drivers. Run "pip install python-3parclient" to'
                    ' install the hpe3parclient.')
            raise exception.VolumeBackendAPIException(data=msg)
        try:
            self.client = self._create_client(timeout=timeout)
            wsapi_version = self.client.getWsApiVersion()
            self.API_VERSION = wsapi_version['build']
        except hpeexceptions.UnsupportedVersion as ex:
            raise exception.InvalidInput(ex)

        if self.src_bkend_config.hpe3par_debug:
            self.client.debug_rest(True)

    def check_for_setup_error(self):
        LOG.info(_LI("HPE3PARCommon %(common_ver)s,"
                     "hpe3parclient %(rest_ver)s"),
                 {"common_ver": self.VERSION,
                  "rest_ver": hpe3parclient.get_version_string()})

        self.client_login()
        try:
            cpg_names = self.src_bkend_config.hpe3par_cpg
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
        try:
            return self.client.queryQoSRule(vvset)
        except Exception as ex:
            msg = _("Failed to get qos from VV set %s - %s.") %\
                   (vvset, ex)
            LOG.error(msg)
            raise exception.HPEDriverGetQosFromVvSetFailed(ex)

    def get_vvset_detail(self, vvset):
        return self.client.getVolumeSet(vvset)

    def get_vvset_from_volume(self, volume):
        vvset_name = self.client.findVolumeSet(volume)
        if vvset_name is not None:
            return self.client.getVolumeSet(vvset_name)
        return None

    def get_volume_detail(self, volume):
        return self.client.getVolume(volume)

    def manage_existing(self, volume, existing_ref_details, is_snap=False,
                        target_vol_name=None, comment=None):

        # check for volume/snap attachment, if attached raise error
        existing_ref = existing_ref_details.get('name')
        try:
            self.client.getVLUN(existing_ref)
        except hpeexceptions.HTTPNotFound:
            # volume not attached so its good to manage
            msg = (_("Volume: (%s) doesn't have vluns"
                     " so can be manage.") % existing_ref)
            LOG.info(msg)
            pass
        else:
            msg = "Managing volume %s failed because it is attached." % \
                  existing_ref
            LOG.error(msg)
            raise exception.HPEDriverManageVolumeAttached(reason=msg)

        if target_vol_name is None:
            target_vol_name = utils.get_3par_name(volume['id'], is_snap)

        if comment is None:
            comment = {'volume_id': volume.get('id'),
                       'name': volume.get('name'),
                       'type': 'Docker',
                       'display_name': volume.get('display_name')}
            comment = json.dumps(comment)

        new_vals = {'newName': target_vol_name, 'comment': comment}

        if('userCPG' in existing_ref_details and
           'snapCPG' not in existing_ref_details):
            new_vals['snapCPG'] = existing_ref_details['userCPG']

        self.client.modifyVolume(existing_ref, new_vals)

        # we can get the latest 3par volume details now
        volume_detail_3par = self.get_volume_detail(target_vol_name)
        return volume_detail_3par

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

    def create_vlun(self, volume, host, is_snap, nsp=None, lun_id=None):
        """Create a VLUN.

        In order to export a volume on a 3PAR box, we have to create a VLUN.
        """
        volume_name = utils.get_3par_name(volume['id'], is_snap)
        vlun_info = self._create_3par_vlun(volume_name, host['name'], nsp,
                                           lun_id=lun_id)
        return self._get_vlun(volume_name,
                              host['name'],
                              vlun_info['lun_id'],
                              nsp)

    def check_response(self, resp):
        for r in resp:
            if 'Error' in r or 'Invalid' in r:
                err_resp = r.strip()
                return err_resp
        return ""

    def create_snap_schedule(self, src_vol_name, schedName, snapPrefix,
                             exphrs, rethrs, schedFrequency):
        expHr = str(exphrs)
        retHr = str(rethrs)

        cmd = ['createsched']
        createsnapstring = []
        createsnapstring.append('"createsv -f ')
        if exphrs is not None:
            createsnapstring.append('-exp ' + expHr + 'h ')
        if rethrs is not None:
            createsnapstring.append('-retain ' + retHr + 'h ')
        snap_string = ".@y@@m@@d@@H@@M@@S@"
        dynamic_snap_name = snapPrefix + snap_string
        createsnapstring.append(dynamic_snap_name + ' ' + src_vol_name + '"')

        snapstring = ''.join(createsnapstring)
        schedFreq = '"' + schedFrequency + '"'

        cmd.append(snapstring)
        cmd.append(schedFreq)
        cmd.append(schedName)
        cmd.append('\r')
        err_resp = ""
        try:
            LOG.info("Creating a snapshot schedule, command is %s..." % cmd)
            resp = self.client._run(cmd)
            LOG.info("Created a snapshot schedule - command is: %s..." % cmd)
            LOG.info("Create schedule response is: %s..." % resp)

            err_resp = self.check_response(resp)
            if err_resp:
                err = (_("Create snapschedule failed Error is"
                         " '%(err_resp)s' ") %
                       {'err_resp': err_resp})
                LOG.error(err)
                raise exception.HPEDriverCreateScheduleFailed(reason=err)
        except hpeexceptions.SSHException as ex:
            LOG.error("Failed to create snapshot schedule error is %s" % ex)
            raise exception.HPEDriverCreateScheduleFailed(reason=ex)

    def force_remove_3par_schedule(self, schedule_name):
        cmd = ['removesched', '-f', '%s' % schedule_name, '\r']
        err_resp = ""
        try:
            LOG.info("Removing a snapshot schedule, command is %s..." % cmd)
            resp = self.client._run(cmd)
            LOG.info("Removed a snapshot schedule - command is: %s..." % cmd)
            LOG.info("Remove schedule response is: %s..." % resp)

            err_resp = self.check_response(resp)
            if err_resp:
                err = (_("Removing snapschedule failed. Error is"
                         " '%(err_resp)s' ") %
                       {'err_resp': err_resp})
                LOG.error(err)
                raise exception.HPEDriverRemoveScheduleFailed(reason=err)
        except hpeexceptions.SSHException as ex:
            LOG.error("Failed to remove snapshot schedule error is %s" % ex)
            raise exception.HPEDriverRemoveScheduleFailed(
                reason=ex)

    def force_remove_volume_vlun(self, vol_name):
        # Assuming that a volume for a given host would have at most
        # two VLUNs if multipath is enabled. If we support shared volume
        # in future, this function would need to be modified to delete
        # VLUN for the desired host only
        attempts = 2
        for i in range(0, attempts):
            try:
                LOG.debug("Getting VLUN for volume %s..." % vol_name)
                # Get single VLUN for the given volume so as to get
                # hold of hostname
                vol_vlun = self.client.getVLUN(vol_name)
                LOG.debug("VLUN found for volume %s..." % vol_name)
            except hpeexceptions.HTTPNotFound:
                LOG.debug("VLUN not found for volume %s..." % vol_name)
                return

            hostname = vol_vlun['hostname']

            # Now get all the VLUNs for this host
            vluns = self.client.getHostVLUNs(hostname)

            for vlun in vluns:
                # Filter vluns by volume-name
                if not vlun['active'] and vlun['volumeName'] == vol_name:
                    port_pos = vlun['portPos']

                    cmd = ['removevlun', '-f']
                    cmd.append(vol_name)
                    cmd.append(str(vlun['lun']))
                    cmd.append(hostname)
                    cmd.append('%s:%s:%s' % (port_pos['node'],
                                             port_pos['slot'],
                                             port_pos['cardPort']))
                    cmd.append('\r')
                    try:
                        LOG.info("Removing VLUN forcibly - Cmd: %s..." % cmd)
                        resp = self.client._run(cmd)
                        LOG.info("Removed VLUN forcibly - Cmd: %s..." % cmd)
                        LOG.info("Removed VLUN - Cmd Response: %s..." % resp)
                    except hpeexceptions.SSHException as ex:
                        LOG.error("Failed to remove VLUN - Cmd: %s..." % cmd)
                        LOG.error(ex)
                        raise exception.HPEDriverForceRemoveVLUNFailed(
                            reason=ex)

            # Imran: Fix for issue #153
            try:
                self.client.getHostVLUNs(hostname)
            except hpeexceptions.HTTPNotFound:
                # Since no VLUNs present for the host, remove it
                LOG.info("Removing host '%s' from 3PAR..." % hostname)
                self._delete_3par_host(hostname)
                LOG.info("Removed host '%s' from 3PAR!" % hostname)

    def delete_vlun(self, volume, hostname, is_snap):
        volume_name = utils.get_3par_name(volume['id'], is_snap)
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

    def get_snapcpg(self, volume, is_snap):
        volume_name = utils.get_3par_name(volume['id'], is_snap)
        vol = self.client.getVolume(volume_name)
        if 'snapCPG' in vol:
            return vol['snapCPG']
        return None

    def get_cpg(self, volume, is_snap, allowSnap=False):
        volume_name = utils.get_3par_name(volume['id'], is_snap)
        vol = self.client.getVolume(volume_name)
        if 'userCPG' in vol:
            return vol['userCPG']
        elif allowSnap and 'snapCPG' in vol:
            return vol['snapCPG']
        else:
            return self.src_bkend_config.hpe3par_cpg[0]
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
            if compression_val is None:
                return None

            # compression_val can be either boolean or string
            # Explicit conversion to string is done to handle both types
            compression_val_str = str(compression_val)
            if compression_val_str.lower() == 'true':
                if not compression_support:
                    msg = _('Compression is not supported on '
                            'underlying hardware')
                    LOG.error(msg)
                    raise exception.InvalidInput(reason=msg)
                return True
            else:
                return False
        return None

    def create_vvs(self, id):
        vvs_name = utils.get_3par_vvs_name(id)

        # TODO(leeantho): Choose the first CPG for now. In the future
        # support selecting different CPGs if multiple are provided.
        cpg = self.src_bkend_config.hpe3par_cpg[0]
        domain = self.get_domain(cpg)
        try:
            self.client.createVolumeSet(vvs_name, domain)
            return vvs_name
        except Exception as ex:
            raise exception.HpeCreateVvsException(ex)

    def create_volume(self, volume):
        """

        :param volume:
        :return:
        :raises:
            HPEDriverInvalidInput: This is raised when supplied provision
                type is not valid
            HPEDriverInvalidSizeForCompressedVolume: Size specified is less
                than 16GB
            HPEDriverInvalidDedupVersion: This is raised when the API version
                doesn't support de-duplication and user has supplied tdvv
                option
            HPEDriverCreateVolumeWithQosFailed:
            HPEDriverCreateVolumeWithFlashCacheFailed:
            HPEDriverVolumeAlreadyExists:
            HPEPluginException:
        """
        LOG.debug('CREATE VOLUME (%(disp_name)s: %(vol_name)s %(id)s on '
                  '%(host)s)',
                  {'disp_name': volume['display_name'],
                   'vol_name': volume['name'],
                   'id': utils.get_3par_vol_name(volume['id']),
                   'host': volume['host']})
        comments = {'volume_id': volume['id'],
                    'name': volume['name'],
                    'type': 'Docker'}

        name = volume.get('display_name', None)
        if name:
            comments['display_name'] = name

        # TODO(leeantho): Choose the first CPG for now. In the future
        # support selecting different CPGs if multiple are provided.
        if volume['cpg'] is not None:
            cpg = volume['cpg']
        else:
            # cpg = self.src_bkend_config.hpe3par_cpg[0]
            cpg = self.src_bkend_config.hpe3par_cpg[0]
            volume['cpg'] = cpg

        # check for valid provisioning type
        prov_value = volume['provisioning']
        if prov_value not in self.valid_prov_values:
            err = ("Must specify a valid provisioning type %(valid)s, "
                   "value '%(prov)s' is invalid.") %\
                {'valid': self.valid_prov_values,
                 'prov': prov_value}
            LOG.error(err)
            raise exception.HPEDriverInvalidInput(reason=err)

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
            # LOG.error(err)
            # Error message can be formatted within exception class itself
            raise exception.HPEDriverInvalidDedupVersion(
                dedup_version=DEDUP_API_VERSION,
                version=self.API_VERSION,
                reason=err)

        extras = {'comment': json.dumps(comments),
                  'tpvv': tpvv, }

        if volume['snap_cpg'] is not None:
            extras['snapCPG'] = volume['snap_cpg']
        else:
            if len(self.src_bkend_config.hpe3par_snapcpg):
                snap_cpg = self.src_bkend_config.hpe3par_snapcpg[0]
                extras['snapCPG'] = snap_cpg
                volume['snap_cpg'] = snap_cpg
            else:
                extras['snapCPG'] = cpg
                volume['snap_cpg'] = cpg

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
                # LOG.error(err)
                raise exception.HPEDriverInvalidSizeForCompressedVolume(
                    size=capacity,
                    reason=err)
        if compression is not None:
            extras['compression'] = compression

        volume_name = utils.get_3par_vol_name(volume['id'])

        try:
            self.client.createVolume(volume_name, cpg, capacity, extras)
            return volume_name
        except hpeexceptions.HTTPConflict:
            msg = _("Volume (%s) already exists on array") % volume_name
            # LOG.error(msg)
            raise exception.HPEDriverVolumeAlreadyExists(
                volume_name=volume_name,
                message=msg)
        except hpeexceptions.HTTPBadRequest as ex:
            # LOG.error("Exception: %s", ex)
            raise exception.HPEDriverInvalidInput(reason=ex.get_description())
        # except exception.InvalidInput as ex:
        #     LOG.error("Exception: %s", ex)
        #     raise
        # except exception.PluginException as ex:
        #     LOG.error("Exception: %s", ex)
        #     raise
        except Exception as ex:
            LOG.error(_LE("Exception: %s"), ex)
            raise exception.PluginException(ex)

    def delete_volume(self, volume, is_snapshot=False):
        try:
            LOG.info("DELETE_VOLUME:%(volume)s", {'volume': volume})
            if volume.get('rcg_info'):
                # this is replicated volume
                self._do_volume_replication_destroy(volume)
                LOG.info("Deletion of replicated volume:%s successful"
                         % volume)
                return

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
                    if vvset_name is not None:
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

    def _do_volume_replication_destroy(self, volume):
        rcg_info = volume.get('rcg_info')
        rcg_name = rcg_info['local_rcg_name']
        vol_name = utils.get_3par_name(volume['id'], None)
        if rcg_name:
            # TODO(sonivi): avoid volume deletion incase of failover
            # avoid volume deletion incase of switchover
            rcg_info = self.client.getRemoteCopyGroup(rcg_name)
            if rcg_info.get('role') != self.ROLE_PRIMARY:
                # it's not primary
                msg = (_("Failed to delete volume: %(vol)s as rcg: %(rcg)s do"
                         " not have valid role") % {
                             'vol': vol_name, 'rcg': rcg_name})
                LOG.error(msg)
                raise exception.InvalidRcgRoleForDeleteVolume(reason=msg)

            # stop remote copy
            try:
                LOG.info("Stopping RCG: %(rcg_name)s.", {'rcg_name': rcg_name})
                self.client.stopRemoteCopy(rcg_name)
                LOG.info("Succesfully stopped RCG: %(rcg_name)s.",
                         {'rcg_name': rcg_name})
            except Exception:
                pass

            # Remove volume from remote copy group
            # 'removeFromTarget=True' will delete volume from secondary array
            # TODO(sonivi): Handle 'removeFromTarget=False' also
            try:
                LOG.info("Removing vol:%(vol_name)s from RCG: %(rcg_name)s.",
                         {'vol_name': vol_name, 'rcg_name': rcg_name})
                self.client.removeVolumeFromRemoteCopyGroup(
                    rcg_name, vol_name, removeFromTarget=True)
                LOG.info("vol:%(vol_name)s succesfully removed from RCG: "
                         "%(rcg_name)s.",
                         {'vol_name': vol_name, 'rcg_name': rcg_name})
            except Exception as ex:
                LOG.error("%s" % six.iteritems(ex))
                pass

            # Delete volume
            try:
                LOG.info("Deleting volume:%(vol_name)s.",
                         {'vol_name': vol_name})
                self.client.deleteVolume(vol_name)
                LOG.info("Succesfully deleted volume:%(vol_name)s.",
                         {'vol_name': vol_name})
            except Exception as ex:
                msg = "Failed to delete volume: %s Error: %s" % (vol_name, ex)
                LOG.error(_LE(msg))
                raise exception.DeleteReplicatedVolumeFailed(reason=msg)

            # check whether we should delete rcg or not ?
            # it will be deleted if not volume is available in it
            rcg_info = self.client.getRemoteCopyGroup(rcg_name)
            LOG.info("Checking RCG Info:%(rcg_info)s.", {'rcg_info': rcg_info})
            if len(rcg_info.get('volumes')) == 0:
                # no volume is present so delete rcg also
                LOG.info("Deleting RCG:%(rcg_info)s.", {'rcg_info': rcg_info})
                self.client.removeRemoteCopyGroup(rcg_name)
                LOG.info("Successfully deleted RCG:%(rcg_info)s.",
                         {'rcg_info': rcg_info})
            else:
                # if other volumes are present, then start rcg
                LOG.info("Other Volumes are present in RCG:%(rcg_info)s",
                         {'rcg_info': rcg_info})
                LOG.info("Starting RCG:%(rcg_name)s.", {'rcg_name': rcg_name})
                self.client.startRemoteCopy(rcg_name)
                LOG.info("Successfully started RCG:%(rcg_name)s.",
                         {'rcg_name': rcg_name})

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

    def terminate_connection(self, volume, hostname, is_snap, wwn=None,
                             iqn=None):
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
            self.delete_vlun(volume, hostname, is_snap)
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
        self.delete_vlun(volume, hostname, is_snap)

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

    def find_existing_vlun(self, volume, host, is_snap):
        """Finds an existing VLUN for a volume on a host.

        Returns an existing VLUN's information. If no existing VLUN is found,
        None is returned.

        :param volume: A dictionary describing a volume.
        :param host: A dictionary describing a host.
        """
        existing_vlun = None
        try:
            vol_name = utils.get_3par_name(volume['id'], is_snap)
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

    def find_existing_vluns(self, volume, host, is_snap):
        existing_vluns = []
        try:
            vol_name = utils.get_3par_name(volume['id'], is_snap)
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
                # flash_cache can be either boolean or string
                # Explicit conversion to string is done to handle both types
                flash_cache_str = str(flash_cache)
                if flash_cache_str.lower() == 'true':
                    return self.client.FLASH_CACHE_ENABLED
                else:
                    return self.client.FLASH_CACHE_DISABLED

        return None

    def set_flash_cache_policy_on_vvs(self, flash_cache, vvs_name):
        flash_cache_policy = \
            self.get_flash_cache_policy(flash_cache)
        # Update virtual volume set
        if flash_cache_policy:
            try:
                self.client.modifyVolumeSet(
                    vvs_name,
                    flashCachePolicy=flash_cache_policy)
                LOG.info(_LI("Flash Cache policy set to %s"),
                         flash_cache_policy)
            except Exception as ex:
                msg = "Driver: Failed to set flash cache policy - %s" % \
                      ex
                LOG.error(_LE(msg))
                raise exception.HPEDriverSetFlashCacheOnVvsFailed(reason=msg)

    def add_volume_to_volume_set(self, vol, vvs_name):
        volume_name = utils.get_3par_vol_name(vol['id'])
        if vvs_name is not None:
            try:
                self.client.addVolumeToVolumeSet(vvs_name, volume_name)
                return volume_name
            except Exception as ex:
                msg = _("Failed to add volume to VV set %s - %s.") %\
                       (vvs_name, ex)
                LOG.error(msg)
                raise exception.HPEDriverAddVvToVvSetFailed(ex)

    def remove_volume_from_volume_set(self, vol_name, vvs_name):
        # TODO: Exception handling might be required here
        self.client.removeVolumeFromVolumeSet(vvs_name, vol_name)

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

            optional = {'comment': json.dumps(extra)}
            if snapshot['expirationHours']:
                optional['expirationHours'] = snapshot['expirationHours']
            if snapshot['retentionHours']:
                optional['retentionHours'] = snapshot['retentionHours']

            self.client.createSnapshot(snap_name, vol_name, optional)
            return snap_name
        except hpeexceptions.HTTPForbidden as ex:
            LOG.error("Exception: %s", ex)
            raise exception.NotAuthorized()
        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.PluginException(ex)

    def create_cloned_volume(self, dst_volume, src_vref):
        LOG.info("Create clone of volume\n%s", json.dumps(src_vref, indent=2))
        try:
            dst_3par_vol_name = utils.get_3par_vol_name(dst_volume['id'])
            src_3par_vol_name = utils.get_3par_vol_name(src_vref['id'])
            # back_up_process = False
            vol_chap_enabled = False

            # Check whether a volume is ISCSI and CHAP enabled on it.
            if self.src_bkend_config.hpe3par_iscsi_chap_enabled:
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
                if 'cpg' in dst_volume:
                    cpg = dst_volume['cpg']
                if 'snap_cpg' in dst_volume:
                    snap_cpg = dst_volume['snap_cpg']

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
                    # compression_val can be either boolean or string
                    # conversion to string is done to handle both types
                    compression_val_str = str(compression_val)
                    compression = (compression_val_str.lower() == 'true')

                # make the 3PAR copy the contents.
                # can't delete the original until the copy is done.
                self._copy_volume(src_3par_vol_name, dst_3par_vol_name,
                                  cpg=cpg, snap_cpg=snap_cpg,
                                  tpvv=tpvv, tdvv=tdvv,
                                  compression=compression)
                return dst_3par_vol_name
            else:
                # The size of the new volume is different, so we have to
                # copy the volume and wait.  Do the resize after the copy
                # is complete.
                LOG.debug("Creating a clone of volume, using offline copy.")

                # we first have to create the destination volume
                self.create_volume(dst_volume)

                optional = {'priority': 1}
                self.client.copyVolume(src_3par_vol_name,
                                       dst_3par_vol_name, None,
                                       optional=optional)

                comments = {'volume_id': dst_volume['id'],
                            'name': dst_volume['name'],
                            'type': 'Docker'}

                name = dst_volume.get('display_name', None)
                if name:
                    comments['display_name'] = name

                self.client.modifyVolume(dst_3par_vol_name,
                                         {'comment': json.dumps(comments)})
                return dst_3par_vol_name

        except hpeexceptions.HTTPForbidden:
            raise exception.NotAuthorized()
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

    def get_snapshots_by_vol(self, vol_id, snap_cpg):
        bkend_vol_name = utils.get_3par_vol_name(vol_id)
        LOG.debug("Querying snapshots for %s in %s cpg "
                  % (bkend_vol_name, snap_cpg))
        return self.client.getSnapshotsOfVolume(snap_cpg, bkend_vol_name)

    def delete_vvset(self, id):
        vvset_name = utils.get_3par_vvs_name(id)
        self.client.deleteVolumeSet(vvset_name)

    def get_rcg(self, rcg_name):
        try:
            rcg = self.client.getRemoteCopyGroup(rcg_name)
            return rcg
        except hpeexceptions.HTTPNotFound:
            raise exception.HPEDriverRemoteCopyGroupNotFound(name=rcg_name)

    def add_volume_to_rcg(self, **kwargs):
        bkend_vol_name = kwargs['bkend_vol_name']
        rcg_name = kwargs['rcg_name']

        # Add volume to remote copy group.
        rcg_targets = []
        rcg_target = {'targetName': self.tgt_bkend_config.backend_id,
                      'secVolumeName': bkend_vol_name}
        rcg_targets.append(rcg_target)
        optional = {'volumeAutoCreation': True}
        try:
            rcg = self.get_rcg(rcg_name)
            original_rcg_state = rcg['targets'][0]['state']
            if original_rcg_state == self.RCG_STARTED:
                LOG.info("Stopping remote copy group: %s..." % rcg_name)
                self.client.stopRemoteCopy(rcg_name)
                LOG.info("Remote copy group stopped: %s" % rcg_name)
            else:
                LOG.info("Remote copy group %s was in stopped state. However"
                         "after adding volume to it, it will be started"
                         % rcg_name)
            self.client.addVolumeToRemoteCopyGroup(rcg_name, bkend_vol_name,
                                                   rcg_targets,
                                                   optional=optional)
            LOG.info("Starting remote copy group: %s..." % rcg_name)
            self.client.startRemoteCopy(rcg_name)
            LOG.info("Remote copy group started: %s" % rcg_name)
        except Exception as ex:
            msg = (_("Error occurred while adding volume '%s' to the remote "
                     "copy group '%s': %s") % (bkend_vol_name, rcg_name,
                                               six.text_type(ex)))
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

    def remove_volume_from_rcg(self, **kwargs):
        bkend_vol_name = kwargs['bkend_vol_name']
        rcg_name = kwargs['rcg_name']
        try:
            self.client.removeVolumeFromRemoteCopyGroup(rcg_name,
                                                        bkend_vol_name)
        except Exception as ex:
            msg = (_("Error occurred while removing volume '%s' from the "
                     "remote copy group '%s': %s") %
                   (bkend_vol_name, rcg_name, six.text_type(ex)))
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

    def _get_backend_replication_mode(self, mode):
        mode_map = {
            'synchronous': self.SYNC,
            'asynchronous': self.PERIODIC,
            'streaming': self.STREAMING}
        ret_mode = mode_map.get(mode)
        return ret_mode

    def create_rcg(self, **kwargs):
        rcg_name = kwargs['rcg_name']
        LOG.info("Creating RCG %s..." % rcg_name)
        src_config = self.src_bkend_config
        tgt_config = self.tgt_bkend_config
        bkend_replication_mode = self._get_backend_replication_mode(
            tgt_config.replication_mode)

        cpg = tgt_config.hpe3par_cpg
        if isinstance(cpg, list):
            cpg = cpg[0]

        snap_cpg = tgt_config.hpe3par_snapcpg
        if isinstance(snap_cpg, list):
            snap_cpg = snap_cpg[0]
        rcg_target = {'targetName': tgt_config.backend_id,
                      'mode': bkend_replication_mode,
                      'snapCPG': snap_cpg,
                      'userCPG': cpg}
        rcg_targets = [rcg_target]

        src_cpg = src_config.hpe3par_cpg
        if isinstance(src_cpg, list):
            src_cpg = src_cpg[0]

        src_snap_cpg = src_config.hpe3par_snapcpg
        if isinstance(src_snap_cpg, list):
            src_snap_cpg = src_snap_cpg[0]

        optional = {'localSnapCPG': src_snap_cpg,
                    'localUserCPG': src_cpg}

        domain = self.get_domain(src_cpg)
        if domain:
            optional['domain'] = domain
        try:
            LOG.info("Creating remote copy group: %s..." % rcg_name)
            self.client.createRemoteCopyGroup(rcg_name, rcg_targets,
                                              optional)
            LOG.info("Remote copy group successfully created: %s!" % rcg_name)
        except Exception as ex:
            msg = "Error encountered while creating remote copy group: %s" %\
                  six.text_type(ex)
            LOG.error(msg)
            raise exception.HPERemoteCopyGroupBackendAPIException(data=msg)

        if tgt_config.quorum_witness_ip:
            pp_params = {'targets': [
                {'targetName': tgt_config.backend_id,
                 'policies': {'autoFailover': True,
                              'pathManagement': True,
                              # TODO: Check if this is required
                              'autoRecover': True}}]}
            try:
                self.client.modifyRemoteCopyGroup(rcg_name, pp_params)
            except Exception as ex:
                msg = "Error encountered while modifying remote copy group"\
                      "%s: %s" % (rcg_name, six.text_type(ex))
                LOG.error(msg)
                raise exception.HPERemoteCopyGroupBackendAPIException(data=msg)

        else:
            if bkend_replication_mode == self.PERIODIC or \
                    bkend_replication_mode == self.STREAMING:
                if tgt_config.sync_period:
                    sync_period = int(tgt_config.sync_period)
                else:
                    sync_period = self.DEFAULT_SYNC_PERIOD

                sync_target = {'targetName': tgt_config.backend_id,
                               'syncPeriod': sync_period}

                opt = {'targets': [sync_target]}
                try:
                    self.client.modifyRemoteCopyGroup(rcg_name, opt)
                except Exception as ex:
                    msg = "Error encountered while setting the sync period "\
                          "for the remote copy group: %s" % six.text_type(ex)
                    LOG.error(msg)
                    raise exception.HPERemoteCopyGroupBackendAPIException(
                        data=msg)

        try:
            rcg = self.client.getRemoteCopyGroup(rcg_name)
            ret_val = {'local_rcg_name': rcg_name,
                       'remote_rcg_name': rcg['remoteGroupName']}
            return ret_val

        except Exception as ex:
            msg = "Error encountered while fetching the remote copy "\
                  "group after its creation: %s" % six.text_type(ex)
            LOG.error(msg)
            raise exception.HPERemoteCopyGroupBackendAPIException(data=msg)

    def delete_rcg(self, **kwargs):
        rcg_name = kwargs['rcg_name']
        try:
            LOG.info("Deleting remote copy group: %s..." % rcg_name)
            self.client.removeRemoteCopyGroup(rcg_name)
            LOG.info("Remote copy group deleted: %s!" % rcg_name)
        except Exception as ex:
            msg = (_("Error occurred while removing the "
                     "remote copy group '%s': %s") %
                   (rcg_name, six.text_type(ex)))
            LOG.error(msg)
            raise exception.HPERemoteCopyGroupBackendAPIException(data=msg)

    def is_vol_having_active_task(self, vol_name):
        return self.client.isOnlinePhysicalCopy(vol_name)
