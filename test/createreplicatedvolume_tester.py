import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpeunittest
from hpe3parclient import exceptions
from oslo_config import cfg
CONF = cfg.CONF


class CreateReplicatedVolumeUnitTest(hpeunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_create'

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def override_configuration(self, all_configs):
        pass

    # TODO: check_response and setup_mock_objects can be implemented
    # here for the normal happy path TCs here as they are same


class TestCreateVolumeDefaultFails(CreateReplicatedVolumeUnitTest):
    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()


class TestCreateReplicatedVolumeAndRCG(CreateReplicatedVolumeUnitTest):
    def __init__(self, backend_name):
        self._backend_name = backend_name

    def get_request_params(self):
        return {"Name": data.DOCKER_VOL_NAME,
                "Opts": {"replicationGroup": data.RCG_NAME,
                         "backend": self._backend_name}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        # Allow RCG creation flow to execute
        mock_3parclient = self.mock_objects['mock_3parclient']
        exc_msg = 'RCG not found: %s' % data.RCG_NAME
        mock_3parclient.getRemoteCopyGroup.side_effect = \
            [
                # Simulate that RCG doesn't exist
                exceptions.HTTPNotFound(exc_msg),
                # Post RCG create, fetch RCG from array to get remote RCG name
                {'remoteGroupName': data.REMOTE_RCG_NAME},
                # Add volume to RCG requires RCG state of the created group
                {'targets': [{'state': data.RCG_STARTED}]},
            ]

        # Called during RCG creation flow to fetch domain from CPG
        mock_3parclient.getCPG.return_value = {}

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": ''})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()

        mock_3parclient.createRemoteCopyGroup.assert_called()

        # In case of Peer Persistence, autoFailover and pathManagement
        # policies are applied for which modifyRemoteCopyGroup is invoked
        if self._backend_name == '3par_pp_rep':
            mock_3parclient.modifyRemoteCopyGroup.assert_called()

        # Since we are returning RCG_STARTED in setup_mock_objects
        # add_volume_to_rcg_group flow stops the group before adding
        # volume to the RCG
        mock_3parclient.stopRemoteCopy.assert_called()
        mock_3parclient.addVolumeToRemoteCopyGroup.assert_called()
        mock_3parclient.startRemoteCopy.assert_called()


class TestCreateReplicatedVolumeAndRCGCreateFails(
        CreateReplicatedVolumeUnitTest):
    def __init__(self, backend_name):
        self._backend_name = backend_name
        self._expected_resp = 'Bad or unexpected response from the RCG ' \
                              'backend API: Error encountered while ' \
                              'creating remote copy group: Bad request ' \
                              '(HTTP 400) - Create RCG failed: TEST-RCG'

    def get_request_params(self):
        return {"Name": data.DOCKER_VOL_NAME,
                "Opts": {"replicationGroup": data.RCG_NAME,
                         "backend": self._backend_name}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = None

        # Allow RCG creation flow to execute
        mock_3parclient = self.mock_objects['mock_3parclient']
        exc_msg = 'RCG not found: %s' % data.RCG_NAME
        mock_3parclient.getRemoteCopyGroup.side_effect = \
            [exceptions.HTTPNotFound(exc_msg)]

        # Called during RCG creation flow to fetch domain from CPG
        mock_3parclient.getCPG.return_value = {}

        mock_3parclient.createRemoteCopyGroup.side_effect = \
            [exceptions.HTTPBadRequest('Create RCG failed: TEST-RCG')]

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": self._expected_resp})

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.createVolume.assert_called()

        mock_3parclient.createRemoteCopyGroup.assert_called()


class TestCreateReplicatedVolumeWithInvalidOptions(
        CreateReplicatedVolumeUnitTest):
    def check_response(self, resp):
        in_valid_opts = ['expHrs', 'retHrs']
        in_valid_opts.sort()
        op = "create replicated volume"
        expected = "Invalid input received: Invalid option(s) " \
                   "%s specified for operation %s. " \
                   "Please check help for usage." % (in_valid_opts, op)
        self._test_case.assertEqual(expected, resp['Err'])

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {"replicationGroup": "Dummy-RCG",
                         "expHrs": 111,
                         "retHrs": 123}}

# TODO:
# class TestCreateVolumeWithMutuallyExclusiveList(
#       CreateReplicatedVolumeUnitTest):
#     def check_response(self, resp):
#         self._test_case.assertEqual(
#             {"Err": "['virtualCopyOf', 'cloneOf', 'qos-name',"
#                     " 'replicationGroup'] cannot be specified at the"
#                     " same time"}, resp)
#
#     def get_request_params(self):
#         return {"Name": "test-vol-001",
#                 "Opts": {"qos-name": "soni_vvset",
#                          "provisioning": "thin",
#                          "size": "2",
#                          "cloneOf": "clone_of"}}
#
#     def setup_mock_objects(self):
#         mock_etcd = self.mock_objects['mock_etcd']
#         mock_etcd.get_vol_byname.return_value = None
#
#         mock_3parclient = self.mock_objects['mock_3parclient']
#         mock_3parclient.getCPG.return_value = {}
