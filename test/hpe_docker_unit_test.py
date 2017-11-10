import abc
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
    """
    Base class to facilitate execution of VolumePlugin APIs
    Does the following:
    1. Gets mock objects using mock_decorator
    2. Allows the child class to set the desired configuration needed by the
       plugin
    3. Allows the child class to configure mock objects, their return values
    4. Finally allows the child class to validate if the operation executed
       as desired
    """

    @staticmethod
    def _get_request_body(request_dict):
        req_body_str = json.dumps(request_dict)
        return RequestBody(req_body_str)

    @setup_mock.mock_decorator
    def _execute_api(self, mock_objects, plugin_api=''):
        """
        This is the method where all the action related to execution of
        VolumePlugin API happen. This also has hooks for child class to
        carry out the pre-requisites for the execution of VolumePlugin API
        :param mock_objects:
            Dictionary of four mock objects returned by
            mock_decorator. Following are the keys and their descriptions
            to access specific mock object
            {'mock_3parclient': 3PAR Client mock object,
            'mock_fileutil': File utilities mock object,
            'mock_osbrick_connector': Protocol specific mock connector,
            'mock_etcd': Etcd mock object}
        :param operation:
            String containing VolumePlugin API name
        :return: Nothing
        """
        self.mock_objects = mock_objects
        self._config = self._get_configuration()

        # Let the child class configure mock objects
        self.setup_mock_objects()

        # Get API parameters from child class
        req_body = self._get_request_body(self.get_request_params())

        _api = api.VolumePlugin(reactor, self._config)
        try:
            resp = getattr(_api, plugin_api)(req_body)
            resp = json.loads(resp)

            # Allow child class to validate response
            self.check_response(resp)
        except Exception as ex:
            # self.handle_exception(ex)
            # Plugin will never throw exception. This exception is coming
            # from check_response as some 3PAR API was not invoked
            # Let it go to testtools framework so that it can report the
            # test case as failed
            raise ex

    def run_test(self, test_case):
        self._test_case = test_case
        # This is important to set as it is used by the mock decorator to
        # take decision which driver to instantiate
        self._protocol = test_case.protocol
        self._execute_api(plugin_api=self._get_plugin_api())

    def _get_configuration(self):
        # _protocol is set in the immediate child class
        config = create_configuration(self._protocol)
        # Allow child classes to override configuration
        self.override_configuration(config)
        return config

    """
    Allows the child class to override the HPE configuration parameters
    needed to invoke VolumePlugin APIs
    """

    def override_configuration(self, config):
        pass

    """
    May need to override this in some rare case where exception is
    thrown from the VolumePlugin
    """

    def handle_exception(self, ex):
        pass

    @abc.abstractmethod
    def _get_plugin_api(self):
        pass

    """
    Allows the child class configure mock objects so that they can return
    the desired values when used in the actual VolumePlugin API flow
    """

    @abc.abstractmethod
    def setup_mock_objects(self):
        pass

    """
    Child class to return dictionary containing input paramteres required to
    execute a particular API in VolumePlugin
    """

    @abc.abstractmethod
    def get_request_params(self):
        pass

    """
    This method is invoked after completing the execution of VolumePlugin API
    Allows the child class to validate if appropriate response was returned
    from the plugin and that the desired methods were invoked on the 3PAR
    Client, ETCD and/or other mock objects
    """

    @abc.abstractmethod
    def check_response(self, resp):
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
    config.hpe3par_iscsi_ips = []
    config.iscsi_ip_address = '1.1.1.2'
    config.hpe3par_iscsi_chap_enabled = False
    config.use_multipath = True
    config.enforce_multipath = True
    config.host_etcd_client_cert = None
    config.host_etcd_client_key = None
    return config
