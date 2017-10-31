import mock
# import fake_hpe_3par_client as hpe3parclient

from hpedockerplugin.hpe import hpe_3par_common as hpecommon
from hpedockerplugin import hpe_storage_api as api
from oslo_config import cfg

# hpeexceptions = hpe3parclient.hpeexceptions

CONF = cfg.CONF

KNOWN_HOSTS_FILE = 'dummy'

TASK_DONE = 1
TASK_ACTIVE = 2

FAKE_FC_PORTS = [{'portPos': {'node': 7, 'slot': 1, 'cardPort': 1},
                  'type': 1,
                  'portWWN': '0987654321234',
                  'protocol': 1,
                  'mode': 2,
                  'linkState': 4},
                 {'portPos': {'node': 6, 'slot': 1, 'cardPort': 1},
                  'type': 1,
                  'portWWN': '123456789000987',
                  'protocol': 1,
                  'mode': 2,
                  'linkState': 4}]
FAKE_ISCSI_PORT = {'portPos': {'node': 8, 'slot': 1, 'cardPort': 1},
                   'protocol': 2,
                   'mode': 2,
                   'IPAddr': '1.1.1.2',
                   'iSCSIName': ('iqn.2000-05.com.3pardata:'
                                 '21810002ac00383d'),
                   'linkState': 4}


@mock.patch(
    'hpedockerplugin.hpe.hpe_3par_common.client.HPE3ParClient',
    spec=True,
)
def setup_mock_3parclient(_m_client, conf=None, m_conf=None):
    mock_client_conf = {
        'PORT_MODE_TARGET': 2,
        'PORT_STATE_READY': 4,
        'PORT_PROTO_ISCSI': 2,
        'PORT_PROTO_FC': 1,
        'PORT_TYPE_HOST': 1,
        'TASK_DONE': TASK_DONE,
        'TASK_ACTIVE': TASK_ACTIVE,
        'HOST_EDIT_ADD': 1,
        'CHAP_INITIATOR': 1,
        'CHAP_TARGET': 2,
        'getPorts.return_value': {'members':
                                  FAKE_FC_PORTS + [FAKE_ISCSI_PORT]}}
    wsapi_version_for_compression = {'major': 1,
                                     'build': 30301215,
                                     'minor': 6,
                                     'revision': 0}

    # Use this to point to latest version of wsapi
    wsapi_version_latest = wsapi_version_for_compression


    # Configure the base constants, defaults etc...
    _m_client.configure_mock(**mock_client_conf)

    _m_client.getWsApiVersion.return_value = wsapi_version_latest

    return _m_client


def mock_decorator(func):
    @mock.patch('hpedockerplugin.hpe_storage_api.fileutil', spec=True)
    @mock.patch('hpedockerplugin.hpe_storage_api.connector.ISCSIConnector',
                spec=True)
    @mock.patch('hpedockerplugin.hpe_storage_api.util.EtcdUtil', spec=True)
    def setup_mock_wrapper(self, mock_etcd, mock_osbrick_connector,
                           mock_fileutil, *args, **kwargs):
        # Override the value as without it it throws an exception
        CONF.set_override('ssh_hosts_key_file',
                          KNOWN_HOSTS_FILE)

        mock_3parclient = setup_mock_3parclient()

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
