import fake_3par_data as data
import hpe_docker_unit_test as hpedockerunittest


class RemoveSnapshotUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):

    def _get_plugin_api(self):
        return 'volumedriver_remove'

    # def setup_mock_objects(self):
    #     mock_etcd = self.mock_objects['mock_etcd']
    #     mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots

    def check_response(self, resp):
        pass

    # To be overridden by the derived class if needed
    def override_configuration(self, config):
        pass


class TestRemoveSnapshot(RemoveSnapshotUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        parent_volume_name = data.volume_with_snapshots['name']
        snapshot_name = data.volume_with_snapshots['snapshots'][0]['name']
        snapshot_path = '/'.join([parent_volume_name, snapshot_name])
        return {"Name": snapshot_path}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots


# Tries to remove a snapshot present at the second level
# This shouldn't even enter driver code
class TestRemoveMultilevelSnapshot(RemoveSnapshotUnitTest):
    def get_request_params(self):
        parent_volume_name = data.volume_with_snapshots['name']
        snapshot_name = 'snap01/snap02'
        self.snapshot_path = '/'.join([parent_volume_name, snapshot_name])
        return {"Name": self.snapshot_path}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = \
            data.volume_with_multilevel_snapshot

    def check_response(self, resp):
        expected = {u"Err": 'invalid volume or snapshot name %s'
                            % self.snapshot_path}
        self._test_case.assertEqual(resp, expected)


# Remove snapshot that has child snapshot(s)
# Creation of multi-level snapshot is not supported as of now
# This would help in case it is supported in the future
class TestRemoveSnapshotWithChildSnapshots(RemoveSnapshotUnitTest):
    def get_request_params(self):
        parent_volume_name = data.volume_with_snapshots['name']
        snapshot_name = data.volume_with_snapshots['snapshots'][0]['name']
        self.snapshot_path = '/'.join([parent_volume_name, snapshot_name])
        return {"Name": self.snapshot_path}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = \
            data.volume_with_multilevel_snapshot

    def check_response(self, resp):
        expected = {u"Err": 'snapshot %s has one or more child snapshots - it'
                            ' cannot be deleted!' % self.snapshot_path}
        self._test_case.assertEqual(resp, expected)


class TestRemoveNonExistentSnapshot(RemoveSnapshotUnitTest):
    def get_request_params(self):
        parent_volume_name = data.volume_with_snapshots['name']
        self.snapshot_name = 'non-existent-snapshot'
        snapshot_path = '/'.join([parent_volume_name,
                                  self.snapshot_name])
        return {"Name": snapshot_path}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = \
            data.volume_with_multilevel_snapshot

    def check_response(self, resp):
        expected = {u'Err': u'snapshot %s does not exist!'
                    % self.snapshot_name}
        self._test_case.assertEqual(resp, expected)
