import pytest
import docker
import yaml
import os
import time
from .base import TEST_API_VERSION, BUSYBOX
from . import helpers
from .helpers import requires_api_version
from .hpe_3par_manager import HPE3ParBackendVerification,HPE3ParVolumePluginTest

# Importing test data from YAML config file
with open("testdata/test_config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# Declaring Global variables and assigning the values from YAML config file

PLUGIN_TYPE = cfg['plugin']['type']
HOST_OS = cfg['platform']['os']
THIN_SIZE = cfg['volumes']['thin_size']
FULL_SIZE = cfg['volumes']['full_size']
DEDUP_SIZE = cfg['volumes']['dedup_size']
COMPRESS_SIZE = cfg['volumes']['compress_size']

if PLUGIN_TYPE == 'managed':
    HPE3PAR = cfg['plugin']['managed_plugin_latest']
    CERTS_SOURCE = cfg['plugin']['certs_source']
else:
    HPE3PAR = cfg['plugin']['containerized_plugin']
    PLUGIN_IMAGE = cfg['plugin']['containerized_image']
    if HOST_OS == 'ubuntu':
        PLUGIN_VOLUMES = cfg['ubuntu_volumes']
    elif HOST_OS == 'suse':
        PLUGIN_VOLUMES = cfg['suse_volumes']
    else:
        PLUGIN_VOLUMES = cfg['rhel_volumes']

@requires_api_version('1.21')
class RemoteCopyTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

    @classmethod
    def setUpClass(cls):
        if PLUGIN_TYPE == 'managed':
            c = docker.APIClient(
                version=TEST_API_VERSION, timeout=600,
                **docker.utils.kwargs_from_env()
                )
            try:
                prv = c.plugin_privileges(HPE3PAR)
                logs = [d for d in c.pull_plugin(HPE3PAR, prv)]
                assert filter(lambda x: x['status'] == 'Download complete', logs)
                if HOST_OS == 'ubuntu':
                    c.configure_plugin(HPE3PAR, {
                        'certs.source': CERTS_SOURCE
                    })
                else:
                    c.configure_plugin(HPE3PAR, {
                        'certs.source': CERTS_SOURCE,
                        'glibc_libs.source': '/lib64'
                    })
                pl_data = c.inspect_plugin(HPE3PAR)
                assert pl_data['Enabled'] is False
                while pl_data['Enabled'] is False:
                    c.enable_plugin(HPE3PAR)
                    HPE3ParBackendVerification.hpe_wait_for_all_backends_to_initialize(cls, driver=HPE3PAR, help='backends')
                pl_data = c.inspect_plugin(HPE3PAR)
                assert pl_data['Enabled'] is True
            except docker.errors.APIError:
                pass
        else:
            c = docker.from_env(version=TEST_API_VERSION, timeout=600)
            try:
                mount = docker.types.Mount(type='bind', source='/opt/hpe/data',
                                           target='/opt/hpe/data', propagation='rshared'
                )
                c.containers.run(PLUGIN_IMAGE, detach=True,
                                 name='hpe_legacy_plugin', privileged=True, network_mode='host',
                                 restart_policy={'Name': 'on-failure', 'MaximumRetryCount': 5},
                                 volumes=PLUGIN_VOLUMES, mounts=[mount],
                                 labels={'type': 'plugin'}
                )
                HPE3ParBackendVerification.hpe_wait_for_all_backends_to_initialize(cls, driver=HPE3PAR, help='backends')
            except docker.errors.APIError:
                pass


    @classmethod
    def tearDownClass(cls):
        if PLUGIN_TYPE == 'managed':
            c = docker.APIClient(
                version=TEST_API_VERSION, timeout=600,
                **docker.utils.kwargs_from_env()
            )
            try:
                c.disable_plugin(HPE3PAR)
            except docker.errors.APIError:
                pass

            try:
                c.remove_plugin(HPE3PAR, force=True)
            except docker.errors.APIError:
                pass
        else:
            c = docker.from_env(version=TEST_API_VERSION, timeout=600)
            try:
                container_list = c.containers.list(all=True, filters={'label': 'type=plugin'})
                container_list[0].stop()
                container_list[0].remove()
                os.remove("/run/docker/plugins/hpe.sock")
                os.remove("/run/docker/plugins/hpe.sock.lock")
            except docker.errors.APIError:
                pass


    def test_active_passive_replication(self):
        '''
           This test creates an active-passive replication group and tests the failover, recover and restore functionality.

           Steps:
           1. Create a replicated volume.
           2. Inspect the created replicated volume and verify volume and RCG details.
           3. Create a container, mount the volume, and write data to the container.
           4. Failover and recover the replication group
           5. Start container and append contents to file and inspect
           6. Restart RCG group.
           7. Start container and append data.
        '''
        client = docker.from_env(version=TEST_API_VERSION) 
        volume_name = helpers.random_name()
        container_name= helpers.random_name()
        self.tmp_volumes.append(volume_name)

        # Create volume with -o replicationGroup option.
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, replicationGroup='testRCG1', backend='ActivePassiveRepBackend')
        
        #Inspect replication group and volume details
        self.hpe_inspect_volume(volume, replicationGroup='testRCG1')


        #Create contianer, mount volume and write data to file 
        container = client.containers.run(BUSYBOX, "sh", detach=True,
                                          name=helpers.random_name(), tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/data']
        ) 

        self.tmp_containers.append(container.id)
        container.exec_run("sh -c 'echo \"hello\" > /data/test'")
        ExecResult = container.exec_run("cat /data/test")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"hello\n")
        container.stop()

        
        #Failover replication group.
        targetrcgName = self.hpe_recover_remote_copy_group('testRCG1', 7)

        container.start()


        #Create contianer, mount volume and write data to file
        container.exec_run("sh -c 'echo \"beautiful\" >> /data/test'")
        ExecResult = container.exec_run("cat /data/test")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"hello\nbeautiful\n")
        container.stop()


        #Restore replication group.
        self.hpe_restore_remote_copy_group(targetrcgName, 10)
        container.start()
        container.exec_run("sh -c 'echo \"world\" >> /data/test'")
        ExecResult = container.exec_run("cat /data/test")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"hello\nbeautiful\nworld\n")
        container.stop()

        #Cleanup
        container.remove() 
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name) 
