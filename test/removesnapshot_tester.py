import copy
import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest


class RemoveSnapshotUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):

    def _get_plugin_api(self):
        return 'volumedriver_remove'

    # def setup_mock_objects(self):
    #     mock_etcd = self.mock_objects['mock_etcd']
    #     mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots

    def check_response(self, resp):
        pass

    # To be overridden by the derived class if needed
    def override_configuration(self, all_configs):
        pass


class TestRemoveSnapshot(RemoveSnapshotUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": data.snap1['display_name']}

    def setup_mock_objects(self):
        parent_vol = copy.deepcopy(data.volume_with_snapshots)
        snapshot = copy.deepcopy(data.snap1)
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            snapshot,
            snapshot,
            parent_vol
        ]


class TestRemoveSnapshotSchedule(RemoveSnapshotUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": data.snap4['display_name']}

    def setup_mock_objects(self):
        parent_vol = copy.deepcopy(data.volume_with_snap_schedule)
        snapshot = copy.deepcopy(data.snap4)
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            snapshot,
            snapshot,
            parent_vol
        ]


# # Tries to remove a snapshot present at the second level
# # This shouldn't even enter driver code
# class TestRemoveMultilevelSnapshot(RemoveSnapshotUnitTest):
#     def get_request_params(self):
#         parent_volume_name = data.volume_with_multilevel_snapshot['name']
#         snapshot_name = 'snap01/snap02'
#         self.snapshot_path = '/'.join([parent_volume_name, snapshot_name])
#         return {"Name": self.snapshot_path}
#
#     def setup_mock_objects(self):
#         mock_etcd = self.mock_objects['mock_etcd']
#         mock_etcd.get_vol_byname.return_value = \
#             copy.deepcopy(data.volume_with_multilevel_snapshot)
#
#     def check_response(self, resp):
#         expected = {u"Err": 'invalid volume or snapshot name %s'
#                             % self.snapshot_path}
#         self._test_case.assertEqual(resp, expected)


# # Remove snapshot that has child snapshot(s)
# # Creation of multi-level snapshot is not supported as of now
# # This would help in case it is supported in the future
# class TestRemoveSnapshotWithChildSnapshots(RemoveSnapshotUnitTest):
#     def get_request_params(self):
#         parent_volume_name = data.volume_with_multilevel_snapshot['name']
#         snapshot_name = data.snap1['name']
#         self.snapshot_path = '/'.join([parent_volume_name, snapshot_name])
#         return {"Name": self.snapshot_path}
#
#     def setup_mock_objects(self):
#         mock_etcd = self.mock_objects['mock_etcd']
#         mock_etcd.get_vol_byname.return_value = \
#             copy.deepcopy(data.volume_with_multilevel_snapshot)
#
#     def check_response(self, resp):
#         expected = {u"Err": 'snapshot %s has one or more child snapshots '
#                             '- it cannot be deleted!' % self.snapshot_path}
#         self._test_case.assertEqual(resp, expected)


class TestRemoveNonExistentSnapshot(RemoveSnapshotUnitTest):
    def get_request_params(self):
        self.snapshot_name = 'non-existent-snapshot'
        return {"Name": self.snapshot_name}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def check_response(self, resp):
        msg = 'Volume name to remove not found: %s' % self.snapshot_name
        expected = {u'Err': msg}
        self._test_case.assertEqual(expected, resp)
