import fake_3par_data as data
import json
import mock
import setup_mock
from cStringIO import StringIO
from hpedockerplugin import hpe_storage_api as api
from twisted.internet import reactor


class RequestBody:
    def __init__(self, req_body_str):
        self.content = StringIO(req_body_str)


class HpeDockerUnitTestExecutor(object):
    @staticmethod
    def _get_request_body(request_dict):
        req_body_str = json.dumps(request_dict)
        return RequestBody(req_body_str)

    @setup_mock.mock_decorator
    def _execute_operation(self, mock_objects, operation=None):
        self.mock_objects = mock_objects
        self.setup_mock_objects()
        req_body = self._get_request_body(self.get_request_params())

        _api = api.VolumePlugin(reactor, self._config)
        try:
            resp = getattr(_api, operation)(req_body)
            resp = json.loads(resp)
            self.check_response(resp)
        except Exception as ex:
            self.handle_exception(ex)

    def _test_operation(self, operation):
        # We MUST create configuration before creating
        # mock objects. As mock decorator needs configuration
        # to decide whether to mock ISCSI or FC connector
        self._config = self.get_configuration()
        self._execute_operation(operation=operation)

    def get_configuration(self):
        config = create_configuration(self._protocol)
        # Allow child classes to override configuration
        self.override_configuration(config)
        return config

    def handle_exception(self, ex):
        pass


def create_configuration(protocol):
    config = mock.Mock()
    config.ssh_hosts_key_file = "/root/.ssh/known_hosts"
    config.host_etcd_ip_address = "10.50.3.140"
    config.host_etcd_port_number = "2379"
    config.logging = "DEBUG"
    config.hpe3par_debug = False
    config.suppress_requests_ssl_warnings = False

    if protocol == 'ISCSI':
        config.hpedockerplugin_driver = \
            "hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver"
    else:
        config.hpedockerplugin_driver = \
            "hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver"

    config.hpe3par_api_url = "https://10.50.3.7:8080/api/v1"
    config.hpe3par_username = "3paradm"
    config.hpe3par_password = "3pardata"
    config.san_ip = "10.50.3.7"
    config.san_login = "3paradm"
    config.san_password = "3pardata"
    config.hpe3par_cpg = [data.HPE3PAR_CPG, data.HPE3PAR_CPG2]
    config.hpe3par_snapcpg = [data.HPE3PAR_CPG]
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
