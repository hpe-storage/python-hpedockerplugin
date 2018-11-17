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
        volume = copy.deepcopy(data.volume)
        mock_etcd.get_vol_byname.side_effect = [
            volume,
            None,
            volume,
            None
        ]
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.isOnlinePhysicalCopy.return_value = False

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
        volume = copy.deepcopy(data.volume)
        mock_etcd.get_vol_byname.side_effect = [
            volume,
            None,
            volume
        ]
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.isOnlinePhysicalCopy.return_value = False

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
        expected = 'Volume/Snapshot %s does not exist' % \
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
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.isOnlinePhysicalCopy.return_value = False

    def check_response(self, resp):
        expected = "ETCD data save failed: snap-001"
        self._test_case.assertEqual(resp, {u"Err": expected})

        # Ensure that createSnapshot was called on 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createSnapshot.assert_called()

        # Rollback
        mock_3parclient.deleteVolume.assert_called()


class TestCreateSnpSchedule(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleName": '3parsched1',
                         "scheduleFrequency": "10 * * * *",
                         "snapshotPrefix": "pqrst",
                         "expHrs": '4',
                         "retHrs": '2'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            data.volume,
            None,
            copy.deepcopy(data.volume)
        ]
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.isOnlinePhysicalCopy.return_value = False

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Ensure that createSnapshot was called on 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient._run.assert_called()
        mock_3parclient.createSnapshot.assert_called()


class TestCreateSnpSchedNegFreq(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleName": '3parsched1',
                         "snapshotPrefix": "pqrst",
                         "expHrs": '4',
                         "retHrs": '2'}}

    def check_response(self, resp):
        opts = ['scheduleName', 'snapshotPrefix', 'scheduleFrequency']
        opts.sort()
        expected = "Invalid input received: One or more mandatory options " \
                   "%s are missing for operation create snapshot schedule" \
                   % opts
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnpSchedNegPrefx(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleName": '3parsched1',
                         "scheduleFrequency": "10 * * * *",
                         "expHrs": '4',
                         "retHrs": '2'}}

    def check_response(self, resp):
        opts = ['scheduleName', 'snapshotPrefix', 'scheduleFrequency']
        opts.sort()
        expected = "Invalid input received: One or more mandatory options " \
                   "%s are missing for operation create snapshot schedule" \
                   % opts
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnpSchedInvPrefxLen(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleName": '3parsched1',
                         "scheduleFrequency": "10 * * * *",
                         "snapshotPrefix": "pqrstwdstyuijowkdlasihguf",
                         "expHrs": '4',
                         "retHrs": '2'}}

    def check_response(self, resp):
        expected = 'Please provide a schedlueName with max 31 characters '\
                   'and snapshotPrefix with max length of 15 characters'
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnpSchedNoSchedName(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleFrequency": "10 * * * *",
                         "snapshotPrefix": "pqrst",
                         "expHrs": '4',
                         "retHrs": '2'}}

    def check_response(self, resp):
        opts = ['scheduleName', 'snapshotPrefix', 'scheduleFrequency']
        opts.sort()
        expected = "Invalid input received: One or more mandatory options " \
                   "%s are missing for operation create snapshot schedule" \
                   % opts
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnpSchedwithRetToBase(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleName": '3parsched1',
                         "scheduleFrequency": "10 * * * *",
                         "snapshotPrefix": "pqrst",
                         "retentionHours": '5',
                         "expHrs": '4',
                         "retHrs": '2'}}

    def check_response(self, resp):
        invalid_opts = ['retentionHours']
        expected = "Invalid input received: Invalid option(s) %s " \
                   "specified for operation create snapshot schedule. " \
                   "Please check help for usage." % invalid_opts
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnpSchedRetExpNeg(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleName": '3parsched1',
                         "scheduleFrequency": "10 * * * *",
                         "snapshotPrefix": "pqrst",
                         "expHrs": '2',
                         "retHrs": '4'}}

    def check_response(self, resp):
        expected = 'create schedule failed, error is: expiration hours '\
                   'cannot be greater than retention hours'
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnpSchedInvSchedFreq(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "scheduleName": '3parsched1',
                         "scheduleFrequency": "10 * * * * *",
                         "snapshotPrefix": "pqrst",
                         "expHrs": '4',
                         "retHrs": '2'}}

    def check_response(self, resp):
        expected = 'Invalid schedule string is passed: HPE Docker Volume '\
                   'plugin Create volume failed: create schedule failed, '\
                   'error is: Improper string passed. '
        self._test_case.assertEqual(resp, {u"Err": expected})


class TestCreateSnapshotInvalidOptions(CreateSnapshotUnitTest):
    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME4,
                "Opts": {"virtualCopyOf": data.VOLUME_NAME,
                         "mountConflictDelay": 22,
                         "backend": "dummy"}}

    def check_response(self, resp):
        invalid_opts = ['backend']
        invalid_opts.sort()
        expected = "Invalid input received: Invalid option(s) " \
                   "%s specified for operation create snapshot. " \
                   "Please check help for usage." % invalid_opts
        self._test_case.assertEqual(resp, {u"Err": expected})

# class TestCreateSnapshotUnauthorized(CreateSnapshotUnitTest):
#     pass
