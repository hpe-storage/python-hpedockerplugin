import mock

import test.fake_3par_data as data
from hpedockerplugin.hpe import hpe_3par_common as hpecommon
from hpedockerplugin import volume_manager as mgr
from hpedockerplugin import backend_orchestrator as orchestrator
from oslo_config import cfg

CONF = cfg.CONF


def mock_decorator(func):
    #@mock.patch(
    #    'hpedockerplugin.backend_orchestrator.Orchestrator',
    #    spec=True,
    #)
    @mock.patch(
        'hpedockerplugin.volume_manager.connector.FibreChannelConnector',
        spec=True
    )
    @mock.patch(
        'hpedockerplugin.volume_manager.connector.ISCSIConnector',
        spec=True
    )
    @mock.patch(
        'hpedockerplugin.volume_manager.fileutil',
        spec=True
    )
    @mock.patch(
        'hpedockerplugin.volume_manager.util.EtcdUtil',
        spec=True
    )
    @mock.patch(
        'hpedockerplugin.hpe.hpe_3par_common.client.HPE3ParClient',
        spec=True,
    )
    def setup_mock_wrapper(self, mock_3parclient, mock_etcd, mock_fileutil,
                           mock_iscsi_connector, mock_fc_connector,
                           *args, **kwargs):
        # Override the value as without it it throws an exception
        CONF.set_override('ssh_hosts_key_file',
                          data.KNOWN_HOSTS_FILE)

        mock_3parclient.configure_mock(**data.mock_client_conf)
        mock_3parclient.getWsApiVersion.return_value = \
            data.wsapi_version_for_compression

        mock_protocol_connector = None
        if self._protocol == 'ISCSI':
            mock_protocol_connector = mock_iscsi_connector
        elif self._protocol == 'FC':
            mock_protocol_connector = mock_fc_connector

        with mock.patch.object(hpecommon.HPE3PARCommon, '_create_client') \
            as mock_create_client, \
            mock.patch.object(mgr.VolumeManager, '_get_etcd_util') \
            as mock_get_etcd_util, \
            mock.patch.object(orchestrator.Orchestrator, 'initialize_manager_objects') \
            as mock_orchestrator, \
            mock.patch.object(mgr.VolumeManager, '_get_connector') \
                as mock_get_connector, \
                mock.patch('hpedockerplugin.volume_manager.connector') \
                as mock_osbricks_connector, \
                mock.patch.object(mgr.VolumeManager, '_get_node_id') \
                as mock_get_node_id:
                mock_create_client.return_value = mock_3parclient
                mock_get_etcd_util.return_value = mock_etcd
                mock_get_connector.return_value = mock_protocol_connector
                mock_get_node_id.return_value = data.THIS_NODE_ID
                #mock_orchestrator.return_value = mock_orchestrat
                config = create_configuration(self._protocol)
                mock_orchestrator.return_value = {'DEFAULT': mgr.VolumeManager(config,config)}
                mock_objects = \
                    {'mock_3parclient': mock_3parclient,
                     'mock_fileutil': mock_fileutil,
                     'mock_osbricks_connector': mock_osbricks_connector,
                     'mock_protocol_connector': mock_protocol_connector,
                     'mock_etcd': mock_etcd,
                     'mock_orchestrator': mock_orchestrator}
                return func(self, mock_objects, *args, **kwargs)
    return setup_mock_wrapper
def create_configuration(protocol):
    config = mock.Mock()
    config.ssh_hosts_key_file = "/root/.ssh/known_hosts"
#    config.ssh_hosts_key_file = "/home/docker/.ssh/known_hosts"
    config.host_etcd_ip_address = "10.50.3.140"
    config.host_etcd_port_number = 2379
    config.logging = "DEBUG"
    config.hpe3par_debug = False
    config.suppress_requests_ssl_warnings = True

    if protocol == 'ISCSI':
        config.hpedockerplugin_driver = \
            "hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver"
    else:
        config.hpedockerplugin_driver = \
            "hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver"

    config.hpe3par_api_url = "https://10.50.3.9:8080/api/v1"
    config.hpe3par_username = "3paradm"
    config.hpe3par_password = "3pardata"
    config.san_ip = "10.50.3.9"
    config.san_login = "3paradm"
    config.san_password = "3pardata"
    config.hpe3par_cpg = [data.HPE3PAR_CPG, data.HPE3PAR_CPG2]
    config.hpe3par_snapcpg = [data.HPE3PAR_CPG]
    config.hpe3par_iscsi_ips = ['10.50.3.59', '10.50.3.60']
    config.iscsi_ip_address = '1.1.1.2'
    config.hpe3par_iscsi_chap_enabled = False
    config.use_multipath = True
    config.enforce_multipath = True
    config.host_etcd_client_cert = None
    config.host_etcd_client_key = None
    config.mount_conflict_delay = 3

    # This flag doesn't belong to hpe.conf. Has been added to allow
    # framework to decide if ETCD is to be mocked or real
    config.use_real_flow = False

    return config
