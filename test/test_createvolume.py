# import mock
import setup_mock
import testtools

import hpe_docker_unit_test as hpedockerunittest


class CreateVolumeUnitTest(hpedockerunittest.HpeDockerUnitTest):

    # This function carries out common steps needed by create-volume for
    # different mock-etcd configurations, docker configuration, create-volume
    # requests and checking of responses for success/failure
    @setup_mock.mock_decorator
    def test_create_volume(self, mock_objects):
        self.mock_objects = mock_objects
        operation = 'volumedriver_create'
        self._test_operation(operation)

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    # To be overridden by the derived class if needed
    def override_configuration(self, config):
        pass


class TestCreateVolumeDefault(CreateVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = 'Imran'


# Provisioning = Full
class TestCreateThickVolume(CreateVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = 'Imran'


# Provisioning = Dedup
class TestCreateDedupVolume(CreateVolumeUnitTest, testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = 'Imran'


# FlashCache = True
class TestCreateVolumeWithFlashCache(CreateVolumeUnitTest,
                                     testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = 'Imran'
        # Return CPG dict without 'domain' member
        # cpg = self.client.getCPG(cpg_name)


# FlashCache = True
class TestCreateVolumeFlashCacheAddToVVSFails(CreateVolumeUnitTest,
                                              testtools.TestCase):
    def check_response(self, resp):
        self.assertEqual(resp, {u"Err": ''})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = 'Imran'

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
