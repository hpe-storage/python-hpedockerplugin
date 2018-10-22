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

"""
Volume driver for HPE 3PAR Storage array.
This driver requires 3.1.3 firmware on the 3PAR array, using
the 4.x version of the hpe3parclient.
You will need to install the python hpe3parclient.
sudo pip install --upgrade "hpe3parclient>=4.0"
Set the following in the hpe.conf file to enable the
3PAR iSCSI Driver along with the required flags:
hpedockerplugin_driver = hpe.hpe_3par_iscsi.HPE3PARISCSIDriver
"""

import re
import sys

try:
    from hpe3parclient import exceptions as hpeexceptions
except ImportError:
    hpeexceptions = None

from oslo_log import log as logging
import six

from hpedockerplugin import exception
from hpedockerplugin.i18n import _, _LW

from hpedockerplugin.hpe import hpe_3par_common as hpecommon
from hpedockerplugin.hpe import utils as volume_utils

LOG = logging.getLogger(__name__)
DEFAULT_ISCSI_PORT = 3260
CHAP_USER_KEY = "HPQ-docker-CHAP-name"
CHAP_PASS_KEY = "HPQ-docker-CHAP-secret"

"""
Need to make sure strict_ssh_host_key_policy and ssh_hosts_key_file
get registered before hpe_3par_common is called
"""


