# import mock
import fake_3par_data as data
import createvolume_tester as createvolume
from hpe3parclient import exceptions


# Variation of CreateVolumeUnitTest. Nothing specific to do here
class CloneVolumeUnitTest(createvolume.CreateVolumeUnitTest):
    pass


# This exercises online-copy path
class TestCloneDefault(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
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


# TODO: Rollback is needed for created volume else unit test would fail
class TestCloneDefaultEtcdSaveFails(CloneVolumeUnitTest):
    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume
        # Make save_vol fail with exception
        mock_etcd.save_vol.side_effect = [Exception("I am dead")]

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": 'I am dead'})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.copyVolume.assert_called()
        # TODO: TC will fail as this is not happening today
        # Again for online copy, we may not be able to delete the
        # volume immediately. We may have to wait for online copy
        # to complete. Or we may just fire delete volume hoping
        # 3PAR will take care of deletion after online copy
        # and eat up exception return by deleteVolume
        mock_3parclient.deleteVolume.assert_called()


# Offline copy
class TestCloneOfflineCopy(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.copyVolume.assert_called()
        mock_3parclient.getTask.assert_called()

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
class TestCloneOfflineCopyFails(CloneVolumeUnitTest):
    def check_response(self, resp):
        # Match error substring with returned error string
        err_received = resp['Err']
        err_expected = 'copy volume task failed: create_cloned_volume'
        self._test_case.assertIn(err_expected, err_received)

        # Check following 3PAR APIs were invoked
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.copyVolume.assert_called()
        mock_3parclient.getTask.assert_called()

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


class TestCloneInvalidSourceVolume(CloneVolumeUnitTest):
    def check_response(self, resp):
        expected_msg = "source volume: %s does not exist" % None
        self._test_case.assertEqual(resp, {u"Err": expected_msg})

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME,
                         # Difference in size of source and cloned volume
                         # triggers offline copy. Src volume size is 2.
                         "size": '20'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        # Source volume not found
        mock_etcd.get_vol_byname.return_value = None


# TODO: Make this fail and in validation compare error message
class TestCloneWithInvalidSize(CloneVolumeUnitTest):
    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME,
                         # Difference in size of source and cloned volume
                         # triggers offline copy. Src volume size is 2.
                         "size": '1'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        # Source volume that is to be cloned
        mock_etcd.get_vol_byname.return_value = data.volume

    def check_response(self, resp):
        expected_msg = "clone volume size 1 is less than source volume size 2"
        self._test_case.assertEqual(resp, {u"Err": expected_msg})


# Online copy with dedup
class TestCloneDedupVolume(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.copyVolume.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME,
                         # Keep same size to invoke online copy
                         "size": str(data.volume_dedup['size'])}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_dedup

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}


# Online copy with flash cache flow
class TestCloneWithFlashCache(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

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
class TestCloneWithFlashCacheAddVVSetFails(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp,
                                    {u"Err": u'Not found (HTTP 404) - fake'})

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolumeSet.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()
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
        mock_3parclient.addVolumeToVolumeSet.side_effect = \
            [exceptions.HTTPNotFound('fake')]


# CHAP enabled makes Offline copy flow to execute
class TestCloneWithCHAP(CloneVolumeUnitTest):
    def override_configuration(self, config):
        config.hpe3par_iscsi_chap_enabled = True

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
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


# TODO: Compression related TCs to be added later
class TestCloneCompressedVolume(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.copyVolume.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME,
                         "compression": 'true',
                         "size": '16'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_compression

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.return_value = \
            {'major': 1,
             # Setting it to lower version that doesn't support dedup
             'build': 30301215,
             'minor': 6,
             'revision': 0}
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getStorageSystemInfo.return_value = \
            {'licenseInfo': {'licenses': [{'name': 'Compression'}]}}
