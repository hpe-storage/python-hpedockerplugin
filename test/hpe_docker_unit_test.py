import json
import mock

from hpedockerplugin import hpe_storage_api as api
from cStringIO import StringIO
from twisted.internet import reactor


class RequestBody:
    def __init__(self, req_body_str):
        self.content = StringIO(req_body_str)


class HpeDockerUnitTest(object):
    @staticmethod
    def _get_request_body(request_dict):
        req_body_str = json.dumps(request_dict)
        return RequestBody(req_body_str)

    def _test_operation(self, operation):
        # Configure all mock objects
        self.setup_mock_objects()
        req_body = self._get_request_body(self.get_request_params())

        config = self.get_configuration()
        _api = api.VolumePlugin(reactor, config)
        try:
            resp = getattr(_api, operation)(req_body)
            resp = json.loads(resp)
            self.check_response(resp)
        except Exception as ex:
            self.handle_exception(ex)

    def get_configuration(self):
        config = create_configuration()
        # Allow child classes to override configuration
        self.override_configuration(config)
        return config

    def handle_exception(self, ex):
        pass


HPE3PAR_CPG = 'DockerCPG'
HPE3PAR_CPG2 = 'fakepool'


def create_configuration():
    config = mock.Mock()
    config.ssh_hosts_key_file = "/root/.ssh/known_hosts"
    config.host_etcd_ip_address = "10.50.3.140"
    config.host_etcd_port_number = "2379"
    config.logging = "DEBUG"
    config.hpe3par_debug = False
    config.suppress_requests_ssl_warnings = False
    # self._config.hpedockerplugin_driver = self.get_driver_class_name()
    config.hpedockerplugin_driver = "hpedockerplugin.hpe.hpe_3par_iscsi. \
        HPE3PARISCSIDriver"
    config.hpe3par_api_url = "https://10.50.3.7:8080/api/v1"
    config.hpe3par_username = "3paradm"
    config.hpe3par_password = "3pardata"
    config.san_ip = "10.50.3.7"
    config.san_login = "3paradm"
    config.san_password = "3pardata"
    config.hpe3par_cpg = [HPE3PAR_CPG, HPE3PAR_CPG2]
    # config.hpe3par_iscsi_ips = ["10.50.17.220", "10.50.17.221",
    #                             "10.50.17.222", "10.50.17.223"]
    config.hpe3par_iscsi_ips = []
    config.iscsi_ip_address = '1.1.1.2'
    config.hpe3par_iscsi_chap_enabled = False
    config.use_multipath = False
    config.enforce_multipath = False
    config.host_etcd_client_cert = None
    config.host_etcd_client_key = None
    return config


class RemoveVolumeUnitTest(HpeDockerUnitTest):
    def _test_remove_volume(self, op_data):
        def setup_mock_objects():
            op_data['setup_mock_etcd']()

        op_data['setup_mock_objects'] = setup_mock_objects
        op_data['operation'] = 'volumedriver_remove'
        self._test_operation(op_data)


class UnmountVolumeUnitTest(HpeDockerUnitTest):
    def _test_unmount_volume(self, op_data):
        # Set up mock configuration of all mock objects
        # required to run mount volume unit test
        def setup_mock_objects():
            # Call child class functions to configure mock objects
            op_data['setup_mock_3parclient']()
            op_data['setup_mock_etcd']()
            op_data['setup_mock_fileutil']()
            op_data['setup_mock_osbrick']()

        op_data['setup_mock_objects'] = setup_mock_objects
        op_data['operation'] = 'volumedriver_unmount'
        self._test_operation(op_data)
