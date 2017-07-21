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
3PAR FC Driver along with the required flags:

hpedockerplugin_driver = hpe.hpe_3par_fc.HPE3PARFCDriver
"""


try:
    from hpe3parclient import exceptions as hpeexceptions
except ImportError:
    hpeexceptions = None

from oslo_log import log as logging

from hpedockerplugin import exception
from hpedockerplugin.i18n import _, _LI, _LW, _LE

from hpedockerplugin.hpe import hpe_3par_common as hpecommon

from hpedockerplugin.hpe import utils
from hpedockerplugin.hpe import san_driver

class HPE3PARFCDRIVER(object):
    """OpenStack iSCSI driver to enable 3PAR storage array.

      Version history:

    """

    VERSION = "1.0"


    def __init__(self, hpe3parconfig):
        self.hpe3parconfig = hpe3parconfig
        self.configuration = hpe3parconfig
        self.configuration.append_config_values(hpecommon.hpe3par_opts)

        self.hpe3parconfig.append_config_values(san_driver.san_opts)
        self.hpe3parconfig.append_config_values(san_driver.volume_opts)


    def _init_common(self):
        return hpecommon.HPE3PARCommon(self.configuration)

    def _login(self):
        common = self._init_common()
        common.do_setup()
        common.client_login()
        return common


    def _logout(self, common):
        common.client_logout()


    def _check_flags(self, common):
        required_flags = ['hpe3par_api_url', 'hpe3par_username',
                          'hpe3par_password', 'san_ip', 'san_login',
                          'san_password']
        common.check_flags(self.configuration, required_flags)

    def do_setup(self):
        common = self._init_common()
        common.do_setup()
        self._check_flags(common)
        common.check_for_setup_error()



    def check_for_setup_error(self):
        """Setup errors are already checked for in do_setup so return pass."""
        pass

    def create_volume(self, volume):
        common = self._login()
        try:
            return common.create_volume(volume)
        finally:
            self._logout(common)

    def delete_volume(self, volume):
        common = self._login()
        try:
            common.delete_volume(volume)
        finally:
            self._logout(common)


    def initialize_connection(self, volume, connector):
        """Assigns the volume to a server.

        Assign any created volume to a compute node/host so that it can be
        used from that host.

        The  driver returns a driver_volume_type of 'fibre_channel'.
        The target_wwn can be a single entry or a list of wwns that
        correspond to the list of remote wwn(s) that will export the volume.
        Example return values:

            {
                'driver_volume_type': 'fibre_channel'
                'data': {
                    'encrypted': False,
                    'target_discovered': True,
                    'target_lun': 1,
                    'target_wwn': '1234567890123',
                }
            }

            or

             {
                'driver_volume_type': 'fibre_channel'
                'data': {
                    'encrypted': False,
                    'target_discovered': True,
                    'target_lun': 1,
                    'target_wwn': ['1234567890123', '0987654321321'],
                }
            }


        Steps to export a volume on 3PAR
          * Create a host on the 3par with the target wwn
          * Create a VLUN for that HOST with the volume we want to export.

        """
        common = self._login()
        try:
            # we have to make sure we have a host
            host = self._create_host(common, volume, connector)
            target_wwns, init_targ_map, numPaths = \
                self._build_initiator_target_map(common, connector)
            # check if a VLUN already exists for this host
            existing_vlun = common.find_existing_vlun(volume, host)

            vlun = None
            if existing_vlun is None:
                # now that we have a host, create the VLUN
                nsp = None
                lun_id = None
                active_fc_port_list = common.get_active_fc_target_ports()

                init_targ_map.clear()
                del target_wwns[:]
                host_connected_nsp = []
                for fcpath in host['FCPaths']:
                    if 'portPos' in fcpath:
                        host_connected_nsp.append(
                            common.build_nsp(fcpath['portPos']))
                for port in active_fc_port_list:
                    if (
                        port['type'] == common.client.PORT_TYPE_HOST and
                        port['nsp'] in host_connected_nsp
                    ):
                        nsp = port['nsp']
                        vlun = common.create_vlun(volume,
                                                  host,
                                                  nsp,
                                                  lun_id=lun_id)
                        target_wwns.append(port['portWWN'])
                        if vlun['remoteName'] in init_targ_map:
                            init_targ_map[vlun['remoteName']].append(
                                port['portWWN'])
                        else:
                            init_targ_map[vlun['remoteName']] = [
                                port['portWWN']]
                        if lun_id is None:
                            lun_id = vlun['lun']
                if lun_id is None:
                    # New vlun creation failed
                    msg = _('No new vlun(s) were created')
                    LOG.error(msg)
                    raise exception.VolumeDriverException(msg)
            else:
                vlun = existing_vlun

            info = {'driver_volume_type': 'fibre_channel',
                    'data': {'target_lun': vlun['lun'],
                             'target_discovered': True,
                             'target_wwn': target_wwns,
                             'initiator_target_map': init_targ_map}}

            encryption_key_id = volume.get('encryption_key_id', None)
            info['data']['encrypted'] = encryption_key_id is not None
            return info
        finally:
            self._logout(common)


    def terminate_connection(self, volume, connector, **kwargs):
        """Driver entry point to unattach a volume from an instance."""
        common = self._login()
        try:
            hostname = common._safe_hostname(connector['host'])
            common.terminate_connection(volume, hostname,
                                        wwn=connector['wwpns'])

            info = {'driver_volume_type': 'fibre_channel',
                    'data': {}}

            #try:
            #    common.client.getHostVLUNs(hostname)
            #except hpeexceptions.HTTPNotFound:
                # No more exports for this host.
            #    LOG.info("Need to remove FC Zone, building initiator "
            #             "target map")
            #
            #    target_wwns, init_targ_map, _numPaths = \
            #        self._build_initiator_target_map(common, connector)
            #
            #    info['data'] = {'target_wwn': target_wwns,
            #                    'initiator_target_map': init_targ_map}
            return info

        finally:
            self._logout(common)

    def _build_initiator_target_map(self, common, connector):
        """Build the target_wwns and the initiator target map."""

        fc_ports = common.get_active_fc_target_ports()
        all_target_wwns = []
        target_wwns = []
        init_targ_map = {}
        numPaths = 0

        for port in fc_ports:
            all_target_wwns.append(port['portWWN'])


        initiator_wwns = connector['wwpns']
        target_wwns = all_target_wwns

        for initiator in initiator_wwns:
            init_targ_map[initiator] = target_wwns

        return target_wwns, init_targ_map, numPaths


    def _create_host(self, common, volume, connector):
        """Creates or modifies existing 3PAR host."""
        host = None
        print('\nBefore safe_hostname value is %s', connector['host'])
        hostname = common._safe_hostname(connector['host'])
        cpg = common.get_cpg(volume, allowSnap=True)
        domain = common.get_domain(cpg)
        print('\nAfter domain : %s', domain)
        try:
#            host = common._get_3par_host(hostname)
            host = common.client.getHost(hostname)
            print('\n After get host method, value of host is %s', host)
            # Check whether host with wwn of initiator present on 3par
            hosts = common.client.queryHost(wwns=connector['wwpns'])
            host, hostname = common._get_prioritized_host_on_3par(host,
                                                                  hosts,
                                                                  hostname)
        except hpeexceptions.HTTPNotFound:
            print('\nInside exception block')
            # get persona from the volume type extra specs
            persona_id = 2
            # host doesn't exist, we have to create it
            hostname = self._create_3par_fibrechan_host(common,
                                                        hostname,
                                                        connector['wwpns'],
                                                        domain,
                                                        persona_id)
            print('\n After create_fc_host')
            host = common._get_3par_host(hostname)
            return host
        else:
            return self._add_new_wwn_to_host(common, host, connector['wwpns'])

    def _add_new_wwn_to_host(self, common, host, wwns):
        """Add wwns to a host if one or more don't exist.

        Identify if argument wwns contains any world wide names
        not configured in the 3PAR host path. If any are found,
        add them to the 3PAR host.
        """
        # get the currently configured wwns
        # from the host's FC paths
        host_wwns = []
        if 'FCPaths' in host:
            for path in host['FCPaths']:
                wwn = path.get('wwn', None)
                if wwn is not None:
                    host_wwns.append(wwn.lower())

        # lower case all wwns in the compare list
        compare_wwns = [x.lower() for x in wwns]

        # calculate wwns in compare list, but not in host_wwns list
        new_wwns = list(set(compare_wwns).difference(host_wwns))

        # if any wwns found that were not in host list,
        # add them to the host
        if (len(new_wwns) > 0):
            self._modify_3par_fibrechan_host(common, host['name'], new_wwns)
            host = common._get_3par_host(host['name'])
        return host

    def create_export(self, volume, connector):
        pass

    def _create_3par_fibrechan_host(self, common, hostname, wwns,
                                    domain, persona_id):
        """Create a 3PAR host.

        Create a 3PAR host, if there is already a host on the 3par using
        the same wwn but with a different hostname, return the hostname
        used by 3PAR.
        """
        # first search for an existing host
        host_found = None
        hosts = common.client.queryHost(wwns=wwns)

        if hosts and hosts['members'] and 'name' in hosts['members'][0]:
            host_found = hosts['members'][0]['name']

        if host_found is not None:
            return host_found
        else:
            persona_id = int(persona_id)
            try:
                common.client.createHost(hostname, FCWwns=wwns,
                                         optional={'domain': domain,
                                                   'persona': persona_id})
            except hpeexceptions.HTTPConflict as path_conflict:
                msg = "Create FC host caught HTTP conflict code: %s"
                LOG.exception(msg, path_conflict.get_code())
                with save_and_reraise_exception(reraise=False) as ctxt:
                    if path_conflict.get_code() is EXISTENT_PATH:
                        # Handle exception : EXISTENT_PATH - host WWN/iSCSI
                        # name already used by another host
                        hosts = common.client.queryHost(wwns=wwns)
                        if hosts and hosts['members'] and (
                                'name' in hosts['members'][0]):
                            hostname = hosts['members'][0]['name']
                        else:
                            # re rasise last caught exception
                            ctxt.reraise = True
                    else:
                        # re rasise last caught exception
                        # for other HTTP conflict
                        ctxt.reraise = True
            return hostname
