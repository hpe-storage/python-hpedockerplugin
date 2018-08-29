# import mock
import createvolume_tester as createvolume
import fake_3par_data as data


# Derives all the functionality from CreteVolumeUnitTest itself
class CreateSnapshotUnitTest(createvolume.CreateVolumeUnitTest):
    pass


# This exercises online-copy path
class TestCreateSnapshotDefault(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": "snap-001",
                "Opts": {"snapshotOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Ensure that createSnapshot was called on 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createSnapshot.assert_called()


class TestCreateSnapshotWithExpiryRetentionTimes(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": "snap-001",
                "Opts": {"snapshotOf": data.VOLUME_NAME,
                         "expirationHours": '10',
                         "retentionHours": '5'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Ensure that createSnapshot was called on 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createSnapshot.assert_called()


# Tries to create snapshot with retention time > expiry time. This should fail.
class TestCreateSnapshotWithInvalidTimes(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": "snap-001",
                "Opts": {"snapshotOf": data.VOLUME_NAME,
                         "expirationHours": '10',
                         "retentionHours": '20'}}

    def check_response(self, resp):
        # TODO: Implement this check in the actual flow
        self._test_case.assertEqual(resp,
                                    {u"Err": 'retention time cannot be '
                                             'greater than expiration time'})


# Tries to create snapshot for a non-existent volume
class TestCreateSnapshotForNonExistentVolume(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": "snap-001",
                "Opts": {"snapshotOf": 'i_do_not_exist_volume'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def check_response(self, resp):
        expected = 'source volume: %s does not exist' % \
                   'i_do_not_exist_volume'
        self._test_case.assertEqual(resp, {u"Err": expected})


# class TestCreateSnapshotUnauthorized(CreateSnapshotUnitTest):
#     pass
