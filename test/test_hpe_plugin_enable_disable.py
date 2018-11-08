import logging
import testtools

import test.enableplugin_tester as enableplugin_tester

logger = logging.getLogger('hpedockerplugin')
logger.level = logging.DEBUG
fh = logging.FileHandler('./unit_tests_run.log')
fh.setLevel(logging.DEBUG)
fmt = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
fh.setFormatter(fmt)
logger.addHandler(fh)


def tc_banner_decorator(func):
    def banner_wrapper(self, *args, **kwargs):
        # logger = logging.getLogger(__name__)
        logger.info('Starting - %s' % func.__name__)
        logger.info('========================================================'
                    '===========')
        func(self, *args, **kwargs)
        logger.info('Finished - %s' % func.__name__)
        logger.info('========================================================'
                    '===========\n\n')
    return banner_wrapper


class HpeDockerEnableDisableUnitTests(object):
    @tc_banner_decorator
    def test_enable(self):
        test = enableplugin_tester.TestEnablePlugin()
        test.run_test(self)

    @tc_banner_decorator
    def test_plugin_init_fails(self):
        test = enableplugin_tester.TestPluginInitializationFails()
        test.run_test(self)


class HpeDockerMixedIscsiDefaultUnitTest(HpeDockerEnableDisableUnitTests,
                                         testtools.TestCase):
    @property
    def protocol(self):
        return 'mixed_iscsi_default'


class HpeDockerMixedFcDefaultUnitTest(HpeDockerEnableDisableUnitTests,
                                      testtools.TestCase):
    @property
    def protocol(self):
        return 'mixed_fc_default'
