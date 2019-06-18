import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest
from oslo_config import cfg
CONF = cfg.CONF


class ListVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_list'

    def get_request_params(self):
        return {}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_all_vols.return_value = []

    def override_configuration(self, config):
        pass

    # TODO: check_response and setup_mock_objects can be implemented
    # here for the normal happy path TCs here as they are same


class TestListNoVolumes(ListVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_all_vols.assert_called()


class TestListVolumeDefault(ListVolumeUnitTest):
    def check_response(self, resp):
        expected_vols = [
            {
                'Devicename': '',
                'Mountpoint': '',
                'Name': 'test-vol-001',
                'Status': {},
                'size': 310
            },
            {
                'Devicename': '',
                'Mountpoint': '',
                'Name': 'test-vol-002',
                'Status': {},
                'size': 555
            }
        ]

        self._test_case.assertEqual(resp, {u"Err": '',
                                           'Volumes': expected_vols})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_all_vols.assert_called()
        mock_etcd.get_path_info_from_vol.assert_called()
        self._test_case.assertEqual(
            mock_etcd.get_path_info_from_vol.call_count, 2)

    def get_request_params(self):
        return {}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_all_vols.return_value = data.vols_list
