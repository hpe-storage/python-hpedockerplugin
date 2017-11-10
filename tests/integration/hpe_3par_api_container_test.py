import tempfile
import docker
import pytest
import yaml

import six

from .base import TEST_API_VERSION, BUSYBOX
from .. import helpers
from ..helpers import requires_api_version
from hpe_3par_manager import HPE3ParBackendVerification,HPE3ParVolumePluginTest

# Importing test data from YAML config file
#with open("tests/integration/testdata/test_config.yml", 'r') as ymlfile:
with open("testdata/test_config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# Declaring Global variables and assigning the values from YAML config file
HPE3PAR = cfg['plugin']['latest_version']
HOST_OS = cfg['platform']['os']
CERTS_SOURCE = cfg['plugin']['certs_source']
THIN_SIZE = cfg['volumes']['thin_size']
ETCD = cfg['etcd']['container']

@requires_api_version('1.20')
class VolumeBindTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

    @classmethod
    def setUpClass(cls):
        c = docker.APIClient(
            version=TEST_API_VERSION, timeout=600,
            **docker.utils.kwargs_from_env()
        )

        try:
            prv = c.plugin_privileges(HPE3PAR)
            for d in c.pull_plugin(HPE3PAR, prv):
                pass
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
            assert c.enable_plugin(HPE3PAR)
            pl_data = c.inspect_plugin(HPE3PAR)
            assert pl_data['Enabled'] is True
        except docker.errors.APIError:
            pass

    @classmethod
    def tearDownClass(cls):
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


    def test_volume_mount(self):
        '''
           This is a volume mount test.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Verify if VLUN is available in 3Par array.

        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/data1')
        self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=helpers.random_name(), host_config=host_conf
                              )
        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name)

    def test_volume_unmount(self):

        '''
        This is a volume unmount test.

        Steps:
        1. Create volume and verify if volume got created in docker host and 3PAR array
        2. Create a host config file to setup container.
        3. Create a container and perform mount and unmount operation.
        4. Verify if VLUN is removed from 3Par array.

        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/data1')
        self.hpe_unmount_volume(BUSYBOX, command='sh', detach=True,
                                name=helpers.random_name(), tty=True, stdin_open=True,
                                host_config=host_conf
                                )
        # Verifying in 3par
        self.hpe_verify_volume_unmount(volume_name)

    def test_write_and_read_data(self):
        '''
           This is a test of write data and verify that data from file archive of container.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Write the data in a file which gets created in 3Par volume.
           5. Get the archive of the above file and verify if data is available in that file.

        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        container = client.containers.run(BUSYBOX, "sh", detach=True,
                                          name=helpers.random_name(), tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/insidecontainer']
        )
        self.tmp_containers.append(container.id)
        container.exec_run("sh -c 'echo \"hello\" > /insidecontainer/test'")
        assert container.exec_run("cat /insidecontainer/test") == b"hello\n"
        container.stop()

    def test_write_data_get_file_archive_from_container(self):
        '''
           This is a test of write data and verify that data from file archive of container.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Write the data in a file which gets created in 3Par volume.
           5. Get the archive of the above file and verify if data is available in that file.

        '''
        text = 'Python Automation is the only way'
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/vol1')
        ctnr = self.hpe_create_container(BUSYBOX,
                                         command='sh -c "echo {0} > /vol1/file.txt"'.format(text),
                                         tty=True, detach=True, stdin_open=True,
                                         host_config=host_conf
                                         )
        self.client.start(ctnr)
        self.client.wait(ctnr)
        with tempfile.NamedTemporaryFile() as destination:
            strm, stat = self.client.get_archive(ctnr, '/vol1/file.txt')
            for d in strm:
                destination.write(d)
            destination.seek(0)
            retrieved_data = helpers.untar_file(destination, 'file.txt')
            if six.PY3:
                retrieved_data = retrieved_data.decode('utf-8')
            self.assertEqual(text, retrieved_data.strip())

    def test_volume_mount_readonly_fs(self):
        '''
           This is a volume mount test with read-only file system.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it with command to create a file in 3Par volume.
           4. Verify if container gets exited with 1 exit code just like 'docker wait' command.

        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/data1:ro')
        ctnr = self.hpe_create_container(BUSYBOX,
                                         command='sh -c "touch /data1/file.txt"',
                                         host_config=host_conf)
        self.client.start(ctnr)
        res = self.client.wait(ctnr)
        self.assertNotEqual(res, 0)

    def test_remove_unused_volumes(self):
        '''
           This is a tests for removal of dangling volumes.

           Steps:
           1. Create volumes with different volume properties.
           2. Mount one volume.
           3. Delete all unused volumes.
        '''
        volume_names = [helpers.random_name(),helpers.random_name(),helpers.random_name()]
        for name in volume_names:
            self.tmp_volumes.append(name)
        volume1 = self.hpe_create_volume(volume_names[0], driver=HPE3PAR)
        volume2 = self.hpe_create_volume(volume_names[1], driver=HPE3PAR,
                                         size=THIN_SIZE, provisioning='thin')
        volume3 = self.hpe_create_volume(volume_names[2], driver=HPE3PAR,
                                         size=THIN_SIZE, flash_cache='true')

        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_names[0] + ':/data1')
        self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=helpers.random_name(), host_config=host_conf
                              )

        result = self.client.volumes(filters={'dangling': True})
        volumes = result['Volumes']
        self.assertNotIn(volume1, volumes)
        volume = [volume2, volume3]
        for vol in volume:
            self.assertIn(vol, volumes)
        for dangling_vol in volumes:
            self.hpe_delete_volume(dangling_vol)
            self.hpe_verify_volume_deleted(dangling_vol['Name'])

    def test_volume_persists_container_is_removed(self):
        '''
           This is a persistent volume test.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Write the data in a file which gets created in 3Par volume.
           5. Stop the container
           6. Try to delete the volume - it should not get deleted
           7. Remove the container
           8. List volumes - Volume should be listed.
           9. Delete the volume - Volume should get deleted.

        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        container = client.containers.run(BUSYBOX,"sh", detach=True,
                                          name=helpers.random_name(), tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/insidecontainer']
        )
        self.tmp_containers.append(container.id)
        container.exec_run("sh -c 'echo \"hello\" > /insidecontainer/test'")
        container.stop()
        container.start()

        assert container.exec_run("cat /insidecontainer/test") == b"hello\n"

        try:
            self.client.remove_volume(volume_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 409)

        container.stop()
        container.remove()
        self.hpe_verify_volume_created(volume_name,size=THIN_SIZE,provisioning='thin')

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_shared_volume(self):
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        mounters = [helpers.random_name(), helpers.random_name(), helpers.random_name()]
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size='5', provisioning='thin')
        container1 = client.containers.run(BUSYBOX, "sh", detach=True, name=mounters[0],
                                           volumes=[volume_name + ':/data1'],
                                           tty=True, stdin_open=True
        )
        self.tmp_containers.append(container1.id)
        container1.exec_run("sh -c 'echo \"This volume will be shared between containers.\" > /data1/Example1.txt'")
        container1.stop()

        container2 = client.containers.run(BUSYBOX, "sh", detach=True, name=mounters[1],
                                           volumes_from=mounters[0],
                                           tty=True, stdin_open=True
        )
        self.tmp_containers.append(container2.id)
        self.hpe_verify_volume_mount(volume_name)
        container2.exec_run("sh -c 'echo \"Both containers will use this.\" >> /data1/Example1.txt'")
        out1 = container2.exec_run("cat /data1/Example1.txt")
        self.assertEqual(out1, b'This volume will be shared between containers.\nBoth containers will use this.\n')
        container2.stop()
        self.hpe_verify_volume_unmount(volume_name)

        container3 = client.containers.run(BUSYBOX, "sh", detach=True, name=mounters[2],
                                           volumes_from=mounters[0] + ':ro',
                                           tty=True, stdin_open=True
        )
        self.tmp_containers.append(container3.id)
        self.hpe_verify_volume_mount(volume_name)
        out2 = container3.exec_run("cat /data1/Example1.txt")
        self.assertEqual(out2, b'This volume will be shared between containers.\nBoth containers will use this.\n')
        out3 = container3.exec_run("touch /data1/Example2.txt")
        self.assertEqual(out3, b'touch: /data1/Example2.txt: Read-only file system\n')
        container3.stop()
        self.hpe_verify_volume_unmount(volume_name)
        container_list = client.containers.list(all=True)
        for ctnr in container_list:
            try:
                self.client.remove_container(ctnr.id)
            except docker.errors.APIError:
                continue

        removed_ctnr_list = client.containers.list(all=True)
        assert len(removed_ctnr_list) == 1
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_checksum_persistance_of_binary_file(self):
        '''
           This is a test of write data and verify that data from file archive of container.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Write the data in a file which gets created in 3Par volume.
           5. Get the archive of the above file and verify if data is available in that file.

        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        container1 = client.containers.run(BUSYBOX, "sh", detach=True,
                                          name=helpers.random_name(), tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/data1']
        )
        self.tmp_containers.append(container1.id)
        container1.exec_run("dd if=/dev/urandom of=/data1/random bs=10M count=1")
        container1.exec_run("sh -c 'md5sum /data1/random > /data1/checksum'")
        container1.stop()
        container1.wait()
        self.hpe_verify_volume_unmount(volume_name)

        container2 = client.containers.run(BUSYBOX, "sh", detach=True,
                                           name=helpers.random_name(), tty=True, stdin_open=True,
                                           volumes=[volume_name + ':/data1']
        )
        self.tmp_containers.append(container2.id)
        self.hpe_verify_volume_mount(volume_name)
        out = container2.exec_run("md5sum -cw /data1/checksum")
        self.assertEqual(out, b'/data1/random: OK\n')
        container1.stop()


