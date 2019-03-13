import mock

import test.fake_3par_data as data
from hpedockerplugin.hpe import hpe_3par_common as hpecommon
from hpedockerplugin import volume_manager as mgr
from hpedockerplugin import backend_orchestrator as orch
from oslo_config import cfg

CONF = cfg.CONF


def mock_decorator(func):
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
        'hpedockerplugin.backend_orchestrator.util.EtcdUtil',
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
                mock.patch.object(orch.Orchestrator, '_get_etcd_util') \
                as mock_get_etcd_util, \
                mock.patch.object(mgr.VolumeManager, '_get_connector') \
                as mock_get_connector, \
                mock.patch('hpedockerplugin.volume_manager.connector') \
                as mock_osbricks_connector, \
                mock.patch.object(orch.Orchestrator, '_get_node_id') \
                as mock_get_node_id, \
                mock.patch.object(mgr.VolumeManager, '_decrypt_password') \
                as mock_decrypt_password:
            mock_create_client.return_value = mock_3parclient
            mock_get_etcd_util.return_value = mock_etcd
            mock_get_connector.return_value = mock_protocol_connector
            mock_get_node_id.return_value = data.THIS_NODE_ID
            mock_decrypt_password.return_value = data.HPE3PAR_USER_PASS

            mock_objects = \
                {'mock_3parclient': mock_3parclient,
                 'mock_fileutil': mock_fileutil,
                 'mock_osbricks_connector': mock_osbricks_connector,
                 'mock_protocol_connector': mock_protocol_connector,
                 'mock_etcd': mock_etcd}
            return func(self, mock_objects, *args, **kwargs)
    return setup_mock_wrapper
