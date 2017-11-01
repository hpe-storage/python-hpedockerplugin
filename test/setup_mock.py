import mock

import fake_3par_data as data
from hpedockerplugin.hpe import hpe_3par_common as hpecommon
from hpedockerplugin import hpe_storage_api as api
from oslo_config import cfg

CONF = cfg.CONF


@mock.patch(
    'hpedockerplugin.hpe.hpe_3par_common.client.HPE3ParClient',
    spec=True,
)
def setup_mock_3parclient(_m_client, conf=None, m_conf=None):
    # Configure the base constants, defaults etc...
    _m_client.configure_mock(**data.mock_client_conf)
    _m_client.getWsApiVersion.return_value = data.wsapi_version_for_compression
    return _m_client


@mock.patch('hpedockerplugin.hpe_storage_api.connector.ISCSIConnector',
            spec=True)
def _get_mock_iscsi_connector(mock_connector):
    return mock_connector


@mock.patch('hpedockerplugin.hpe_storage_api.connector.FibreChannelConnector',
            spec=True)
def _get_mock_fc_connector(mock_connector):
    return mock_connector


def mock_decorator(func):
    @mock.patch('hpedockerplugin.hpe_storage_api.fileutil', spec=True)
    @mock.patch('hpedockerplugin.hpe_storage_api.util.EtcdUtil', spec=True)
    def setup_mock_wrapper(self, mock_etcd, mock_fileutil, *args, **kwargs):
        # Override the value as without it it throws an exception
        CONF.set_override('ssh_hosts_key_file',
                          data.KNOWN_HOSTS_FILE)

        mock_3parclient = setup_mock_3parclient()

        mock_osbrick_connector = None
        if 'ISCSI' in self._config.hpedockerplugin_driver:
            mock_osbrick_connector = _get_mock_iscsi_connector()
        elif 'FC' in self._config.hpedockerplugin_driver:
            mock_osbrick_connector = _get_mock_fc_connector()

        with mock.patch.object(hpecommon.HPE3PARCommon, '_create_client') \
            as mock_create_client, \
            mock.patch.object(api.VolumePlugin, '_get_etcd_util') \
            as mock_get_etcd_util, \
            mock.patch.object(api.VolumePlugin, '_get_connector') \
                as mock_get_connector:
                mock_create_client.return_value = mock_3parclient
                mock_get_etcd_util.return_value = mock_etcd
                mock_get_connector.return_value = mock_osbrick_connector
                mock_objects = \
                    {'mock_3parclient': mock_3parclient,
                     'mock_fileutil': mock_fileutil,
                     'mock_osbrick_connector': mock_osbrick_connector,
                     'mock_etcd': mock_etcd}
                return func(self, mock_objects, *args, **kwargs)
    return setup_mock_wrapper
