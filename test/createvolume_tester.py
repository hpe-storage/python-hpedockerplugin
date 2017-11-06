# import mock
import fake_3par_data as data
import hpe_docker_unit_test as hpedockerunittest


class CreateVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_create'

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def override_configuration(self, config):
        pass


class TestCreateVolumeDefault(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None


# Provisioning = Full
class TestCreateThickVolume(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {'provisioning': data.FULL}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None


# Provisioning = Dedup
class TestCreateDedupVolume(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {'provisioning': data.DEDUP}}

    # Configure mock objects to return the desired values
    # from the function calls in the actual flow
    def setup_mock_objects(self):
        # Let ETCD confirm that the volume being created
        # is not there already which is done by returning
        # None for "get_vol_by_name" call
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        # Correct WSAPI version needs to be set for dedup feature
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.return_value = \
            data.wsapi_version_for_dedup


# FlashCache = True
class TestCreateVolumeWithFlashCache(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None
        # Return CPG dict without 'domain' member
        # cpg = self.client.getCPG(cpg_name)


# FlashCache = True
class TestCreateVolumeFlashCacheAddToVVSFails(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        # try:
        #     self._set_flash_cache_policy_in_vvs(flash_cache, vvs_name)
        #     self.client.addVolumeToVolumeSet(vvs_name, volume_name)
        # except Exception as ex:
        #     # Cleanup the volume set if unable to create the qos rule
        #     # or flash cache policy or add the volume to the volume set
        # TODO: Ensure that deleteVolumeSet is invoked here
        #     self.client.deleteVolumeSet(vvs_name)
        # TODO: Handle this
        #     raise exception.PluginException(ex)


class TestCompressedVolume(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"compression": 'true'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.return_value = \
            data.wsapi_version_for_compression
        mock_3parclient.copyVolume.return_value = {'taskid': data.TASK_ID}
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getStorageSystemInfo.return_value = \
            {'licenseInfo': {'licenses': [{'name': 'Compression'}]}}

# More cases of flash cache
# 1.
# if flash_cache:
#     try:
#         self.client.modifyVolumeSet(vvs_name,
#                                     flashCachePolicy=flash_cache)
#         LOG.info(_LI("Flash Cache policy set to %s"), flash_cache)
#     except Exception as ex:
#         LOG.error(_LE("Error setting Flash Cache policy "
#                       "to %s - exception"), flash_cache)
#         exception.PluginException(ex)
