import copy

import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest


class UnmountShareUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def __init__(self):
        self._backend_name = None
        self._share = copy.deepcopy(data.etcd_mounted_share)

    def _get_plugin_api(self):
        return 'volumedriver_unmount'

    def get_request_params(self):
        return {"Name": 'GoodShare',
                "ID": "Fake-Mount-ID"}

    def setup_mock_objects(self):
        def _setup_mock_3parclient():
            self.setup_mock_3parclient()

        def _setup_mock_etcd():
            mock_share_etcd = self.mock_objects['mock_share_etcd']
            mock_share_etcd.get_share.return_value = self._share
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


class TestUnmountNfsShare(UnmountShareUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    # def setup_mock_3parclient(self):
    #     mock_client = self.mock_objects['mock_3parclient']

    def check_response(self, resp):
        pass
        # mnt_point = '/opt/hpe/data/hpedocker-GoodShare'
        # dev_name = '192.168.98.41:/DockerFpg_2/DockerVfs_2/GoodShare'
        # expected = {
        #     'Mountpoint': mnt_point,
        #     'Err': '',
        #     'Name': 'GoodShare',
        #     'Devicename': dev_name}
        # expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        # for key in expected_keys:
        #     self._test_case.assertIn(key, resp)
        #
        # self._test_case.assertEqual(resp, expected)