class HPE3PARISCSIDriver(object):
    """OpenStack iSCSI driver to enable 3PAR storage array.
    Version history:
    .. code-block:: none
        0.0.1 - Initial version of the 3PAR iSCSI driver created.
        0.0.2 - Added support for CHAP.
    """

    VERSION = "0.0.2"

    def __init__(self, host_config, src_bkend_config,
                 tgt_bkend_config=None):

        self._host_config = host_config
        self.configuration = src_bkend_config

        # Get source and target backend configs as separate dictionaries
        self.src_bkend_config = src_bkend_config
        self.tgt_bkend_config = tgt_bkend_config

    def _init_common(self):
        return hpecommon.HPE3PARCommon(self._host_config,
                                       self.src_bkend_config,
                                       self.tgt_bkend_config)

    def _login(self):
        common = self._init_common()
        common.do_setup()
        common.client_login()
        return common

    def _logout(self, common):
        common.client_logout()

    def _check_flags(self, common):
        """Sanity check to ensure we have required options set."""
        required_flags = ['hpe3par_api_url', 'hpe3par_username',
                          'hpe3par_password', 'san_ip', 'san_login',
                          'san_password']
        common.check_flags(self.src_bkend_config, required_flags)

    def do_setup(self, timeout):
        common = self._init_common()
        common.do_setup(timeout=timeout)
        self._check_flags(common)
        common.check_for_setup_error()

        common.client_login()
        try:
            self.initialize_iscsi_ports(common)
        finally:
            self._logout(common)

    def initialize_iscsi_ports(self, common):
        # map iscsi_ip-> ip_port
        #             -> iqn
        #             -> nsp
        self.iscsi_ips = {}
        temp_iscsi_ip = {}

        # use the 3PAR ip_addr list for iSCSI configuration
        if len(self.configuration.hpe3par_iscsi_ips) > 0:
            # add port values to ip_addr, if necessary
            for ip_addr in self.configuration.hpe3par_iscsi_ips:
                ip = ip_addr.split(':')
                if len(ip) == 1:
                    temp_iscsi_ip[ip_addr] = {'ip_port': DEFAULT_ISCSI_PORT}
                elif len(ip) == 2:
                    temp_iscsi_ip[ip[0]] = {'ip_port': ip[1]}
                else:
                    LOG.warning(_LW("Invalid IP address format '%s'"), ip_addr)

        # add the single value iscsi_ip_address option to the IP dictionary.
        # This way we can see if it's a valid iSCSI IP. If it's not valid,
        # we won't use it and won't bother to report it, see below
        if (self.configuration.iscsi_ip_address not in temp_iscsi_ip):
            ip = self.configuration.iscsi_ip_address
            ip_port = self.configuration.iscsi_port
            temp_iscsi_ip[ip] = {'ip_port': ip_port}

        # get all the valid iSCSI ports from 3PAR
        # when found, add the valid iSCSI ip, ip port, iqn and nsp
        # to the iSCSI IP dictionary
        iscsi_ports = common.get_active_iscsi_target_ports()

        for port in iscsi_ports:
            ip = port['IPAddr']
            if ip in temp_iscsi_ip:
                ip_port = temp_iscsi_ip[ip]['ip_port']
                self.iscsi_ips[ip] = {'ip_port': ip_port,
                                      'nsp': port['nsp'],
                                      'iqn': port['iSCSIName']
                                      }
                del temp_iscsi_ip[ip]

        # if the single value iscsi_ip_address option is still in the
        # temp dictionary it's because it defaults to $my_ip which doesn't
        # make sense in this context. So, if present, remove it and move on.
        if (self.configuration.iscsi_ip_address in temp_iscsi_ip):
            del temp_iscsi_ip[self.configuration.iscsi_ip_address]

        # lets see if there are invalid iSCSI IPs left in the temp dict
        if len(temp_iscsi_ip) > 0:
            LOG.warning(_LW("Found invalid iSCSI IP address(s) in "
                            "configuration option(s) hpe3par_iscsi_ips or "
                            "iscsi_ip_address '%s.'"),
                        (", ".join(temp_iscsi_ip)))

        if not len(self.iscsi_ips) > 0:
            msg = _('At least one valid iSCSI IP address must be set.')
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)

    def check_for_setup_error(self):
        """Setup errors are already checked for in do_setup so return pass."""
        pass

    def create_volume(self, volume):
        common = self._login()
        try:
            return common.create_volume(volume)
        finally:
            self._logout(common)

    def delete_volume(self, volume, is_snapshot=False):
        common = self._login()
        try:
            common.delete_volume(volume, is_snapshot)
        finally:
            self._logout(common)

    def get_snapcpg(self, volume, is_snap):
        common = self._login()
        try:
            return common.get_snapcpg(volume, is_snap)
        finally:
            self._logout(common)

    def get_cpg(self, volume, is_snap, allowSnap=False):
        common = self._login()
        try:
            return common.get_cpg(volume, is_snap, allowSnap)
        finally:
            self._logout(common)

    def initialize_connection(self, volume, connector, is_snap):
        """Assigns the volume to a server.
        Assign any created volume to a compute node/host so that it can be
        used from that host.
        This driver returns a driver_volume_type of 'iscsi'.
        The format of the driver data is defined in _get_iscsi_properties.
        Example return value:
            {
                'driver_volume_type': 'iscsi'
                'data': {
                    'encrypted': False,
                    'target_discovered': True,
                    'target_iqn': 'iqn.2010-10.org.openstack:volume-00000001',
                    'target_protal': '127.0.0.1:3260',
                    'volume_id': 1,
                }
            }
        Steps to export a volume on 3PAR
          * Get the 3PAR iSCSI iqn
          * Create a host on the 3par
          * create vlun on the 3par
        """
        common = self._login()
        try:
            # we have to make sure we have a host
            host, username, password = self._create_host(
                common,
                volume,
                connector, is_snap)

            if connector['multipath']:
                ready_ports = common.client.getiSCSIPorts(
                    state=common.client.PORT_STATE_READY)

                target_portals = []
                target_iqns = []
                target_luns = []

                # Target portal ips are defined in hpe.conf.
                target_portal_ips = self.iscsi_ips.keys()

                # Collect all existing VLUNs for this volume/host combination.
                existing_vluns = common.find_existing_vluns(volume, host,
                                                            is_snap)

                # Cycle through each ready iSCSI port and determine if a new
                # VLUN should be created or an existing one used.
                lun_id = None
                for port in ready_ports:
                    iscsi_ip = port['IPAddr']
                    if iscsi_ip in target_portal_ips:
                        vlun = None
                        # check for an already existing VLUN matching the
                        # nsp for this iSCSI IP. If one is found, use it
                        # instead of creating a new VLUN.
                        for v in existing_vluns:
                            portPos = common.build_portPos(
                                self.iscsi_ips[iscsi_ip]['nsp'])
                            if v['portPos'] == portPos:
                                vlun = v
                                break
                        else:
                            vlun = common.create_vlun(
                                volume, host, is_snap,
                                self.iscsi_ips[iscsi_ip]['nsp'],
                                lun_id=lun_id)
                            # We want to use the same LUN ID  for every port
                            lun_id = vlun['lun']
                        iscsi_ip_port = "%s:%s" % (
                            iscsi_ip, self.iscsi_ips[iscsi_ip]['ip_port'])
                        target_portals.append(iscsi_ip_port)
                        target_iqns.append(port['iSCSIName'])
                        target_luns.append(vlun['lun'])
                    else:
                        LOG.warning(_LW("iSCSI IP: '%s' was not found in "
                                        "hpe3par_iscsi_ips list defined in "
                                        "hpe.conf."), iscsi_ip)

                info = {'driver_volume_type': 'iscsi',
                        'data': {'target_portals': target_portals,
                                 'target_iqns': target_iqns,
                                 'target_luns': target_luns,
                                 'target_discovered': True
                                 }
                        }
            else:
                least_used_nsp = None

                # check if a VLUN already exists for this host
                existing_vlun = common.find_existing_vlun(volume, host,
                                                          is_snap)

                if existing_vlun:
                    # We override the nsp here on purpose to force the
                    # volume to be exported out the same IP as it already is.
                    # This happens during nova live-migration, we want to
                    # disable the picking of a different IP that we export
                    # the volume to, or nova complains.
                    least_used_nsp = common.build_nsp(existing_vlun['portPos'])

                if not least_used_nsp:
                    least_used_nsp = self._get_least_used_nsp_for_host(
                        common,
                        host['name'])

                vlun = None
                if existing_vlun is None:
                    # now that we have a host, create the VLUN
                    vlun = common.create_vlun(volume, host, is_snap,
                                              least_used_nsp)
                else:
                    vlun = existing_vlun

                if least_used_nsp is None:
                    LOG.warning(_LW("Least busy iSCSI port not found, "
                                    "using first iSCSI port in list."))
                    iscsi_ip = list(self.iscsi_ips.keys())[0]
                else:
                    iscsi_ip = self._get_ip_using_nsp(least_used_nsp)

                iscsi_ip_port = self.iscsi_ips[iscsi_ip]['ip_port']
                iscsi_target_iqn = self.iscsi_ips[iscsi_ip]['iqn']
                info = {'driver_volume_type': 'iscsi',
                        'data': {'target_portal': "%s:%s" %
                                 (iscsi_ip, iscsi_ip_port),
                                 'target_iqn': iscsi_target_iqn,
                                 'target_lun': vlun['lun'],
                                 'target_discovered': True
                                 }
                        }

            if self.configuration.hpe3par_iscsi_chap_enabled:
                info['data']['auth_method'] = 'CHAP'
                info['data']['auth_username'] = username
                info['data']['auth_password'] = password

            encryption_key_id = volume.get('encryption_key_id', None)
            info['data']['encrypted'] = encryption_key_id is not None

            return info
        finally:
            self._logout(common)

    def terminate_connection(self, volume, connector, is_snap, **kwargs):
        """Driver entry point to unattach a volume from an instance."""
        common = self._login()
        try:
            hostname = common._safe_hostname(connector['host'])
            common.terminate_connection(
                volume,
                hostname,
                is_snap,
                iqn=connector['initiator'])
            self._clear_chap_3par(common, volume, is_snap)
        finally:
            self._logout(common)

    def _clear_chap_3par(self, common, volume, is_snap):
        """Clears CHAP credentials on a 3par volume.
        Ignore exceptions caused by the keys not being present on a volume.
        """
        vol_name = volume_utils.get_3par_name(volume['id'], is_snap)

        try:
            common.client.removeVolumeMetaData(vol_name, CHAP_USER_KEY)
        except hpeexceptions.HTTPNotFound:
            pass
        except Exception:
            raise

        try:
            common.client.removeVolumeMetaData(vol_name, CHAP_PASS_KEY)
        except hpeexceptions.HTTPNotFound:
            pass
        except Exception:
            raise

    def _create_3par_iscsi_host(self, common, hostname, iscsi_iqn, domain,
                                persona_id):
        """Create a 3PAR host.
        Create a 3PAR host, if there is already a host on the 3par using
        the same iqn but with a different hostname, return the hostname
        used by 3PAR.
        """
        # first search for an existing host
        host_found = None
        hosts = common.client.queryHost(iqns=[iscsi_iqn])

        if hosts and hosts['members'] and 'name' in hosts['members'][0]:
            host_found = hosts['members'][0]['name']

        if host_found is not None:
            return host_found
        else:
            if isinstance(iscsi_iqn, six.string_types):
                iqn = [iscsi_iqn]
            else:
                iqn = iscsi_iqn
            persona_id = int(persona_id)
            common.client.createHost(hostname, iscsiNames=iqn,
                                     optional={'domain': domain,
                                               'persona': persona_id})
            return hostname

    def _modify_3par_iscsi_host(self, common, hostname, iscsi_iqn):
        mod_request = {'pathOperation': common.client.HOST_EDIT_ADD,
                       'iSCSINames': [iscsi_iqn]}

        common.client.modifyHost(hostname, mod_request)

    def _set_3par_chaps(self, common, hostname, volume, username, password):
        """Sets a 3PAR host's CHAP credentials."""
        if not self.configuration.hpe3par_iscsi_chap_enabled:
            return

        mod_request = {'chapOperation': common.client.HOST_EDIT_ADD,
                       'chapOperationMode': common.client.CHAP_INITIATOR,
                       'chapName': username,
                       'chapSecret': password}
        common.client.modifyHost(hostname, mod_request)

    def _create_host(self, common, volume, connector, is_snap):
        """Creates or modifies existing 3PAR host."""
        # make sure we don't have the host already
        host = None
        username = None
        password = None
        hostname = common._safe_hostname(connector['host'])
        cpg = common.get_cpg(volume, is_snap, allowSnap=True)
        domain = common.get_domain(cpg)

        # Get the CHAP secret if CHAP is enabled
        if self.configuration.hpe3par_iscsi_chap_enabled:
            vol_name = volume_utils.get_3par_name(volume['id'], is_snap)
            username = common.client.getVolumeMetaData(
                vol_name, CHAP_USER_KEY)['value']
            password = common.client.getVolumeMetaData(
                vol_name, CHAP_PASS_KEY)['value']

        try:
            host = common._get_3par_host(hostname)
        except hpeexceptions.HTTPNotFound:
            # get persona from the volume type extra specs
            persona_id = 2
            # host doesn't exist, we have to create it
            hostname = self._create_3par_iscsi_host(common,
                                                    hostname,
                                                    connector['initiator'],
                                                    domain,
                                                    persona_id)
        else:
            if 'iSCSIPaths' not in host or len(host['iSCSIPaths']) < 1:
                self._modify_3par_iscsi_host(
                    common, hostname,
                    connector['initiator'])
            elif (not host['initiatorChapEnabled'] and
                    self.configuration.hpe3par_iscsi_chap_enabled):
                LOG.warning(_LW("Host exists without CHAP credentials set and "
                                "has iSCSI attachments but CHAP is enabled. "
                                "Updating host with new CHAP credentials."))

        self._set_3par_chaps(common, hostname, volume, username, password)
        host = common._get_3par_host(hostname)
        return host, username, password

    def _do_export(self, common, volume, connector, is_snap):
        """Gets the associated account, generates CHAP info and updates."""
        model_update = {}

        if not self.configuration.hpe3par_iscsi_chap_enabled:
            model_update['provider_auth'] = None
            return model_update

        # CHAP username will be the hostname
        chap_username = connector['host']

        chap_password = None
        try:
            # Get all active VLUNs for the host
            vluns = common.client.getHostVLUNs(chap_username)

            # Host has active VLUNs... is CHAP enabled on host?
            host_info = common.client.getHost(chap_username)

            if not host_info['initiatorChapEnabled']:
                LOG.warning(_LW("Host has no CHAP key, but CHAP is enabled."))

        except hpeexceptions.HTTPNotFound:
            chap_password = volume_utils.generate_password(16)
            LOG.warning(_LW("No host or VLUNs exist. Generating new "
                            "CHAP key."))
        else:
            # Get a list of all iSCSI VLUNs and see if there is already a CHAP
            # key assigned to one of them.  Use that CHAP key if present,
            # otherwise create a new one.  Skip any VLUNs that are missing
            # CHAP credentials in metadata.
            chap_exists = False
            active_vluns = 0

            for vlun in vluns:
                if not vlun['active']:
                    continue

                active_vluns += 1

                # iSCSI connections start with 'iqn'.
                if ('remoteName' in vlun and
                        re.match('iqn.*', vlun['remoteName'])):
                    try:
                        chap_password = common.client.getVolumeMetaData(
                            vlun['volumeName'], CHAP_PASS_KEY)['value']
                        chap_exists = True
                        break
                    except hpeexceptions.HTTPNotFound:
                        LOG.debug("The VLUN %s is missing CHAP credentials "
                                  "but CHAP is enabled. Skipping.",
                                  vlun['remoteName'])
                else:
                    LOG.warning(_LW("Non-iSCSI VLUN detected."))

            if not chap_exists:
                chap_password = volume_utils.generate_password(16)
                LOG.warning(_LW("No VLUN contained CHAP credentials. "
                                "Generating new CHAP key."))

        # Add CHAP credentials to the volume metadata
        vol_name = volume_utils.get_3par_name(volume['id'], is_snap)
        common.client.setVolumeMetaData(
            vol_name, CHAP_USER_KEY, chap_username)
        common.client.setVolumeMetaData(
            vol_name, CHAP_PASS_KEY, chap_password)

        model_update['provider_auth'] = ('CHAP %s %s' %
                                         (chap_username, chap_password))

        return model_update

    def create_export(self, volume, connector, is_snap):
        common = self._login()
        try:
            return self._do_export(common, volume, connector, is_snap)
        finally:
            self._logout(common)

    def _get_least_used_nsp_for_host(self, common, hostname):
        """Get the least used NSP for the current host.
        Steps to determine which NSP to use.
            * If only one iSCSI NSP, return it
            * If there is already an active vlun to this host, return its NSP
            * Return NSP with fewest active vluns
        """

        iscsi_nsps = self._get_iscsi_nsps()
        # If there's only one path, use it
        if len(iscsi_nsps) == 1:
            return iscsi_nsps[0]

        # Try to reuse an existing iscsi path to the host
        vluns = common.client.getVLUNs()
        for vlun in vluns['members']:
            if vlun['active']:
                if vlun['hostname'] == hostname:
                    temp_nsp = common.build_nsp(vlun['portPos'])
                    if temp_nsp in iscsi_nsps:
                        # this host already has an iscsi path, so use it
                        return temp_nsp

        # Calculate the least used iscsi nsp
        least_used_nsp = self._get_least_used_nsp(common,
                                                  vluns['members'],
                                                  self._get_iscsi_nsps())
        return least_used_nsp

    def _get_iscsi_nsps(self):
        """Return the list of candidate nsps."""
        nsps = []
        for value in self.iscsi_ips.values():
            nsps.append(value['nsp'])
        return nsps

    def _get_ip_using_nsp(self, nsp):
        """Return IP associated with given nsp."""
        for (key, value) in self.iscsi_ips.items():
            if value['nsp'] == nsp:
                return key

    def _get_least_used_nsp(self, common, vluns, nspss):
        """Return the nsp that has the fewest active vluns."""
        # return only the nsp (node:server:port)
        # count the number of nsps
        nsp_counts = {}
        for nsp in nspss:
            # initialize counts to zero
            nsp_counts[nsp] = 0

        current_least_used_nsp = None

        for vlun in vluns:
            if vlun['active']:
                nsp = common.build_nsp(vlun['portPos'])
                if nsp in nsp_counts:
                    nsp_counts[nsp] = nsp_counts[nsp] + 1

        # identify key (nsp) of least used nsp
        current_smallest_count = sys.maxsize
        for (nsp, count) in nsp_counts.items():
            if count < current_smallest_count:
                current_least_used_nsp = nsp
                current_smallest_count = count

        return current_least_used_nsp

    def create_snapshot(self, snapshot):
        common = self._login()
        try:
            return common.create_snapshot(snapshot)
        finally:
            self._logout(common)

    def revert_snap_to_vol(self, volume, snapshot):
        common = self._login()
        try:
            common.revert_snap_to_vol(volume, snapshot)
        finally:
            self._logout(common)

    def create_cloned_volume(self, volume, src_vref):
        common = self._login()
        try:
            return common.create_cloned_volume(volume, src_vref)
        finally:
            self._logout(common)

    def get_snapshots_by_vol(self, vol_id, snp_cpg):
        common = self._login()
        try:
            return common.get_snapshots_by_vol(vol_id, snp_cpg)
        finally:
            self._logout(common)

    def get_qos_detail(self, vvset):
        common = self._login()
        try:
            return common.get_qos_detail(vvset)
        finally:
            self._logout(common)

    def get_vvset_detail(self, vvset):
        common = self._login()
        try:
            return common.get_vvset_detail(vvset)
        finally:
            self._logout(common)

    def get_vvset_from_volume(self, volume):
        common = self._login()
        try:
            return common.get_vvset_from_volume(volume)
        finally:
            self._logout(common)

    def get_volume_detail(self, volume):
        common = self._login()
        try:
            return common.get_volume_detail(volume)
        finally:
            self._logout(common)

    def manage_existing(self, volume, existing_ref_details, is_snap=False,
                        target_vol_name=None, comment=None):
        common = self._login()
        try:
            return common.manage_existing(
                volume, existing_ref_details, is_snap=is_snap,
                target_vol_name=target_vol_name, comment=comment)
        finally:
            self._logout(common)

    def create_vvs(self, id):
        common = self._login()
        try:
            return common.create_vvs(id)
        finally:
            self._logout(common)

    def delete_vvset(self, id):
        common = self._login()
        try:
            return common.delete_vvset(id)
        finally:
            self._logout(common)

    def add_volume_to_volume_set(self, vol, vvs_name):
        common = self._login()
        try:
            return common.add_volume_to_volume_set(vol, vvs_name)
        finally:
            self._logout(common)

    def remove_volume_from_volume_set(self, vol_name, vvs_name):
        common = self._login()
        try:
            return common.remove_volume_from_volume_set(vol_name, vvs_name)
        finally:
            self._logout(common)

    def set_flash_cache_policy_on_vvs(self, flash_cache, vvs_name):
        common = self._login()
        try:
            return common.set_flash_cache_policy_on_vvs(flash_cache,
                                                        vvs_name)
        finally:
            self._logout(common)

    def force_remove_volume_vlun(self, vol_name):
        common = self._login()
        try:
            return common.force_remove_volume_vlun(vol_name)
        finally:
            self._logout(common)

    def add_volume_to_rcg(self, **kwargs):
        common = self._login()
        try:
            return common.add_volume_to_rcg(**kwargs)
        finally:
            self._logout(common)

    def remove_volume_from_rcg(self, **kwargs):
        common = self._login()
        try:
            return common.remove_volume_from_rcg(**kwargs)
        finally:
            self._logout(common)

    def create_rcg(self, **kwargs):
        common = self._login()
        try:
            return common.create_rcg(**kwargs)
        finally:
            self._logout(common)

    def delete_rcg(self, **kwargs):
        common = self._login()
        try:
            return common.delete_rcg(**kwargs)
        finally:
            self._logout(common)

    def force_remove_3par_schedule(self, schedule_name):
        common = self._login()
        try:
            return common.force_remove_3par_schedule(schedule_name)
        finally:
            self._logout(common)

    def create_snap_schedule(self, src_vol_name, schedName, snapPrefix,
                             exphrs, rethrs, schedFrequency):
        common = self._login()
        try:
            return common.create_snap_schedule(src_vol_name, schedName,
                                               snapPrefix, exphrs, rethrs,
                                               schedFrequency)
        finally:
            self._logout(common)

    def get_rcg(self, rcg_name):
        common = self._login()
        try:
            return common.get_rcg(rcg_name)
        finally:
            self._logout(common)

    def is_vol_having_active_task(self, vol_name):
        common = self._login()
        try:
            return common.is_vol_having_active_task(vol_name)
        finally:
            self._logout(common)

    def get_domain(self, cpg_name):
        common = self._login()
        try:
            return common.get_domain(cpg_name)
        finally:
            self._logout(common)
