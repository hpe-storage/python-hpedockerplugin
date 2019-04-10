import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest
import copy

from oslo_config import cfg
CONF = cfg.CONF


class RemoveVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_remove'

    def override_configuration(self, all_configs):
        pass


class TestRemoveVolume(RemoveVolumeUnitTest):

    def __init__(self, test_obj):
        self._test_obj = test_obj

    def get_request_params(self):
        return self._test_obj.get_request_params()

    def setup_mock_objects(self):
        self._test_obj.setup_mock_objects(self.mock_objects)

    def check_response(self, resp):
        self._test_obj.check_response(resp, self.mock_objects,
                                      self._test_case)

    # Nested class to handle regular volume
    class Regular(object):
        def get_request_params(self):
            vol_name = data.volume['name']
            return {"Name": vol_name,
                    "Opts": {}}

        def setup_mock_objects(self, mock_objects):
            mock_etcd = mock_objects['mock_etcd']
            mock_etcd.get_vol_byname.return_value = copy.deepcopy(data.volume)

        def check_response(self, resp, mock_objects, test_case):
            # Check if these functions were actually invoked
            # in the flow or not
            mock_3parclient = mock_objects['mock_3parclient']
            mock_3parclient.getWsApiVersion.assert_called()

            mock_3parclient.deleteVolume.assert_called()

            mock_etcd = mock_objects['mock_etcd']
            mock_etcd.delete_vol.assert_called()

    # REPLICATED VOLUME
    class ReplicatedVolume(object):
        def __init__(self, params):
            self._params = params

        def get_request_params(self):
            vol_name = data.replicated_volume['name']
            return {"Name": vol_name,
                    "Opts": {}}

        def setup_mock_objects(self, mock_objects):
            mock_etcd = mock_objects['mock_etcd']
            mock_etcd.get_vol_byname.return_value = data.replicated_volume

            mock_3parclient = mock_objects['mock_3parclient']

            if self._params.get('rm_last_volume'):
                # Simulate that this is the last volume
                mock_3parclient.getRemoteCopyGroup.side_effect = [
                    {'role': self._params['role']},
                    {'volumes': []}
                ]
            else:
                # Simulate that this is NOT the last volume
                mock_3parclient.getRemoteCopyGroup.side_effect = [
                    {'role': self._params['role']},
                    {'volumes': ['dummy-vol1', 'dummy-vol2']}
                ]

        def check_response(self, resp, mock_objects, test_case):
            if self._params['role'] == data.ROLE_PRIMARY:
                test_case.assertEqual(resp, {u"Err": ''})

                mock_3parclient = mock_objects['mock_3parclient']
                mock_3parclient.getRemoteCopyGroup.assert_called()
                mock_3parclient.stopRemoteCopy.assert_called()
                mock_3parclient.removeVolumeFromRemoteCopyGroup.assert_called()
                mock_3parclient.deleteVolume.assert_called()
                if self._params.get('rm_last_volume'):
                    mock_3parclient.removeRemoteCopyGroup.assert_called()
                else:
                    mock_3parclient.removeRemoteCopyGroup.assert_not_called()
                    mock_3parclient.startRemoteCopy.asssert_called()

                mock_etcd = mock_objects['mock_etcd']
                mock_etcd.delete_vol.assert_called()
            else:
                msg = "Error: Failed to delete volume: %(vol)s as rcg: " \
                      "%(rcg)s do not have valid role" % {
                          'vol': data.VOLUME_3PAR_NAME,
                          'rcg': data.replicated_volume['rcg_info'][
                              'local_rcg_name']}
                test_case.assertEqual(resp, {u"Err": msg})


class TestRemoveNonExistentVolume(RemoveVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        # Return None to simulate volume doesnt' exist
        mock_etcd.get_vol_byname.return_value = None

    def check_response(self, resp):
        msg = 'Volume name to remove not found: %s' % data.VOLUME_NAME
        self._test_case.assertEqual(resp, {u"Err": msg})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.deleteVolume.assert_not_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.delete_vol.assert_not_called()


class TestRemoveVolumeWithChildSnapshot(RemoveVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots

    def check_response(self, resp):
        msg = 'Err: Volume %s has one or more child snapshots - volume ' \
              'cannot be deleted!' % data.VOLUME_NAME
        self._test_case.assertEqual(resp, {u"Err": msg})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.deleteVolume.assert_not_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.delete_vol.assert_not_called()
