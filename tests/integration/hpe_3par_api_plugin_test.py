import docker
import pytest
import yaml

from .base import BaseAPIIntegrationTest, TEST_API_VERSION, BUSYBOX
from .. import helpers
from ..helpers import requires_api_version
from hpe_3par_manager import HPE3ParBackendVerification,HPE3ParVolumePluginTest
import pdb

# Importing test data from YAML config file
with open("testdata/test_config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# Declaring Global variables and assigning the values from YAML config file
HPE3PAR = cfg['plugin']['latest_version']
HPE3PAR_OLD = cfg['plugin']['old_version']
HOST_OS = cfg['platform']['os']
CERTS_SOURCE = cfg['plugin']['certs_source']
THIN_SIZE = cfg['volumes']['thin_size']
client = docker.APIClient(
            version=TEST_API_VERSION, timeout=600,
            **docker.utils.kwargs_from_env()
)


@requires_api_version('1.25')
class PluginTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

    @classmethod
    def teardown_class(cls):
        try:
            client.remove_plugin(HPE3PAR, force=True)
            if HPE3PAR_OLD:
                client.remove_plugin(HPE3PAR_OLD, force=True)
        except docker.errors.APIError:
            pass

    def teardown_method(self, method):
        try:
            client.disable_plugin(HPE3PAR)
            if HPE3PAR_OLD:
                client.disable_plugin(HPE3PAR_OLD)
        except docker.errors.APIError:
            pass

        for p in self.tmp_plugins:
            try:
                client.remove_plugin(p, force=True)
            except docker.errors.APIError:
                pass

    def ensure_plugin_installed(self, plugin_name):
        # This test will ensure if the plugin is installed
        try:
            return client.inspect_plugin(plugin_name)
        except docker.errors.NotFound:
            prv = client.plugin_privileges(plugin_name)
            for d in client.pull_plugin(plugin_name, prv):
                pass
        return client.inspect_plugin(plugin_name)

    def test_enable_plugin(self):
        # This test will configure and enable the plugin
        pl_data = self.ensure_plugin_installed(HPE3PAR)
        self.tmp_plugins.append(HPE3PAR)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE
                })
        else:
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE,
                'glibc_libs.source': '/lib64'
                })
        assert pl_data['Enabled'] is False
        assert client.enable_plugin(HPE3PAR)
        pl_data = client.inspect_plugin(HPE3PAR)
        assert pl_data['Enabled'] is True
        with pytest.raises(docker.errors.APIError):
            client.enable_plugin(HPE3PAR)

    def test_disable_plugin(self):
        # This test will enable and disable the plugin
        pl_data = self.ensure_plugin_installed(HPE3PAR)
        self.tmp_plugins.append(HPE3PAR)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE
                })
        else:
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE,
                'glibc_libs.source': '/lib64'
                })
        assert pl_data['Enabled'] is False
        assert client.enable_plugin(HPE3PAR)
        pl_data = client.inspect_plugin(HPE3PAR)
        assert pl_data['Enabled'] is True
        client.disable_plugin(HPE3PAR)
        pl_data = client.inspect_plugin(HPE3PAR)
        assert pl_data['Enabled'] is False
        with pytest.raises(docker.errors.APIError):
            client.disable_plugin(HPE3PAR)

    def test_inspect_plugin(self):
        # This test will inspect the plugin
        self.ensure_plugin_installed(HPE3PAR)
        self.tmp_plugins.append(HPE3PAR)
        data = client.inspect_plugin(HPE3PAR)
        assert 'Config' in data
        assert 'Name' in data
        assert data['Name'] == HPE3PAR

    def test_list_plugins(self):
        # This test will list all installed plugin
        self.ensure_plugin_installed(HPE3PAR)
        self.tmp_plugins.append(HPE3PAR)
        data = client.plugins()
        assert len(data) > 0
        plugin = [p for p in data if p['Name'] == HPE3PAR][0]
        assert 'Config' in plugin

    def test_remove_plugin(self):
        # This test will remove the plugin
        pl_data = self.ensure_plugin_installed(HPE3PAR)
        self.tmp_plugins.append(HPE3PAR)
        assert pl_data['Enabled'] is False
        assert client.remove_plugin(HPE3PAR) is True

    def test_force_remove_plugin(self):
        # This test will remove the plugin forcefully
        self.ensure_plugin_installed(HPE3PAR)
        self.tmp_plugins.append(HPE3PAR)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE
                })
        else:
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE,
                'glibc_libs.source': '/lib64'
                })
        client.enable_plugin(HPE3PAR)
        assert client.inspect_plugin(HPE3PAR)['Enabled'] is True
        assert client.remove_plugin(HPE3PAR, force=True) is True

    def test_install_plugin(self):
        # This test will remove plugin first if installed, and then install and enable the plugin
        prv = client.plugin_privileges(HPE3PAR)
        self.tmp_plugins.append(HPE3PAR)
        logs = [d for d in client.pull_plugin(HPE3PAR, prv)]
        assert filter(lambda x: x['status'] == 'Download complete', logs)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE
                })
        else:
            client.configure_plugin(HPE3PAR, {
                'certs.source': CERTS_SOURCE,
                'glibc_libs.source': '/lib64'
                })
        assert client.inspect_plugin(HPE3PAR)
        assert client.enable_plugin(HPE3PAR)

    @requires_api_version('1.26')
    def test_upgrade_plugin_without_volume_operations(self):
        # This test will upgrade the plugin with same repository name
        pl_data = self.ensure_plugin_installed(HPE3PAR_OLD)
        self.tmp_plugins.append(HPE3PAR_OLD)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR_OLD, {
                'certs.source': CERTS_SOURCE
                })
        else:
            client.configure_plugin(HPE3PAR_OLD, {
                'certs.source': CERTS_SOURCE,
                'glibc_libs.source': '/lib64'
                })
        assert pl_data['Enabled'] is False
        prv = client.plugin_privileges(HPE3PAR_OLD)
        logs = [d for d in client.upgrade_plugin(HPE3PAR_OLD, HPE3PAR, prv)]
        assert filter(lambda x: x['status'] == 'Download complete', logs)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR_OLD, {
                'certs.source': CERTS_SOURCE
                })
        else:
            client.configure_plugin(HPE3PAR_OLD, {
                'certs.source': CERTS_SOURCE,
                'glibc_libs.source': '/lib64'
                })
        assert client.inspect_plugin(HPE3PAR_OLD)
        assert client.enable_plugin(HPE3PAR_OLD)
        client.disable_plugin(HPE3PAR_OLD)
        client.remove_plugin(HPE3PAR_OLD, force=True)

    def test_upgrade_plugin_with_volume_operations(self):
        # This test will upgrade the plugin with same repository name
        client = docker.APIClient(
            version=TEST_API_VERSION, timeout=600,
            **docker.utils.kwargs_from_env()
        )
        pl_data = self.ensure_plugin_installed(HPE3PAR_OLD)
        self.tmp_plugins.append(HPE3PAR_OLD)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR_OLD, {
                    'certs.source': CERTS_SOURCE
            })
        else:
            client.configure_plugin(HPE3PAR_OLD, {
                    'certs.source': CERTS_SOURCE,
                    'glibc_libs.source': '/lib64'
            })
        assert pl_data['Enabled'] is False
        assert client.enable_plugin(HPE3PAR_OLD)
        pl_data = client.inspect_plugin(HPE3PAR_OLD)
        assert pl_data['Enabled'] is True

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR_OLD,
                                   size=THIN_SIZE, provisioning='thin')
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR_OLD,
                                                binds=volume_name + ':/data1')
        container_info = self.hpe_unmount_volume(BUSYBOX, command='sh', detach=True,
                                    name=helpers.random_name(), tty=True, stdin_open=True,
                                    host_config=host_conf
        )

        id = container_info['Id']
        self.client.remove_container(id)
        self.hpe_delete_volume(volume)


        client.disable_plugin(HPE3PAR_OLD)
        pl_data = client.inspect_plugin(HPE3PAR_OLD)
        assert pl_data['Enabled'] is False


        prv = client.plugin_privileges(HPE3PAR)
        logs = [d for d in client.upgrade_plugin(HPE3PAR_OLD, HPE3PAR, prv)]
        assert filter(lambda x: x['status'] == 'Download complete', logs)
        if HOST_OS == 'ubuntu':
            client.configure_plugin(HPE3PAR_OLD, {
                    'certs.source': CERTS_SOURCE
            })
        else:
            client.configure_plugin(HPE3PAR_OLD, {
                    'certs.source': CERTS_SOURCE,
                    'glibc_libs.source': '/lib64'
            })
        assert client.inspect_plugin(HPE3PAR_OLD)
        assert client.enable_plugin(HPE3PAR_OLD)

        cl = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR_OLD,
                               size=THIN_SIZE, provisioning='thin')
        container = cl.containers.run(BUSYBOX, "sh", detach=True, name=helpers.random_name(),
                                          volumes=[volume_name + ':/insidecontainer'],
                                          tty=True, stdin_open=True
        )
        self.tmp_containers.append(container.id)
        self.hpe_verify_volume_mount(volume_name)
        container.exec_run("sh -c 'echo \"hello\" > /insidecontainer/test'")
        assert container.exec_run("cat /insidecontainer/test") == b"hello\n"
        container.stop()
        container.wait()
        container.remove()
        self.hpe_verify_volume_unmount(volume_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)


