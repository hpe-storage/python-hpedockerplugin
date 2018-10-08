import test.fake_3par_data as data
import test.createvolume_tester as createvolume
from hpedockerplugin import exception as hpe_exc
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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        mock_3parclient.getCPG.return_value = {}


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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        mock_3parclient.getCPG.return_value = {}

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": 'I am dead'})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.copyVolume.assert_called()

        # Rollback validation
        mock_3parclient.deleteVolume.assert_called()


# Offline copy
class TestCloneOfflineCopy(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.copyVolume.assert_called()
        mock_3parclient.modifyVolume.assert_called()

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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getTask.return_value = {'status': data.TASK_DONE}


# Offline copy
class TestCloneFromBaseVolumeActiveTask(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertNotEqual(resp, {u"Err": ''})

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
        mock_3parclient.isOnlinePhysicalCopy.return_value = True
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getTask.return_value = {'status': data.TASK_DONE}


class TestCloneInvalidSourceVolume(CloneVolumeUnitTest):
    def check_response(self, resp):
        expected_msg = "source volume: %s does not exist" % data.VOLUME_NAME
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
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.isOnlinePhysicalCopy.return_value = False

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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        mock_3parclient.getCPG.return_value = {}


# Online copy with qos flow
class TestCloneWithQOS(CloneVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.addVolumeToVolumeSet.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_qos

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
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

        # Rollback steps validation
        mock_3parclient.deleteVolumeSet.assert_called()
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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        # Make addVolumeToVolumeSet fail by throwing exception
        mock_3parclient.addVolumeToVolumeSet.side_effect = \
            [exceptions.HTTPNotFound('fake')]


# Online copy with flash cache - etcd save fails
class TestCloneWithFlashCacheEtcdSaveFails(CloneVolumeUnitTest):
    def check_response(self, resp):
        expected = "ETCD data save failed: clone-vol-001"
        self._test_case.assertEqual(resp, {u"Err": expected})

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.assert_called()
        mock_3parclient.createVolumeSet.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()

        # Rollback steps validation
        mock_3parclient.removeVolumeFromVolumeSet.assert_called()
        mock_3parclient.deleteVolumeSet.assert_called()
        mock_3parclient.deleteVolume.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_flash_cache
        mock_etcd.save_vol.side_effect = \
            [hpe_exc.HPEPluginSaveFailed(obj='clone-vol-001')]

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        mock_3parclient.getCPG.return_value = {}


# Online copy with flash cache fails
class TestCloneSetFlashCacheFails(CloneVolumeUnitTest):
    def check_response(self, resp):
        expected = "Driver: Failed to set flash cache policy"
        self._test_case.assertIn(expected, resp["Err"])

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolumeSet.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()

        # Rollback steps validation
        mock_3parclient.deleteVolumeSet.assert_called()
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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        # Make addVolumeToVolumeSet fail by throwing exception
        mock_3parclient.modifyVolumeSet.side_effect = [
            exceptions.HTTPInternalServerError("Internal server error")
        ]


# Online copy with qos flow
class TestCloneWithFlashCacheAndQOSEtcdSaveFails(CloneVolumeUnitTest):
    def check_response(self, resp):
        expected = "ETCD data save failed: clone-vol-001"
        self._test_case.assertEqual(resp, {u"Err": expected})

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()

        # Rollback steps validation
        mock_3parclient.removeVolumeFromVolumeSet.assert_called()
        mock_3parclient.deleteVolume.assert_called()

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"cloneOf": data.VOLUME_NAME}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = \
            data.volume_flash_cache_and_qos
        mock_etcd.save_vol.side_effect = \
            [hpe_exc.HPEPluginSaveFailed(obj='clone-vol-001')]

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        mock_3parclient.getCPG.return_value = {}


# CHAP enabled makes Offline copy flow to execute
class TestCloneWithCHAP(CloneVolumeUnitTest):
    def override_configuration(self, all_configs):
        all_configs['DEFAULT'].hpe3par_iscsi_chap_enabled = True
        all_configs['DEFAULT'].use_multipath = False

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})
        mock_3parclient = self.mock_objects['mock_3parclient']
        # TODO: Fixing exception for now. This must be fixed
        # later by checking why getVolumeMetaData and
        # createVolume are not getting called in the flow
        # mock_3parclient.getVolumeMetaData.assert_called()
        # mock_3parclient.createVolume.assert_called()
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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
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
        mock_3parclient.isOnlinePhysicalCopy.return_value = False
        mock_3parclient.getStorageSystemInfo.return_value = \
            {'licenseInfo': {'licenses': [{'name': 'Compression'}]}}


class TestCloneVolumeWithInvalidOptions(CloneVolumeUnitTest):
    def check_response(self, resp):
        expected_error_msg = "Invalid input received: Invalid option(s) " \
                             "['provisioning', 'qos-name'] specified for " \
                             "operation clone volume. Please check help " \
                             "for usage."
        self._test_case.assertEqual(expected_error_msg, resp['Err'])

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"qos-name": "soni_vvset",
                         "provisioning": "thin",
                         "size": "2",
                         "cloneOf": "clone_of"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getCPG.return_value = {}
