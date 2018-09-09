import createvolume_tester as createvolume
import fake_3par_data as data


class RevertSnapshotUnitTest(createvolume.CreateVolumeUnitTest):
    pass


class TestCreateSnapRevertVolume(RevertSnapshotUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.isOnlinePhysicalCopy.assert_called()
        mock_3parclient.promoteVirtualCopy.assert_called()

    def get_request_params(self):
        vol_name = data.volume_with_snapshots['name']
        snap_name = data.volume_with_snapshots['snapshots'][0]['name']
        return {"Name": snap_name, "Opts": {"promote": vol_name}}

#    def override_configuration(self, all_configs):
#        all_configs['DEFAULT'].ssh_hosts_key_file = config.ssh_hosts_key_file

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots


class TestSnapRevertVolumeNotExist(RevertSnapshotUnitTest):
    def check_response(self, resp):
        expected_msg = 'Volume: myvolume does not exist'
        self._test_case.assertEqual(resp, {u"Err": expected_msg})

    def get_request_params(self):
        vol_name = 'myvolume'
        snap_name = data.volume_with_snapshots['snapshots'][0]['name']
        return {"Name": snap_name, "Opts": {"promote": vol_name}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None


class TestSnapRevertSnapNotExist(RevertSnapshotUnitTest):
    def check_response(self, resp):
        expected_msg = 'snapshot: mysnapshot does not exist!'
        self._test_case.assertEqual(resp, {u"Err": expected_msg})

    def get_request_params(self):
        vol_name = data.volume_with_snapshots['name']
        snap_name = 'mysnapshot'
        return {"Name": snap_name, "Opts": {"promote": vol_name}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots
