import json
import setup_mock
import testtools
import mock
from twisted.internet import reactor
from hpedockerplugin import hpe_storage_api as api
from oslo_config import cfg
# from oslo_utils import importutils
from cStringIO import StringIO
# from hpedockerplugin.hpe import hpe_3par_common as hpecommon
import fake_hpe_3par_client as hpe3parclient

hpeexceptions = hpe3parclient.hpeexceptions

CONF = cfg.CONF


class RequestBody:
    def __init__(self, req_body_str):
        self.content = StringIO(req_body_str)


HPE3PAR_CPG = 'DockerCPG'
HPE3PAR_CPG2 = 'fakepool'


class TestHpeDockerPlugin(testtools.TestCase):

    TASK_DONE = 1
    TASK_ACTIVE = 2
    STATUS_DONE = {'status': 1}
    STATUS_ACTIVE = {'status': 2}
    VOL_NAME = 'My-Test-Vol-001'
    VOL_SIZE = 10
    PROV = 'thin'
    FLASH_CACHE = False

    VOLUME_3PAR_NAME = 'dcv-AhonjfVvSk6D9CkpOYV9Gg'
    TARGET_LUN = 186

    wwn = ["123456789012345", "123456789054321"]
    volume = {'id': '021a278d-f56f-4a4e-83f4-292939857d1a',
              'name': VOL_NAME,
              'host': '',
              'size': VOL_SIZE,
              'availability_zone': '',
              'status': 'available',
              'attach_status': '',
              'display_name': VOL_NAME,
              'volume_id': '',
              'volume_type': None,
              'volume_attachment': None,
              'provider_location': None,
              'path_info': None,
              'provisioning': PROV,
              'flash_cache': FLASH_CACHE}
    FAKE_HOST = 'fakehost'
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
        'getPorts.return_value': {
            'members': FAKE_FC_PORTS + [FAKE_ISCSI_PORT]
        }
    }
    KNOWN_HOSTS_FILE = 'dummy'
    wsapi_version_for_compression = {'major': 1,
                                     'build': 30301215,
                                     'minor': 6,
                                     'revision': 0}

    # Use this to point to latest version of wsapi
    wsapi_version_latest = wsapi_version_for_compression

    def _get_configuration(self):
        config = mock.Mock()
        config.ssh_hosts_key_file = "/root/.ssh/known_hosts"
        config.host_etcd_ip_address = "10.50.3.140"
        config.host_etcd_port_number = "2379"
        config.logging = "DEBUG"
        config.hpe3par_debug = False
        config.suppress_requests_ssl_warnings = False
        config.hpedockerplugin_driver = self.get_driver_class_name()
        config.hpe3par_api_url = "https://10.50.3.7:8080/api/v1"
        config.hpe3par_username = "3paradm"
        config.hpe3par_password = "3pardata"
        config.san_ip = "10.50.3.7"
        config.san_login = "3paradm"
        config.san_password = "3pardata"
        config.hpe3par_cpg = [HPE3PAR_CPG, HPE3PAR_CPG2]
        # config.hpe3par_iscsi_ips = ["10.50.17.220", "10.50.17.221",
        #                             "10.50.17.222", "10.50.17.223"]
        config.hpe3par_iscsi_ips = []
        config.iscsi_ip_address = '1.1.1.2'
        config.hpe3par_iscsi_chap_enabled = False
        config.use_multipath = False
        config.enforce_multipath = False
        config.host_etcd_client_cert = None
        config.host_etcd_client_key = None
        return config

    @setup_mock.mock_decorator
    def test_create_volume_default(self, mock_objects):
        # mock_3parclient = mock_objects['mock_3parclient']
        # mock_fileutil = mock_objects['mock_fileutil']
        # mock_osbrick_connector = mock_objects['mock_osbrick_connector']
        mock_etcd = mock_objects['mock_etcd']

        mock_etcd.get_vol_byname.return_value = None

        vol_name = "test-vol-001"
        req_body_dict = {"Name": vol_name,
                         "Opts": {}}
        req_body_str = json.dumps(req_body_dict)
        req_body = RequestBody(req_body_str)

        self._config = self._get_configuration()
        self._api = api.VolumePlugin(reactor, self._config)
        resp = self._api.volumedriver_create(req_body)
        resp = json.loads(resp)
        self.assertTrue(resp, {u"Err": ''})

    @setup_mock.mock_decorator
    def test_mount_volume_default(self, mock_objects):
        mock_3parclient = mock_objects['mock_3parclient']
        mock_fileutil = mock_objects['mock_fileutil']
        mock_osbrick_connector = mock_objects['mock_osbrick_connector']
        mock_etcd = mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = self.volume

        mock_fileutil.mkdir_for_mounting.return_value = '/tmp'

        mock_osbrick_connector.get_connector_properties.return_value = \
            {'ip': '10.0.0.2',
             'initiator': 'iqn.1993-08.org.debian:01:222',
             'wwpns': [self.wwn[0], self.wwn[1]],
             'wwnns': ["223456789012345", "223456789054321"],
             'host': self.FAKE_HOST,
             'multipath': False}

        # MUST provide an existing path on FS for FilePath to work
        mock_osbrick_connector.connect_volume.return_value = {'path': '/tmp'}
        mock_3parclient.getVolume.return_value = {'userCPG': HPE3PAR_CPG}
        mock_3parclient.getHostVLUNs.return_value = \
            [{'active': True,
              'volumeName': self.VOLUME_3PAR_NAME,
              'portPos': {'node': 8,
                          'slot': 1,
                          'cardPort': 1},
              'remoteName': self.wwn[1],
              'lun': 90, 'type': 0}, {'active': False,
                                      'volumeName': self.VOLUME_3PAR_NAME,
                                      'portPos': {'node': 9,
                                                  'slot': 1,
                                                  'cardPort': 1},
                                      'remoteName': self.wwn[0],
                                      'lun': 90, 'type': 0}]

        mock_3parclient.getHost.return_value = \
            {'name': self.FAKE_HOST,
             'initiatorChapEnabled': False,
             'iSCSIPaths': [{"name": "iqn.1993-08.org.debian:01:222"}]}

        mock_3parclient.queryHost.return_value = {'members':
                                                  [{'name': self.FAKE_HOST}]}

        mock_3parclient.getVolumeMetaData.return_value = \
            {'value': 'random-key'}

        mock_3parclient.getCPG.return_value = {}

        location = ("%(volume_name)s,%(lun_id)s,%(host)s,%(nsp)s" %
                    {'volume_name': self.VOLUME_3PAR_NAME,
                     'lun_id': 90,
                     'host': self.FAKE_HOST,
                     'nsp': 'something'})
        mock_3parclient.createVLUN.return_value = location

        vol_name = "test-vol-001"
        req_body_dict = {"Name": vol_name}
        req_body_str = json.dumps(req_body_dict)
        req_body = RequestBody(req_body_str)

        self._config = self._get_configuration()
        self._api = api.VolumePlugin(reactor, self._config)
        resp = self._api.volumedriver_mount(req_body)
        resp = json.loads(resp)

        # {"Mountpoint": "/tmp", "Name": "test-vol-001", "Err": "",
        #  "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self.assertIn(key, resp)
        self.assertEqual(resp['Err'], '')


class TestHpeDockerPluginSCSI(TestHpeDockerPlugin):
    def get_driver_class_name(self):
        return "hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver"
