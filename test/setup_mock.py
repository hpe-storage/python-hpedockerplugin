import mock

from hpe3parclient import http
import test.fake_3par_data as data
from hpedockerplugin.hpe import hpe_3par_common as hpecommon
from hpedockerplugin.hpe import hpe_3par_mediator as hpe_3par_mediator
from hpedockerplugin.hpe import utils
from hpedockerplugin import volume_manager as mgr
from hpedockerplugin import backend_orchestrator as orch
from hpedockerplugin import file_backend_orchestrator as f_orch
from oslo_config import cfg

CONF = cfg.CONF


def mock_decorator(func):
    @mock.patch(
        'hpedockerplugin.file_manager.sh'
    )
    @mock.patch(
        'hpedockerplugin.file_manager.os',
        spec=True
    )
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
        'hpedockerplugin.file_backend_orchestrator.util.'
        'HpeFilePersonaEtcdClient',
        spec=True
    )
    @mock.patch(
        'hpedockerplugin.file_backend_orchestrator.util.'
        'HpeShareEtcdClient',
        spec=True
    )
    @mock.patch(
        'hpedockerplugin.hpe.hpe_3par_common.client.HPE3ParClient',
        spec=True
    )
    @mock.patch(
        'hpedockerplugin.hpe.hpe_3par_mediator.file_client.'
        'HPE3ParFilePersonaClient', spec=True
    )
    def setup_mock_wrapper(self, mock_file_client, mock_3parclient,
                           mock_share_etcd, mock_fp_etcd, mock_etcd,
                           mock_fileutil, mock_iscsi_connector,
                           mock_fc_connector, mock_os, mock_sh,
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
                mock.patch.object(orch.VolumeBackendOrchestrator,
                                  '_get_etcd_client') \
                as _get_etcd_client, \
                mock.patch.object(mgr.VolumeManager, '_get_connector') \
                as mock_get_connector, \
                mock.patch('hpedockerplugin.volume_manager.connector') \
                as mock_osbricks_connector, \
                mock.patch.object(orch.VolumeBackendOrchestrator,
                                  '_get_node_id') \
                as mock_get_node_id, \
                mock.patch.object(f_orch.FileBackendOrchestrator,
                                  '_get_node_id') \
                as mock_file_get_node_id, \
                mock.patch.object(utils.PasswordDecryptor,
                                  'decrypt_password') \
                as mock_decrypt_password, \
                mock.patch.object(f_orch.FileBackendOrchestrator,
                                  '_get_etcd_client') \
                as mock_get_etcd_client, \
                mock.patch.object(f_orch.FileBackendOrchestrator,
                                  '_get_fp_etcd_client') \
                as mock_get_fp_etcd_client, \
                mock.patch.object(hpe_3par_mediator.HPE3ParMediator,
                                  '_create_client') \
                as mock_create_file_client:
            mock_create_client.return_value = mock_3parclient
            _get_etcd_client.return_value = mock_etcd
            mock_get_connector.return_value = mock_protocol_connector
            mock_get_node_id.return_value = data.THIS_NODE_ID
            mock_file_get_node_id.return_value = data.THIS_NODE_ID
            mock_decrypt_password.return_value = data.HPE3PAR_USER_PASS
            mock_create_file_client.return_value = mock_file_client
            mock_get_etcd_client.return_value = mock_share_etcd
            mock_get_fp_etcd_client.return_value = mock_fp_etcd
            mock_file_client.http = mock.Mock(spec=http.HTTPJSONRESTClient)

            mock_objects = {
                'mock_3parclient': mock_3parclient,
                'mock_file_client': mock_file_client,
                'mock_fileutil': mock_fileutil,
                'mock_osbricks_connector': mock_osbricks_connector,
                'mock_protocol_connector': mock_protocol_connector,
                'mock_etcd': mock_etcd,
                'mock_share_etcd': mock_share_etcd,
                'mock_fp_etcd': mock_fp_etcd,
                'mock_os': mock_os,
                'mock_sh': mock_sh
            }
            return func(self, mock_objects, *args, **kwargs)
    return setup_mock_wrapper
