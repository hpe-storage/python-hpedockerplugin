# import mock
import fake_3par_data as data

import hpe_docker_unit_test as hpedockerunittest


class CreateVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):

    # This function carries out common steps needed by create-volume for
    # different mock-etcd configurations, docker configuration, create-volume
    # requests and checking of responses for success/failure
    def run_test(self, protocol):
        # This is important to set as it is used by the base class to
        # take decision which driver to instantiate
        self._protocol = protocol
        operation = 'volumedriver_create'
        self._test_operation(operation)

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def override_configuration(self, config):
        pass


# class TestCreateVolumeDefault(CreateVolumeUnitTest, testtools.TestCase):
class TestCreateVolumeDefault(CreateVolumeUnitTest):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None


# Provisioning = Full
class TestCreateThickVolume(CreateVolumeUnitTest):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {'provisioning': data.FULL}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None


# Provisioning = Dedup
class TestCreateDedupVolume(CreateVolumeUnitTest):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {'provisioning': data.DEDUP}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None


# FlashCache = True
class TestCreateVolumeWithFlashCache(CreateVolumeUnitTest):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

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
        self.assertEqual(resp, {u"Err": ''})

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
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "clone-vol-001",
                "Opts": {"compression": 'true'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

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
