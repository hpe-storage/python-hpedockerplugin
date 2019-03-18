import copy

import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest


class MountShareUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def __init__(self):
        self._backend_name = None
        self._share = copy.deepcopy(data.share)

    def _get_plugin_api(self):
        return 'volumedriver_mount'

    def get_request_params(self):
        opts = {'mount-volume': 'True',
                'fstore': 'imran_fstore',
                'shareDir': 'DemoShareDir99',
                'vfsIP': '10.50.9.90'}

        if self._backend_name:
            opts['backend'] = self._backend_name
        return {"Name": 'DemoShare-99',
                "ID": "Fake-Mount-ID",
                "Opts": opts}

    def setup_mock_objects(self):
        def _setup_mock_3parclient():
            self.setup_mock_3parclient()

        def _setup_mock_etcd():
            mock_etcd = self.mock_objects['mock_etcd']
            mock_etcd.get_vol_byname.return_value = self._share
            # Allow child class to make changes
            self.setup_mock_etcd()

        # def _setup_mock_fileutil():
        #     mock_fileutil = self.mock_objects['mock_fileutil']
        #     mock_fileutil.mkdir_for_mounting.return_value = '/tmp'
        #     # Let the flow create filesystem
        #     mock_fileutil.has_filesystem.return_value = False
        #     # Allow child class to make changes
        #     self.setup_mock_fileutil()
        _setup_mock_3parclient()
        _setup_mock_etcd()
        # _setup_mock_fileutil()

    def setup_mock_3parclient(self):
        pass

    def setup_mock_etcd(self):
        pass

    def setup_mock_fileutil(self):
        pass


class TestMountNfsShare(MountShareUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    # def setup_mock_3parclient(self):
    #     mock_client = self.mock_objects['mock_3parclient']

    def check_response(self, resp):
        mnt_point = '/opt/hpe/data/hpedocker-DemoShare-99-Fake-Mount-ID'
        dev_name = '10.50.9.90:/imran_fpg/imran_vfs/imran_fstore/' \
                   'DemoShareDir99'
        expected = {
            'Mountpoint': mnt_point,
            'Err': '',
            'Name': 'DemoShare-99',
            'Devicename': dev_name}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp, expected)
        # # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        # #          u'Err': u'', u'Devicename': u'/tmp'}
        # self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        # self._test_case.assertEqual(resp['Name'],
        #                             self._vol['display_name'])
        # self._test_case.assertEqual(resp['Err'], u'')
        # self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # # Check if these functions were actually invoked
        # # in the flow or not
        # mock_etcd = self.mock_objects['mock_etcd']
        # mock_3parclient = self.mock_objects['mock_3parclient']
        # mock_3parclient.getWsApiVersion.assert_called()
