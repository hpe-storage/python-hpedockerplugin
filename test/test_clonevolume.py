import mock
import testtools

import fake_3par_data as data
import test_createvolume as createvolume
from hpe3parclient import exceptions


# Variation of CreateVolumeUnitTest. Nothing specific to do here
class CloneVolumeUnitTest(createvolume.CreateVolumeUnitTest):
    pass


# This exercises online-copy path
class TestCloneDefault(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}


# TODO: Rollback is needed for created volume else unit test would fail
class TestCloneDefaultEtcdSaveFails(CloneVolumeUnitTest, testtools.TestCase):
    pass


# Offline copy
class TestCloneOfflineCopy(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.copyVolume.assert_called()


    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME,
                         # Difference in size of source and cloned volume
                         # triggers offline copy. Src volume size is 2.
                         "size": 20}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getTask.return_value = {'status': data.TASK_DONE}


# Make copyVolume operation fail
class TestCloneOfflineCopyFailed(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

        # TODO: Check following were invoked
        # self.client.createVolumeSet(vvs_name, domain)
        # self._set_flash_cache_policy_in_vvs(flash_cache, vvs_name)
        # self.client.addVolumeToVolumeSet(vvs_name, volume_name)

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME,
                         # Difference in size of source and cloned volume
                         # triggers offline copy. Src size is 2.
                         "size": 20}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        # TASK_FAILED simulates failure of copyVolume() operation
        mock_3parclient.getTask.return_value = {'status': data.TASK_FAILED}


class TestCloneInvalidSourceVolume(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME,
                         # Difference in size of source and cloned volume
                         # triggers offline copy. Src volume size is 2.
                         "size": 20}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        # Source volume not found
        mock_etcd.get_vol_byname.return_value = None


# TODO: Make this fail and in validation compare error message
class TestCloneWithInvalidSize(CloneVolumeUnitTest, testtools.TestCase):
    pass

# Online copy with dedup
class TestCloneDedupVolume(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_dedup

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}


# Online copy with flash cache flow
class TestCloneWithFlashCache(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolumeSet.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_flash_cache

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}


# Online copy with flash cache - add to vvset fails
class TestCloneWithFlashCacheAddVVSetFails(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": u'Not found (HTTP 404) - fake'})

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolumeSet.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()
        mock_3parclient.deleteVolumeSet.assert_called()

        # TODO: This is not happening at the moment and would make
        # the unit test fail
        mock_3parclient.deleteVolume.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_flash_cache

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}
        # Make addVolumeToVolumeSet fail by throwing exception
        mock_3parclient.addVolumeToVolumeSet.side_effect = [exceptions.HTTPNotFound('fake')]


# CHAP enabled makes Offline copy flow to execute
class TestCloneWithCHAP(CloneVolumeUnitTest, testtools.TestCase):
    def override_configuration(self, config):
        config.hpe3par_iscsi_chap_enabled = True

    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getVolumeMetaData.assert_called()
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.copyVolume.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getVolumeMetaData.return_value = {'value': True}
        mock_3parclient.getTask.return_value = {'status': data.TASK_DONE}

# TODO: This is already covered in other tests above
class TestCloneWithoutCHAP(CloneVolumeUnitTest, testtools.TestCase):
    pass


# Override WS-API-Version to have lower value
class TestCloneUnsupportedDedupVersion(CloneVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_dedup

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.return_value = \
            {'major': 1,
             # Setting it to lower version that doesn't support dedup
             'build': 20301215,
             'minor': 6,
             'revision': 0}
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}


# TODO: Compression related TCs to be added later
