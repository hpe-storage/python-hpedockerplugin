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

"""HPE LeftHand SAN ISCSI REST Proxy.

Volume driver for HPE LeftHand Storage array.
This driver requires 11.5 or greater firmware on the LeftHand array, using
the 2.0 or greater version of the hpelefthandclient.

You will need to install the python hpelefthandclient module.
sudo pip install python-lefthandclient

Set the following in the hpe.conf file to enable the
LeftHand iSCSI REST Driver along with the required flags:

hpedockerplugin_driver = hpe.hpe_lefthand_iscsi.HPELeftHandISCSIDriver

It also requires the setting of hpelefthand_api_url, hpelefthand_username,
hpelefthand_password for credentials to talk to the REST service on the
LeftHand array.

"""

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils
from oslo_utils import units

from hpedockerplugin import exception
from hpedockerplugin.i18n import _, _LE, _LI, _LW

from hpe import san_driver
from hpe import utils as volume_utils

LOG = logging.getLogger(__name__)

hpelefthandclient = importutils.try_import("hpelefthandclient")
if hpelefthandclient:
    from hpelefthandclient import client as hpe_lh_client
    from hpelefthandclient import exceptions as hpeexceptions

hpelefthand_opts = [
    cfg.StrOpt('hpelefthand_api_url',
               default=None,
               help="HPE LeftHand WSAPI Server Url like "
                    "https://<LeftHand ip>:8081/lhos",
               deprecated_name='hplefthand_api_url'),
    cfg.StrOpt('hpelefthand_username',
               default=None,
               help="HPE LeftHand Super user username",
               deprecated_name='hplefthand_username'),
    cfg.StrOpt('hpelefthand_password',
               default=None,
               help="HPE LeftHand Super user password",
               secret=True,
               deprecated_name='hplefthand_password'),
    cfg.StrOpt('hpelefthand_clustername',
               default=None,
               help="HPE LeftHand cluster name",
               deprecated_name='hplefthand_clustername'),
    cfg.BoolOpt('hpelefthand_iscsi_chap_enabled',
                default=False,
                help='Configure CHAP authentication for iSCSI connections '
                '(Default: Disabled)',
                deprecated_name='hplefthand_iscsi_chap_enabled'),
    cfg.BoolOpt('hpelefthand_debug',
                default=False,
                help="Enable HTTP debugging to LeftHand",
                deprecated_name='hplefthand_debug'),
    cfg.BoolOpt('suppress_requests_ssl_warnings',
                default=False,
                help='Suppress requests library SSL certificate warnings.'),

]

CONF = cfg.CONF
CONF.register_opts(hpelefthand_opts)

MIN_API_VERSION = "1.1"
MIN_CLIENT_VERSION = '2.0.0'


