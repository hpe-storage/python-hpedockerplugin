from hpe3parclient import exceptions
import test.hpe_docker_unit_test as hpeunittest
from oslo_config import cfg
CONF = cfg.CONF


class EnablePluginUnitTest(hpeunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'plugin_activate'

    def check_response(self, resp):
        expected_resp = {u"Implements": [u"VolumeDriver"]}
        self._test_case.assertEqual(resp, expected_resp)


class TestEnablePlugin(EnablePluginUnitTest):
    pass


class InitializePluginUnitTest(hpeunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return ""


class TestPluginInitializationFails(InitializePluginUnitTest):
    def setup_mock_objects(self):
        mock_3parclient = self.mock_objects['mock_3parclient']

        # Add as many side_effect as the number of backends
        side_effect = []
        for backend in self._all_configs:
            side_effect.append(exceptions.UnsupportedVersion)
        mock_3parclient.getWsApiVersion.side_effect = side_effect

    def check_response(self, resp):
        self._test_case.assertEqual(resp, {u"Err": 'GOT RESPONSE'})
