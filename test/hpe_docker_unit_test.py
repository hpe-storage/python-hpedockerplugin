import abc
import json
import six
import time

from io import StringIO
from twisted.internet import reactor


from config import setupcfg
from hpedockerplugin import exception
from hpedockerplugin import hpe_storage_api as api
import test.setup_mock as setup_mock


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

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._all_configs = None

    @staticmethod
    def _get_request_body(request_dict):
        req_body_str = json.dumps(request_dict)
        return RequestBody(req_body_str)

    def _real_execute_api(self, plugin_api):
        """
        This is the method where all the action related to execution of
        VolumePlugin API happen. This also has hooks for child class to
        carry out the pre-requisites for the execution of VolumePlugin API
        :param operation:
            String containing VolumePlugin API name
        :return: Nothing
        """
        # import pdb
        # pdb.set_trace()

        # Get API parameters from child class
        req_body = self._get_request_body(self.get_request_params())

        _api = api.VolumePlugin(reactor, self._all_configs)
        try:
            resp = getattr(_api, plugin_api)(req_body)
            resp = json.loads(resp)
        except Exception as ex:
            # self.handle_exception(ex)
            # Plugin will never throw exception. This exception is coming
            # from check_response as some 3PAR API was not invoked
            # Let it go to testtools framework so that it can report the
            # test case as failed
            raise ex

    @setup_mock.mock_decorator
    def _mock_execute_api(self, mock_objects, plugin_api=''):
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
        # import pdb
        # pdb.set_trace()
        self.mock_objects = mock_objects

        # Let the child class configure mock objects
        self.setup_mock_objects()

        # Get API parameters from child class
        req_body = self._get_request_body(self.get_request_params())

        _api = api.VolumePlugin(reactor, self._all_configs)

        if _api.orchestrator:
            _api.orchestrator._execute_request = \
                _api.orchestrator.__undeferred_execute_request__

        if _api._file_orchestrator:
            _api._file_orchestrator._execute_request = \
                _api._file_orchestrator.__undeferred_execute_request__

        req_params = self.get_request_params()

        # Workaround to allow all the async-initializing threads to
        # complete the initialization. We cannot use thread.join()
        # in the plugin code as that would defeat the purpose of async
        # initialization by making the main thread wait for all the
        # child threads to complete initialization
        time.sleep(3)

        # There are few TCs like enable/disable plugin for which
        # there isn't going to be any request parameters
        # Such TCs need to skip the below block and continue
        if req_params:
            backend = req_params.get('backend', 'DEFAULT')

            while True:
                backend_state = _api.is_backend_initialized(backend)
                print(" ||| Backend %s, backend_state %s " % (backend,
                                                              backend_state))
                if backend_state == 'OK' or backend_state == 'FAILED':
                    break
                time.sleep(1)

        try:
            # Plugin initialization UTs will return empty plugin_api string
            if plugin_api:
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
        self._all_configs = self._get_configuration()

        if not self.use_real_flow():
            self._mock_execute_api(plugin_api=self._get_plugin_api())
        else:
            self._real_execute_api(plugin_api=self._get_plugin_api())

    # Individual TCs can override this value to execute real flow
    def use_real_flow(self):
        return False

    def _get_configuration(self):
        if self.use_real_flow():
            cfg_file_name = '/etc/hpedockerplugin/hpe.conf'
        else:
            cfg_file_name = './test/config/hpe_%s.conf' % \
                            self._protocol.lower()
        cfg_param = ['--config-file', cfg_file_name]
        try:
            host_config = setupcfg.get_host_config(cfg_param)
            backend_configs = setupcfg.get_all_backend_configs(cfg_param)
        except Exception as ex:
            msg = 'Setting up of hpe3pardocker unit test failed, error is: ' \
                  '%s' % six.text_type(ex)
            # LOG.error(msg)
            raise exception.HPEPluginStartPluginException(reason=msg)

        all_configs = self._rearrange_configs(host_config, backend_configs)

        # _protocol is set in the immediate child class
        # config = create_configuration(self._protocol)
        # Allow child classes to override configuration
        self.override_configuration(all_configs)
        return all_configs

    def _rearrange_configs(self, host_config, backend_configs):
        file_driver = 'hpedockerplugin.hpe.hpe_3par_file.HPE3PARFileDriver'
        fc_driver = 'hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver'
        iscsi_driver = 'hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver'
        # backend_configs -> {'backend1': config1, 'backend2': config2, ...}
        # all_configs -> {'block': backend_configs1, 'file': backend_configs2}
        file_configs = {}
        block_configs = {}
        all_configs = {}
        for backend_name, config in backend_configs.items():
            configured_driver = config.hpedockerplugin_driver.strip()
            if configured_driver == file_driver:
                file_configs[backend_name] = config
            elif configured_driver == fc_driver or \
                    configured_driver == iscsi_driver:
                block_configs[backend_name] = config
            else:
                msg = "Bad driver name specified in hpe.conf: %s" %\
                      configured_driver
                raise exception.HPEPluginStartPluginException(reason=msg)

        if file_configs:
            all_configs['file'] = (host_config, file_configs)
        if block_configs:
            all_configs['block'] = (host_config, block_configs)

        return all_configs

    """
    Allows the child class to override the HPE configuration parameters
    needed to invoke VolumePlugin APIs
    """

    def override_configuration(self, all_configs):
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