class HPELeftHandISCSIDriver(object):
    """Executes REST commands relating to HPE/LeftHand SAN ISCSI volumes.

    Version history:

    .. code-block:: none

        0.0.1 - Initial version of the LeftHand iSCSI driver created.
        0.0.2 - Added support for CHAP.
        0.0.3 - Added the ability to choose volume provisionings.

    """

    VERSION = "0.0.3"

    valid_prov_values = ['thin', 'full', 'dedup']

    def __init__(self, hpelefthandconfig):

        self.configuration = hpelefthandconfig
        self.configuration.append_config_values(hpelefthand_opts)

        # TODO: Need to move the SAN opts values out, but where?!?
        self.configuration.append_config_values(san_driver.san_opts)
        self.configuration.append_config_values(san_driver.volume_opts)

        # blank is the only invalid character for cluster names
        # so we need to use it as a separator
        self.DRIVER_LOCATION = self.__class__.__name__ + ' %(cluster)s %(vip)s'

    def _login(self):
        client = self._create_client()
        try:
            if self.configuration.hpelefthand_debug:
                client.debug_rest(True)

            client.login(
                self.configuration.hpelefthand_username,
                self.configuration.hpelefthand_password)

            cluster_info = client.getClusterByName(
                self.configuration.hpelefthand_clustername)
            self.cluster_id = cluster_info['id']
            virtual_ips = cluster_info['virtualIPAddresses']
            self.cluster_vip = virtual_ips[0]['ipV4Address']

            return client
        except hpeexceptions.HTTPNotFound:
            raise exception.DriverNotInitialized(
                _('LeftHand cluster not found'))
        except Exception as ex:
            raise exception.DriverNotInitialized(ex)

    def _logout(self, client):
        client.logout()

    def _create_client(self):
        return hpe_lh_client.HPELeftHandClient(
            self.configuration.hpelefthand_api_url,
            suppress_ssl_warnings=CONF.suppress_requests_ssl_warnings)

    def do_setup(self):
        """Set up LeftHand client."""
        if hpelefthandclient.version < MIN_CLIENT_VERSION:
            ex_msg = (_("Invalid hpelefthandclient version found ("
                        "%(found)s). Version %(minimum)s or greater "
                        "required. Run 'pip install --upgrade "
                        "python-lefthandclient' to upgrade the "
                        "hpelefthandclient.")
                      % {'found': hpelefthandclient.version,
                         'minimum': MIN_CLIENT_VERSION})
            LOG.error(ex_msg)
            raise exception.InvalidInput(reason=ex_msg)

    def check_for_setup_error(self):
        """Checks for incorrect LeftHand API being used on backend."""
        client = self._login()
        try:
            self.api_version = client.getApiVersion()

            LOG.info(_LI("HPELeftHand API version %s"), self.api_version)

            if self.api_version < MIN_API_VERSION:
                LOG.warning(_LW("HPELeftHand API is version %(current)s. "
                                "A minimum version of %(min)s is needed for "
                                "manage/unmanage support."),
                            {'current': self.api_version,
                             'min': MIN_API_VERSION})
        finally:
            self._logout(client)

    def get_version_string(self):
        return (_('REST %(proxy_ver)s hpelefthandclient %(rest_ver)s') % {
            'proxy_ver': self.VERSION,
            'rest_ver': hpelefthandclient.get_version_string()})

    def create_volume(self, volume):
        """Creates a volume."""
        # check for valid provisioning type
        prov_value = volume['provisioning']
        if prov_value not in self.valid_prov_values:
            err = (_("Must specify a valid provisioning type %(valid)s, "
                     "value '%(prov)s' is invalid.") %
                   {'valid': self.valid_prov_values,
                    'prov': prov_value})
            LOG.error(err)
            raise exception.InvalidInput(reason=err)

        thin_prov = True

        if prov_value == "full":
            thin_prov = False
        elif prov_value == "dedup":
            err = (_("Dedup is not supported in the StoreVirtual driver."))
            LOG.error(err)
            raise exception.InvalidInput(reason=err)

        client = self._login()
        try:
            optional = {'isThinProvisioned': thin_prov,
                        'dataProtectionLevel': 0}

            clusterName = self.configuration.hpelefthand_clustername
            optional['clusterName'] = clusterName

            volume_info = client.createVolume(
                volume['name'], self.cluster_id,
                volume['size'] * units.Gi,
                optional)

            model_update = self._update_provider(volume_info)
            volume['provider_location'] = model_update['provider_location']
            volume['provider_auth'] = ''
        except Exception as ex:
            raise exception.VolumeBackendAPIException(data=ex)
        finally:
            self._logout(client)

    def delete_volume(self, volume):
        """Deletes a volume."""
        client = self._login()
        try:
            volume_info = client.getVolumeByName(volume['name'])
            client.deleteVolume(volume_info['id'])
        except hpeexceptions.HTTPNotFound:
            LOG.error(_LE("Volume did not exist. It will not be deleted"))
        except Exception as ex:
            raise exception.VolumeBackendAPIException(ex)
        finally:
            self._logout(client)

    def initialize_connection(self, volume, connector):
        """Assigns the volume to a server.

        Assign any created volume to a compute node/host so that it can be
        used from that host. HPE VSA requires a volume to be assigned
        to a server.
        """
        client = self._login()
        try:
            server_info = self._create_server(connector, client)
            volume_info = client.getVolumeByName(volume['name'])

            access_already_enabled = False
            if volume_info['iscsiSessions'] is not None:
                # Extract the server id for each session to check if the
                # new server already has access permissions enabled.
                for session in volume_info['iscsiSessions']:
                    server_id = int(session['server']['uri'].split('/')[3])
                    if server_id == server_info['id']:
                        access_already_enabled = True
                        break

            if not access_already_enabled:
                client.addServerAccess(
                    volume_info['id'],
                    server_info['id'])

            iscsi_properties = san_driver._get_iscsi_properties(
                volume,
                self.configuration.iscsi_ip_address)

            if ('chapAuthenticationRequired' in server_info and
                    server_info['chapAuthenticationRequired']):
                iscsi_properties['auth_method'] = 'CHAP'
                iscsi_properties['auth_username'] = connector['initiator']
                iscsi_properties['auth_password'] = (
                    server_info['chapTargetSecret'])

            return {'driver_volume_type': 'iscsi', 'data': iscsi_properties}
        except Exception as ex:
            raise exception.VolumeBackendAPIException(ex)
        finally:
            self._logout(client)

    def terminate_connection(self, volume, connector, **kwargs):
        """Unassign the volume from the host."""
        client = self._login()
        try:
            volume_info = client.getVolumeByName(volume['name'])
            server_info = client.getServerByName(connector['host'])
            volume_list = client.findServerVolumes(server_info['name'])

            removeServer = True
            for entry in volume_list:
                if entry['id'] != volume_info['id']:
                    removeServer = False
                    break

            client.removeServerAccess(
                volume_info['id'],
                server_info['id'])

            if removeServer:
                client.deleteServer(server_info['id'])
        except Exception as ex:
            raise exception.VolumeBackendAPIException(ex)
        finally:
            self._logout(client)

    def _create_server(self, connector, client):
        server_info = None
        chap_enabled = self.configuration.hpelefthand_iscsi_chap_enabled
        try:
            server_info = client.getServerByName(connector['host'])
            chap_secret = server_info['chapTargetSecret']
            if not chap_enabled and chap_secret:
                LOG.warning(_LW('CHAP secret exists for host %s but CHAP is '
                                'disabled'), connector['host'])
            if chap_enabled and chap_secret is None:
                LOG.warning(_LW('CHAP is enabled, but server secret not '
                                'configured on server %s'), connector['host'])
            return server_info
        except hpeexceptions.HTTPNotFound:
            # server does not exist, so create one
            pass

        optional = None
        if chap_enabled:
            chap_secret = volume_utils.generate_password()
            optional = {'chapName': connector['initiator'],
                        'chapTargetSecret': chap_secret,
                        'chapAuthenticationRequired': True
                        }

        server_info = client.createServer(connector['host'],
                                          connector['initiator'],
                                          optional)
        return server_info

    def _update_provider(self, volume_info, cluster_vip=None):
        if not cluster_vip:
            cluster_vip = self.cluster_vip
        # TODO(justinsb): Is this always 1? Does it matter?
        cluster_interface = '1'
        iscsi_portal = cluster_vip + ":3260," + cluster_interface

        return {'provider_location': (
            "%s %s %s" % (iscsi_portal, volume_info['iscsiIqn'], 0))}

    def create_export(self, volume, connector):
        pass
