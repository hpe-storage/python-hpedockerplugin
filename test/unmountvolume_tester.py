# import mock
import copy

import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest
from hpe3parclient import exceptions


class UnmountVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def __init__(self, is_snap=False):
        self._is_snap = is_snap
        self._vol = copy.deepcopy(data.vol_mounted_on_this_node)
        if is_snap:
            self._vol['id'] = data.SNAPSHOT_ID1
            self._vol['name'] = data.SNAPSHOT_ID1
            self._vol['display_name'] = data.SNAPSHOT_NAME1
            self._vol['is_snap'] = True

    def _get_plugin_api(self):
        return 'volumedriver_unmount'

    def get_request_params(self):
        return {"Name": self._vol['display_name'],
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
        mock_etcd.get_vol_byname.return_value = self._vol
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
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def _setup_mock_3parclient(self):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryHost.return_value = data.fake_hosts
        # Returning more VLUNs
        if not self._is_snap:
            mock_3parclient.getHostVLUNs.side_effect = \
                [data.host_vluns, data.host_vluns]
        else:
            mock_3parclient.getHostVLUNs.side_effect = \
                [data.snap_host_vluns, data.snap_host_vluns]

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
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def _setup_mock_3parclient(self):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryHost.return_value = data.fake_hosts
        # Returning HTTPNotFound second time would mean we removed
        # the last LUN and hence VHOST should be removed
        if not self._is_snap:
            mock_3parclient.getHostVLUNs.side_effect = \
                [data.host_vluns, exceptions.HTTPNotFound('fake')]
        else:
            mock_3parclient.getHostVLUNs.side_effect = \
                [data.snap_host_vluns, exceptions.HTTPNotFound('fake')]

    def check_response(self, resp):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryHost.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        mock_3parclient.deleteVLUN.assert_called()
        mock_3parclient.deleteHost.assert_called()
        # mock_3parclient.removeVolumeMetaData.assert_called()


# Volume is mounted on the same node more than once
# Unmount once should not
class TestUnmountVolOnceMountedTwiceOnThisNode(UnmountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._vol = copy.deepcopy(data.volume_mounted_twice_on_this_node)
        if self._is_snap:
            self._vol['name'] = data.SNAPSHOT_NAME1
            self._vol['id'] = data.SNAPSHOT_ID1
            self._vol['display_name'] = data.SNAPSHOT_NAME1
            self._vol['is_snap'] = True

    def _setup_mock_etcd(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = self._vol

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.update_vol.assert_called_with(self._vol['id'],
                                                'node_mount_info',
                                                self._vol['node_mount_info'])

        # node_id_list should have only one node-id left after
        # un-mount is called
        self._test_case.assertEqual(len(self._vol['node_mount_info']
                                        [data.THIS_NODE_ID]), 1)

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryHost.assert_not_called()
        mock_3parclient.getHostVLUNs.assert_not_called()
        mock_3parclient.deleteVLUN.assert_not_called()
        mock_3parclient.deleteHost.assert_not_called()


# Volume is mounted on the same node more than once
# Unmount once should not
class TestUnmountVolMountedTwiceOnThisNode(UnmountVolumeUnitTest):
    # This TC needs to be executed twice from outside and for each
    # execution, the state of volume gets modified. Setting up
    # the volume object to be used across two runs along with
    # the run-count that is used to take decisions
    def __init__(self, tc_run_cnt, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._tc_run_cnt = tc_run_cnt
        self._vol = copy.deepcopy(data.volume_mounted_twice_on_this_node)

    def _setup_mock_3parclient(self):
        if self._tc_run_cnt == 1:
            mock_3parclient = self.mock_objects['mock_3parclient']
            mock_3parclient.queryHost.return_value = data.fake_hosts
            # Returning more VLUNs
            if not self._is_snap:
                mock_3parclient.getHostVLUNs.side_effect = \
                    [data.host_vluns, data.host_vluns]
            else:
                mock_3parclient.getHostVLUNs.side_effect = \
                    [data.snap_host_vluns, data.snap_host_vluns]

    def _setup_mock_etcd(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = self._vol
        mock_etcd.get_vol_path_info.return_value = \
            {'path': '/dummy-path',
             'connection_info': {'data': 'dummy-conn-inf'},
             'mount_dir': '/dummy-mnt-dir'}

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        vol = self._vol
        mock_etcd = self.mock_objects['mock_etcd']
        if self._tc_run_cnt == 0:
            mock_etcd.update_vol.assert_called_with(vol['id'],
                                                    'node_mount_info',
                                                    vol['node_mount_info'])
            # node_id_list should have only one node-id left after
            # un-mount is called
            self._test_case.assertEqual(len(vol['node_mount_info']
                                            [data.THIS_NODE_ID]), 1)
        elif self._tc_run_cnt == 1:
            mock_etcd.save_vol.assert_called_with(vol)
            self._test_case.assertNotIn('node_mount_info',
                                        self._vol)

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        if self._tc_run_cnt == 0:
            mock_3parclient.queryHost.assert_not_called()
            mock_3parclient.getHostVLUNs.assert_not_called()
            mock_3parclient.deleteVLUN.assert_not_called()
            mock_3parclient.deleteHost.assert_not_called()
        elif self._tc_run_cnt == 1:
            mock_3parclient.queryHost.assert_called()
            mock_3parclient.getHostVLUNs.assert_called()
            mock_3parclient.deleteVLUN.assert_called()
            mock_3parclient.deleteHost.assert_called()

        self._tc_run_cnt += 1


# This TC should carry out the cleanup steps
class TestUnmountVolNotOwnedByThisNode(UnmountVolumeUnitTest):
    # This TC needs to be executed twice from outside and for each
    # execution, the state of volume gets modified. Setting up
    # the volume object to be used across two runs along with
    # the run-count that is used to take decisions
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._vol = copy.deepcopy(data.vol_mounted_on_other_node)

    def _setup_mock_3parclient(self):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryHost.return_value = data.fake_hosts
        # Returning more VLUNs
        if not self._is_snap:
            mock_3parclient.getHostVLUNs.side_effect = \
                [data.host_vluns, data.host_vluns]
        else:
            mock_3parclient.getHostVLUNs.side_effect = \
                [data.snap_host_vluns, data.snap_host_vluns]

    def _setup_mock_etcd(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = self._vol
        mock_etcd.get_vol_path_info.return_value = \
            {'path': '/dummy-path',
             'connection_info': {'data': 'dummy-conn-inf'},
             'mount_dir': '/dummy-mnt-dir'}

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        vol = self._vol
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.save_vol.assert_called_with(vol)
        self._test_case.assertIn('node_mount_info',
                                 self._vol)

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryHost.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        mock_3parclient.deleteVLUN.assert_called()
        mock_3parclient.deleteHost.assert_called()

# # TODO:
# class TestUnmountVolumeChapCredentialsNotFound(UnmountVolumeUnitTest):
#     pass

# class TestUnmountVolumeHostSeesRemoveVHost(UnmountVolumeUnitTest)
# class TestUnmountVolumeHostSeesKeepVHost(UnmountVolumeUnitTest):
