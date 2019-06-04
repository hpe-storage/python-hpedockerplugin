import pytest
import time
import docker
import yaml
import os
from .base import TEST_API_VERSION, BUSYBOX
from .helpers import requires_api_version, random_name
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
class FilePersonaTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

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

    #Create file share with -o fpg option

    def test_file_persona_with_fpg(self):
        '''
           This test creates a file share with -o fpg option.

           Steps:
           1. Create a file share with -o file persona and -o fpg option.
           2. Inspect the creation of the file share, without mount details.
           3. Create a container, mount the share.
           4. Inspect container mount values.
           5. Unmount container
           6. remove container
           7. Delete file share
           8. Validate file share delete. 
        '''
        client = docker.from_env(version=TEST_API_VERSION) 
        volume_name = random_name()
        container_name= random_name()
        self.tmp_volumes.append(volume_name)

        # Create file share with -o fpg option.
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, filePersona="", fpg="Test_Fpg_2")
        fileshareinfo = self.hpe_inspect_share(volume)
        fileshare_id = fileshareinfo[1]['id']
        self.hpe_verify_share_created(volume_name, fileshare_id)

        container = client.containers.run(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, volumes=[volume_name + ':/data1']
                              )

        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        fileshareinfo = self.hpe_inspect_share(volume, mount='yes')
        container_id = container.id 
        self.hpe_unmount_volume(container_id)
        container.remove()
        time.sleep(10)
        self.hpe_delete_volume(volume)
        time.sleep(120)
        self.hpe_verify_share_deleted(volume_name)


    def test_file_persona(self):
        '''
         
           This test creates a file share with default option.

           Steps:
           1. Create a file share with -o file persona option.
           2. Inspect the creation of the file share, without mount details.
           3. Create a container, mount the share.
           4. Inspect container mount values.
           5. Unmount container
           6. remove container
           7. Delete file share
           8. Validate file share delete.
        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = random_name()
        container_name= random_name()
        self.tmp_volumes.append(volume_name)

        # Create file share. Test will create file share on default fpg and vfs.
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, filePersona="")
        fileshareinfo = self.hpe_inspect_share(volume)
        fileshare_id = fileshareinfo[1]['id']
        self.hpe_verify_share_created(volume_name, fileshare_id)
        
        container = client.containers.run(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, volumes=[volume_name + ':/data1']
                              )

        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        fileshareinfo = self.hpe_inspect_share(volume, mount='yes')
        container_id = container.id
        self.hpe_unmount_volume(container_id)
        container.remove()
        time.sleep(10)
        self.hpe_delete_volume(volume)
        time.sleep(120)
        self.hpe_verify_share_deleted(volume_name) 
        


    def test_file_persona_with_fpg_cpg(self):
        '''
         
           This test creates a file share with -o cpg option.

           Steps:
           1. Create a file share with -o file persona, -o fpg and -o cpg option.
           2. Inspect the creation of the file share, without mount details.
           3. Create a container, mount the share.
           4. Inspect container mount values.
           5. Unmount container
           6. remove container
           7. Delete file share
           8. Validate file share delete.
        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = random_name()
        container_name= random_name()
        self.tmp_volumes.append(volume_name)

        # Create file share with -o fpg -o cpg option.
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, filePersona="", fpg="Test_Fpg_2", cpg='FC_r6')
        fileshareinfo = self.hpe_inspect_share(volume)
        fileshare_id = fileshareinfo[1]['id']
        self.hpe_verify_share_created(volume_name, fileshare_id)
        container = client.containers.run(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, volumes=[volume_name + ':/data1']
                              )

        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        fileshareinfo = self.hpe_inspect_share(volume, mount='yes')
        
        container_id = container.id  
        self.hpe_unmount_volume(container_id)
        container.remove()
        time.sleep(10)
        self.hpe_delete_volume(volume)
        time.sleep(120)
        self.hpe_verify_share_deleted(volume_name)




    def test_file_persona_with_fpg_size(self):
        '''
         
           This test creates a file share with -o size option.

           Steps:
           1. Create a file share with -o file persona, -o size and -o fpg option.
           2. Inspect the creation of the file share, without mount details.
           3. Create a container, mount the share.
           4. Inspect container mount values.
           5. Unmount container
           6. remove container
           7. Delete file share
           8. Validate file share delete. 
        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = random_name()
        container_name= random_name()
        self.tmp_volumes.append(volume_name)

        # Create file share with -o fpg and -ip option.
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, filePersona="", fpg="Test_Fpg_2", size="1")
        fileshareinfo = self.hpe_inspect_share(volume)
        fileshare_id = fileshareinfo[1]['id']
        self.hpe_verify_share_created(volume_name, fileshare_id)
        container = client.containers.run(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, volumes=[volume_name + ':/data1']
                              )

        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        fileshareinfo = self.hpe_inspect_share(volume, mount='yes') 
        container_id = container.id
        self.hpe_unmount_volume(container_id)
        container.remove()
        time.sleep(10)
        self.hpe_delete_volume(volume)
        time.sleep(120)
        self.hpe_verify_share_deleted(volume_name)


    def test_file_persona_with_fpg_backend(self):
        '''
           This test creates a file share with -o backend option.

           Steps:
           1. Create a file share with -o file persona, -o backend and -o fpg option.
           2. Inspect the creation of the file share, without mount details.
           3. Create a container, mount the share.
           4. Inspect container mount values.
           5. Unmount container
           6. remove container
           7. Delete file share
           8. Validate file share delete. 
        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = random_name()
        container_name= random_name()
        self.tmp_volumes.append(volume_name)

        # Create file share with -o fpg and -backend option.
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, filePersona="", fpg="Test_Fpg_2", backend='3par_file')
        fileshareinfo = self.hpe_inspect_share(volume)
        fileshare_id = fileshareinfo[1]['id']
        self.hpe_verify_share_created(volume_name, fileshare_id)
        container = client.containers.run(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, volumes=[volume_name + ':/data1']
                              )

        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        fileshareinfo = self.hpe_inspect_share(volume, mount='yes')
        container_id = container.id
        self.hpe_unmount_volume(container_id)
        container.remove()
        time.sleep(10)
        self.hpe_delete_volume(volume)
        time.sleep(120)
        self.hpe_verify_share_deleted(volume_name)

