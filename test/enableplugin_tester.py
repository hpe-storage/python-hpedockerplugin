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
