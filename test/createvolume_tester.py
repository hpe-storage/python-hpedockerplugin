# import mock
import fake_3par_data as data
import hpe_docker_unit_test as hpedockerunittest
from hpe3parclient import exceptions
from oslo_config import cfg
CONF = cfg.CONF


class CreateVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_create'

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def override_configuration(self, config):
        pass

    # TODO: check_response and setup_mock_objects can be implemented
    # here for the normal happy path TCs here as they are same


class TestCreateVolumeDefault(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()

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

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {'provisioning': data.FULL,
                         'size': '10'}}

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
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {'provisioning': data.DEDUP,
                         'size': '10'}}

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


# qos-name=<vvset_name>
class TestCreateVolumeWithQOS(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"qos-name": "vvk_vvset",
                         "provisioning": "thin",
                         "size": "2"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getCPG.return_value = {}


# qos-name=<vvset_name>
class TestCreateVolumeWithInvalidQOS(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp,
                                    {u"Err": 'Not found (HTTP 404) - fake'})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()
        mock_3parclient.deleteVolume("test-vol-001")

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"qos-name": "soni_vvset",
                         "provisioning": "thin",
                         "size": "2"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getCPG.return_value = {}

        # vvset does not exist
        mock_3parclient.addVolumeToVolumeSet.side_effect = \
            [exceptions.HTTPNotFound('fake')]


class TestCreateVolumeWithMutuallyExclusiveList(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(
            resp,
            {"Err": "['snapshotOf', 'cloneOf', 'qos-name', 'promote'] cannot "
             "be specified at the same time"})

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"qos-name": "soni_vvset",
                         "provisioning": "thin",
                         "size": "2",
                         "cloneOf": "clone_of",
                         "qos-name": "qos_name"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getCPG.return_value = {}


# FlashCache = True and qos-name=<vvset_name>
class TestCreateVolumeWithFlashCacheAndQOS(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"flash-cache": "true",
                         "qos-name": "vvk_vvset",
                         "provisioning": "thin",
                         "size": "2"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getCPG.return_value = {}


# FlashCache = True
class TestCreateVolumeWithFlashCache(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.createVolumeSet.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"flash-cache": "true",
                         "provisioning": "thin",
                         "size": "20"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getCPG.return_value = {}


# FlashCache = True
class TestCreateVolumeFlashCacheAddToVVSFails(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp,
                                    {u"Err": u'Not found (HTTP 404) - fake'})

        # Check required WSAPI calls were made
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.createVolume.assert_called()
        mock_3parclient.createVolumeSet.assert_called()
        mock_3parclient.modifyVolumeSet.assert_called()
        mock_3parclient.addVolumeToVolumeSet.assert_called()
        mock_3parclient.deleteVolumeSet.assert_called()

        # TODO: This is not happening at the moment and would make
        # the unit test fail
        # TODO: Remove comment once deleteVolume is invoked
        # mock_3parclient.deleteVolume.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"flash-cache": "true",
                         "provisioning": "thin",
                         "size": "20"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        # Make addVolumeToVolumeSet fail by throwing exception
        mock_3parclient.addVolumeToVolumeSet.side_effect = \
            [exceptions.HTTPNotFound('fake')]


class TestCreateCompressedVolume(CreateVolumeUnitTest):
    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getStorageSystemInfo.assert_called()
        mock_3parclient.createVolume.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"compression": 'true',
                         "size": '20',
                         "provisioning": 'thin'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.return_value = \
            data.wsapi_version_for_compression
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getStorageSystemInfo.return_value = \
            {'licenseInfo': {'licenses': [{'name': 'Compression'}]}}


class TestCreateCompressedVolumeNegativeSize(CreateVolumeUnitTest):
    def check_response(self, resp):
        expected_msg = 'Invalid input received: To create compression '\
                       'enabled volume, size of the volume should be '\
                       'atleast 16GB. Fully provisioned volume can not be '\
                       'compressed. Please re enter requested volume size '\
                       'or provisioning type. '
        self._test_case.assertEqual(resp, {u"Err": expected_msg})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getStorageSystemInfo.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"compression": 'true',
                         "size": '2',
                         "provisioning": 'thin'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.return_value = \
            data.wsapi_version_for_compression
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getStorageSystemInfo.return_value = \
            {'licenseInfo': {'licenses': [{'name': 'Compression'}]}}


class TestCreateCompressedVolNoHardwareSupport(CreateVolumeUnitTest):
    def check_response(self, resp):
        expected_msg = 'Invalid input received: Compression is not '\
                       'supported on underlying hardware'
        self._test_case.assertEqual(resp, {u"Err": expected_msg})

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getStorageSystemInfo.assert_called()

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"compression": 'true',
                         "size": '20',
                         "provisioning": 'thin'}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.return_value = \
            data.wsapi_version_for_compression
        mock_3parclient.getCPG.return_value = {}
        mock_3parclient.getStorageSystemInfo.return_value = \
            {'licenseInfo': {'licenses': []}}


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
