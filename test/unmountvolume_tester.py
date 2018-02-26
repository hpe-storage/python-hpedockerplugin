# import mock
import fake_3par_data as data
import hpe_docker_unit_test as hpedockerunittest
from hpe3parclient import exceptions


class UnmountVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_unmount'

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "ID": "Fake-Mount-ID"}

    def setup_mock_objects(self):
        # Call child class functions to configure mock objects
        self._setup_mock_3parclient()
        self._setup_mock_etcd()
        self._setup_mock_fileutil()
        self._setup_mock_protocol_connector()
        self._setup_mock_osbrick_connector()

    def _setup_mock_etcd(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume
        mock_etcd.get_vol_path_info.return_value = \
            {'path': '/dummy-path',
             'connection_info': {'data': 'dummy-conn-inf'},
             'mount_dir': '/dummy-mnt-dir'}

    def _setup_mock_osbrick_connector(self):
        mock_connector = self.mock_objects['mock_osbricks_connector']

        # Same connector has info for both FC and ISCSI
        mock_connector.get_connector_properties.return_value = \
            data.connector_multipath_enabled

    def _setup_mock_3parclient(self):
        pass

    def _setup_mock_fileutil(self):
        pass

    def _setup_mock_protocol_connector(self):
        pass


# Other volumes are present for the host hence host shouldn't
# get deleted in this case
class TestUnmountOneVolumeForHost(UnmountVolumeUnitTest):

    def _setup_mock_3parclient(self):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryHost.return_value = data.fake_hosts
        # Returning more VLUNs
        mock_3parclient.getHostVLUNs.side_effect = \
            [data.host_vluns, data.host_vluns]

    def check_response(self, resp):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryHost.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        mock_3parclient.deleteVLUN.assert_called()
        mock_3parclient.deleteHost.assert_called()
        # mock_3parclient.removeVolumeMetaData.assert_called()


# Last volume getting unmounted in which case host should also
# get removed
class TestUnmountLastVolumeForHost(UnmountVolumeUnitTest):

    def _setup_mock_3parclient(self):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryHost.return_value = data.fake_hosts
        # Returning HTTPNotFound second time would mean we removed
        # the last LUN and hence VHOST should be removed
        mock_3parclient.getHostVLUNs.side_effect = \
            [data.host_vluns, exceptions.HTTPNotFound('fake')]

    def check_response(self, resp):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryHost.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        mock_3parclient.deleteVLUN.assert_called()
        mock_3parclient.deleteHost.assert_called()
        # mock_3parclient.removeVolumeMetaData.assert_called()

# # TODO:
# class TestUnmountVolumeChapCredentialsNotFound(UnmountVolumeUnitTest):
#     pass

# class TestUnmountVolumeHostSeesRemoveVHost(UnmountVolumeUnitTest)
# class TestUnmountVolumeHostSeesKeepVHost(UnmountVolumeUnitTest):
