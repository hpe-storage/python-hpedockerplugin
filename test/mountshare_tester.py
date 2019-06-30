import copy

import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest


class MountShareUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def __init__(self):
        self._backend_name = None

    def _get_plugin_api(self):
        return 'volumedriver_mount'

    def get_request_params(self):
        return {"Name": 'DemoShare-99',
                "ID": "Fake-Mount-ID"}

    def setup_mock_objects(self):
        def _setup_mock_3parclient():
            self.setup_mock_3parclient()

        def _setup_mock_etcd():
            # Allow child class to make changes
            self.setup_mock_etcd()

        _setup_mock_3parclient()
        _setup_mock_etcd()

    def setup_mock_3parclient(self):
        pass

    def setup_mock_etcd(self):
        pass

    def setup_mock_fileutil(self):
        pass


class TestMountNfsShare(MountShareUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._share = copy.deepcopy(data.etcd_share)

    def setup_mock_etcd(self):
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_share_etcd.get_share.return_value = self._share

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


class TestMountNfsShareWithAcl(MountShareUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._share = copy.deepcopy(data.etcd_share_with_acl)

    def setup_mock_etcd(self):
        mock_share_etcd = self.mock_objects['mock_share_etcd']
        mock_share_etcd.get_share.return_value = self._share
        mock_file_client = self.mock_objects['mock_file_client']
        mock_file_client._run.side_effect = [
            data.show_fs_user_resp,
            data.show_fs_group_resp
        ]

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
