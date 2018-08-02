# import mock
import copy

import test.createvolume_tester as createvolume
import test.fake_3par_data as data
from hpedockerplugin import exception as hpe_exc


# Derives all the functionality from CreteVolumeUnitTest itself
class CreateSnapshotUnitTest(createvolume.CreateVolumeUnitTest):
    pass


# This exercises online-copy path
class TestCreateSnapshotDefault(CreateSnapshotUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._parent_vol = copy.deepcopy(data.volume)

    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME1,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            data.volume,
            None,
            copy.deepcopy(data.volume),
            None
        ]

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Ensure that createSnapshot was called on 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createSnapshot.assert_called()


class TestCreateSnapshotWithExpiryRetentionTimes(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME1,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "expirationHours": '10',
                         "retentionHours": '5'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            data.volume,
            None,
            copy.deepcopy(data.volume)
        ]

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Ensure that createSnapshot was called on 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createSnapshot.assert_called()


# Tries to create a snapshot with a duplicate name
class TestCreateSnapshotDuplicateName(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME1,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.snap1

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": 'snapshot snapshot-1'
                                                   ' already exists'})


# Tries to create snapshot with retention time > expiry time. This should fail.
class TestCreateSnapshotWithInvalidTimes(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": "snap-001",
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
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
                "Opts": {"virtualCopyOf": 'i_do_not_exist_volume'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            None,
            None
        ]

    def check_response(self, resp):
        expected = 'source volume: %s does not exist' % \
                   'i_do_not_exist_volume'
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnapshotEtcdSaveFails(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME1,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            data.volume,
            None,
            copy.deepcopy(data.volume)
        ]
        mock_etcd.save_vol.side_effect = \
            [hpe_exc.HPEPluginSaveFailed(obj='snap-001')]

    def check_response(self, resp):
        expected = "ETCD data save failed: snap-001"
        self._test_case.assertEqual(resp, {u"Err": expected})

        # Ensure that createSnapshot was called on 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createSnapshot.assert_called()

        # Rollback
        mock_3parclient.deleteVolume.assert_called()

# class TestCreateSnapshotUnauthorized(CreateSnapshotUnitTest):
#     pass
