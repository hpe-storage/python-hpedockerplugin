import tempfile
import docker
import os
import pytest
import yaml
from time import sleep
import six

from .base import TEST_API_VERSION, BUSYBOX
from . import helpers
from .helpers import requires_api_version
from .hpe_3par_manager import HPE3ParBackendVerification,HPE3ParVolumePluginTest

# Importing test data from YAML config file
#with open("tests/integration/testdata/test_config.yml", 'r') as ymlfile:
with open("testdata/test_config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# Declaring Global variables and assigning the values from YAML config file
PLUGIN_TYPE = cfg['plugin']['type']
HOST_OS = cfg['platform']['os']
THIN_SIZE = cfg['volumes']['thin_size']
ETCD = cfg['etcd']['container']

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

@requires_api_version('1.20')
class VolumeBindTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

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
                                 labels={'type': 'plugin'})
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
        container_name= helpers.random_name()
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/data1')
        self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, host_config=host_conf
                              )
        self.hpe_inspect_container_volume_mount(volume_name, container_name)
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
        container_name = helpers.random_name()
        self.tmp_containers.append(container_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/data1')
        container_info = self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, host_config=host_conf
                              )

        container_id = container_info['Id']
        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name)

        self.hpe_unmount_volume(container_id)
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
        # assert container.wait()['StatusCode'] == 0
        container.exec_run("sh -c 'echo \"hello\" > /insidecontainer/test'")
        ExecResult = container.exec_run("cat /insidecontainer/test")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"hello\n")
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
        exitcode = self.client.wait(ctnr)['StatusCode']
        assert exitcode == 0
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
        res = self.client.wait(ctnr)['StatusCode']
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
            self.hpe_delete_volume(vol)
            self.hpe_verify_volume_deleted(vol['Name'])

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
        # assert container.wait()['StatusCode'] == 0
        container.exec_run("sh -c 'echo \"hello\" > /insidecontainer/test'")
        container.stop()
        container.start()
        # assert container.wait()['StatusCode'] == 0

        ExecResult = container.exec_run("cat /insidecontainer/test")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"hello\n")

        try:
            self.client.remove_volume(volume_name)
        except docker.errors.APIError as ex:
            resp = ex.status_code
            self.assertEqual(resp, 409)

        container.stop()
        container.remove()
        self.hpe_verify_volume_created(volume_name,size=THIN_SIZE,provisioning='thin')

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_shared_volume(self):
        '''
           This is a shared volume test.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container1 and mount volume to it with command to create a file in 3Par volume.
           4. Create and start container2 with --volumes-from option mounting the volume from container1.
           5. Write data from container2 and verify the data of container1.
           6. Create and start container3 with --volumes-from option mounting the volume from container1 with read-only mode.
           7. Stop container1, container2 & container3.
           8. Remove all containers.
           9. Delete volume and verify removal from 3par array.
        '''

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
        # assert container1.wait()['StatusCode'] == 0
        container1.exec_run("sh -c 'echo \"This volume will be shared between containers.\" > /data1/Example1.txt'")

        container2 = client.containers.run(BUSYBOX, "sh", detach=True, name=mounters[1],
                                           volumes_from=mounters[0],
                                           tty=True, stdin_open=True
        )
        self.tmp_containers.append(container2.id)
        # assert container2.wait()['StatusCode'] == 0
        self.hpe_inspect_container_volume_mount(volume_name, mounters[1])
        self.hpe_verify_volume_mount(volume_name)
        container2.exec_run("sh -c 'echo \"Both containers will use this.\" >> /data1/Example1.txt'")
        ExecResult1 = container2.exec_run("cat /data1/Example1.txt")
        self.assertEqual(ExecResult1.output,
                         b'This volume will be shared between containers.\nBoth containers will use this.\n')
        self.assertEqual(ExecResult1.exit_code, 0)


        container3 = client.containers.run(BUSYBOX, "sh", detach=True, name=mounters[2],
                                           volumes_from=mounters[0] + ':ro',
                                           tty=True, stdin_open=True
        )
        self.tmp_containers.append(container3.id)
        # assert container3.wait()['StatusCode'] == 0
        self.hpe_inspect_container_volume_mount(volume_name, mounters[2])
        self.hpe_verify_volume_mount(volume_name)
        ExecResult2 = container3.exec_run("cat /data1/Example1.txt")
        self.assertEqual(ExecResult2.output,
                         b'This volume will be shared between containers.\nBoth containers will use this.\n')
        self.assertEqual(ExecResult2.exit_code, 0)

        ExecResult3 = container3.exec_run("touch /data1/Example2.txt")
        self.assertEqual(ExecResult3.output,
                         b'touch: /data1/Example2.txt: Read-only file system\n')
        self.assertNotEqual(ExecResult3.exit_code, 0)

        container1.stop()
        self.hpe_verify_volume_mount(volume_name)
        container2.stop()
        self.hpe_inspect_container_volume_mount(volume_name, mounters[1])
        self.hpe_verify_volume_mount(volume_name)

        container3.stop()
        self.hpe_inspect_container_volume_unmount(volume_name, mounters[2])
        self.hpe_verify_volume_unmount(volume_name)
        container_list = client.containers.list(all=True)
        for ctnr in container_list:
            try:
                self.client.remove_container(ctnr.id)
            except docker.errors.APIError:
                continue
        # removed_ctnr_list = client.containers.list(all=True)
        # assert len(removed_ctnr_list) == 1
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_checksum_persistance_of_binary_file(self):
        '''
           This is a test of verify checksum persistence of binary file in 3par volume.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Create a random binary file.
           5. Get the checksum of that file.
           6. Unmount the volume.
           7. Verify the checksum persistence of that binary file.
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
        # assert container1.wait()['StatusCode'] == 0
        container1.exec_run("dd if=/dev/urandom of=/data1/random bs=10M count=1")
        container1.exec_run("sh -c 'md5sum /data1/random > /data1/checksum'")
        container1.stop()
        self.hpe_verify_volume_unmount(volume_name)

        container2 = client.containers.run(BUSYBOX, "sh", detach=True,
                                           name=helpers.random_name(), tty=True, stdin_open=True,
                                           volumes=[volume_name + ':/data1']
        )
        self.tmp_containers.append(container2.id)
        # assert container2.wait()['StatusCode'] == 0
        self.hpe_verify_volume_mount(volume_name)
        ExecResult = container2.exec_run("md5sum -cw /data1/checksum")
        self.assertEqual(ExecResult.output, b'/data1/random: OK\n')
        self.assertEqual(ExecResult.exit_code, 0)
        container1.stop()

    def test_clone_mount_unmount_delete(self):
        '''
           This is a mount test of a cloned volume.

           Steps:
           1. Create a volume.
           2. Create a clone and verify if clone got created in docker host and 3PAR array
           3. Create a host config file to setup container.
           4. Create a container and mount clone to it.
           5. Verify if VLUN is available in 3Par array.
           6. Unmount the clone.
           7. Verify the unmount in 3par array.
           8. Delete the clone.
           9. Verify the removal of clone in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR)
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_verify_volume_created(clone_name, size='100',
                                       provisioning='thin', clone=True)
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= clone_name + ':/data1')
        mount = self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=helpers.random_name(), host_config=host_conf
                              )
        # Verifying in 3par
        self.hpe_verify_volume_mount(clone_name)

        try:
            self.client.remove_volume(clone_name)
        except docker.errors.APIError as ex:
            resp = ex.status_code
            self.assertEqual(resp, 409)

        id = mount['Id']
        # Unmount volume to this container
        self.client.stop(id)
        sleep(5)
        self.client.remove_container(id)
        self.hpe_verify_volume_unmount(clone_name)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)

    def test_read_clone_data(self):
        '''
           This is a test of reading data of cloned volume.

           Steps:
           1. Create a volume, mount it and write some data on it.
           2. Create a clone and verify if clone got created in docker host and 3PAR array
           3. Create a host config file to setup container.
           4. Create a container and mount clone to it.
           5. Read the data in cloned volume.
           6. Stop and remove the containers.
           7. Remove both volume and its clone.
           8. Verify the removal of volume and clone in 3par array.
        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR)
        container_volume = client.containers.run(BUSYBOX, "sh", detach=True,
                                          name=helpers.random_name(), tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/data1']
        )
        self.tmp_containers.append(container_volume.id)
        # assert container_volume.wait()['StatusCode'] == 0
        container_volume.exec_run("sh -c 'touch /data1/test'")
        container_volume.exec_run("sh -c 'echo \"cloned_data\" > /data1/test'")
        container_volume.stop()
        container_volume.remove()
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_verify_volume_created(clone_name, size='100',
                                       provisioning='thin', clone=True)
        container_name = helpers.random_name()
        container_clone = client.containers.run(BUSYBOX, "sh", detach=True,
                                                name= container_name, tty=True, stdin_open=True,
                                                volumes=[clone_name + ':/data1']
        )
        self.tmp_containers.append(container_clone.id)
        # assert container_clone.wait()['StatusCode'] == 0
        self.hpe_inspect_container_volume_mount(clone_name, container_name)
        self.hpe_verify_volume_mount(clone_name)
        ExecResult = container_clone.exec_run("sh -c 'cat /data1/test'")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"cloned_data\n")
        container_clone.stop()
        self.hpe_inspect_container_volume_unmount(clone_name, container_name)
        container_clone.remove()
        self.hpe_verify_volume_unmount(volume_name)
        self.hpe_verify_volume_unmount(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)

    def test_mount_volume_create_snapshots(self):
        '''
            This is a snapshot create test of a mounted volume.

            Steps:
            1. Create a volume.
            2. Create a container and mount volume to it.
            3. Create multiple snapshots with and without expiration period.
            4. Inspect snapshots.
            5. Verify the snapshots in 3par array.
            6. Unmount the volume.
            7. Verify the unmount in 3par array.
            8. Delete all the snapshots and volume.
            9. Verify the removal of snapshots and volume in 3par array.
         '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        snapshot_names = []
        i = 0; j = 0; k = 0
        for i in range(3):
            snapshot_names.append(helpers.random_name())
            self.tmp_volumes.append(snapshot_names[i])
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        container_name = helpers.random_name()
        container = client.containers.run(BUSYBOX, "sh", detach=True,
                                          name=container_name, tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/data1']
        )
        self.tmp_containers.append(container.id)
        # assert container.wait()['StatusCode'] == 0
        container.exec_run("sh -c 'echo \"snapshot_data\" > /data1/test'")

        snapshot1 = self.hpe_create_snapshot(snapshot_names[0], driver=HPE3PAR,
                                             virtualCopyOf=volume_name)
        snapshot2 = self.hpe_create_snapshot(snapshot_names[1], driver=HPE3PAR,
                                             virtualCopyOf=volume_name, expirationHours='2')
        snapshot3 = self.hpe_create_snapshot(snapshot_names[2], driver=HPE3PAR,
                                             virtualCopyOf=volume_name, expirationHours='6')
        self.hpe_inspect_snapshot(snapshot1, snapshot_name=snapshot_names[0],
                                  virtualCopyOf=volume_name, size=THIN_SIZE)
        self.hpe_inspect_snapshot(snapshot2, snapshot_name=snapshot_names[1],
                                  virtualCopyOf=volume_name, size=THIN_SIZE,
                                  expirationHours='2')
        self.hpe_inspect_snapshot(snapshot3, snapshot_name=snapshot_names[2],
                                  virtualCopyOf=volume_name, size=THIN_SIZE,
                                  expirationHours='6')
        self.hpe_verify_snapshot_created(volume_name, snapshot_names[0])
        self.hpe_verify_snapshot_created(volume_name, snapshot_names[1], expirationHours='2')
        self.hpe_verify_snapshot_created(volume_name, snapshot_names[2], expirationHours='6')
        inspect_volume_snapshot = self.client.inspect_volume(volume_name)
        snapshots = inspect_volume_snapshot['Status']['Snapshots']
        snapshot_list = []
        for j in range(len(snapshots)):
            snapshot_list.append(snapshots[j]['Name'])
        for snapshot in snapshot_names:
            self.assertIn(snapshot, snapshot_list)
        container.stop()
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)
        self.hpe_verify_volume_unmount(volume_name)
        container.remove()
        for snapshot in snapshot_names:
            self.hpe_delete_snapshot(volume_name, snapshot)
            self.hpe_verify_snapshot_deleted(volume_name, snapshot)
        inspect_volume_snapshot = self.client.inspect_volume(volume_name)
        if 'Snapshots' not in inspect_volume_snapshot['Status']:
            pass
        else:
            snapshots = inspect_volume_snapshot['Status']['Snapshots']
            snapshot_list = []
            for k in range(len(snapshots)):
                snapshot_list.append(snapshots[k]['Name'])
            for snapshot in snapshot_names:
                self.assertNotIn(snapshot, snapshot_list)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_mount_unmount_compressed_volume(self):
        '''
           This is a test to verify mount and unmount a compressed volume.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Inspect containers and verify the volume is mounted or not
           5. Verify if VLUN is available in 3Par array.
           6. Write data on volume
           7. Unmount the volume
           8. Verify if VLUN entry is not available in 3Par array.
           9. Read the data from the volume

        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        container_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size="17", provisioning='thin', compression='true')
        container = client.containers.run(BUSYBOX,"sh", detach=True,
                                          name=container_name, tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/insidecontainer']
        )
        self.tmp_containers.append(container.id)
        # assert container.wait()['StatusCode'] == 0
        self.hpe_inspect_container_volume_mount(volume_name,container_name)
        self.hpe_verify_volume_mount(volume_name)
        container.exec_run("sh -c 'echo \"hello compressed volume\" > /insidecontainer/test'")
        container.stop()
        self.hpe_inspect_container_volume_unmount(volume_name,container_name)
        self.hpe_verify_volume_unmount(volume_name)
        container.start()
        ExecResult = container.exec_run("cat /insidecontainer/test")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"hello compressed volume\n")
        container.stop()
        container.remove()
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_delete_compressed_volume(self):
        '''
           This is a delete compressed volume test.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Try to delete the volume - it should not get deleted
           5. List volumes - Volume should be listed
           6. Stop the container
           7. Delete the volume - Volume should get deleted.
           8. List volumes - Volume should not be listed.

        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        container_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size="17", provisioning='thin', compression='true')
        container = client.containers.run(BUSYBOX,"sh", detach=True,
                                          name=container_name, tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/insidecontainer']
        )
        self.tmp_containers.append(container.id)
        # assert container.wait()['StatusCode'] == 0
        try:
            self.client.remove_volume(volume_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 409)
        self.hpe_verify_volume_created(volume_name,size="17",provisioning='thin')
        container.stop()
        container.remove()

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_mount_unmount_snapshots(self):
        '''
            This is a reverting a volume from its snapshots test.

            Steps:
            1. Create a volume.
            2. Create a container and mount volume to it.
            3. Write data.
            4. Create snapshot1 without expiration period.
            5. Write data again on volume.
            6. Create snapshot2 with expiration period.
            7. Write data again on volume.
            8. Mount snapshot1 and verify the data.
            9. Mount snapshot2 and verify the data.
            10. Unmount the volume, snapshot1 and snapshot2.
            11. Verify the unmount in 3par array.
            12. Delete all the snapshots, container and volume.
            13. Verify the removal of snapshots and volume in 3par array.
        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        snapshot_names = []
        i = 0; j = 0
        for i in range(2):
            snapshot_names.append(helpers.random_name())
            self.tmp_volumes.append(snapshot_names[i])
        self.tmp_volumes.append(volume_name)

        container_names = []
        k = 0
        for k in range(3):
            container_names.append(helpers.random_name())

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')
        container_volume = client.containers.run(BUSYBOX, "sh", detach=True,
                                          name=container_names[0], tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/data1']
        )
        self.tmp_containers.append(container_volume.id)
        # assert container.wait()['StatusCode'] == 0
        container_volume.exec_run("sh -c 'echo \"snapshot_data1\" > /data1/test1'")
        container_volume.stop()

        self.hpe_create_snapshot(snapshot_names[0], driver=HPE3PAR,
                                 virtualCopyOf=volume_name)

        container_snapshot1 = client.containers.run(BUSYBOX, "sh", detach=True,
                                                    name=container_names[1], tty=True, stdin_open=True,
                                                    volumes=[snapshot_names[0] + ':/data1']
        )
        self.tmp_containers.append(container_snapshot1.id)
        self.hpe_inspect_container_volume_mount(snapshot_names[0], container_names[1])
        self.hpe_verify_snapshot_mount(snapshot_names[0])

        ExecResult1 = container_snapshot1.exec_run("sh -c 'ls data1/'")
        self.assertEqual(ExecResult1.exit_code, 0)
        self.assertEqual(ExecResult1.output, b"test1\n")
        ExecResult2 = container_snapshot1.exec_run("sh -c 'cat /data1/test1'")
        self.assertEqual(ExecResult2.exit_code, 0)
        self.assertEqual(ExecResult2.output, b"snapshot_data1\n")
        container_snapshot1.stop()

        container_volume.start()
        container_volume.exec_run("sh -c 'echo \"snapshot_data2\" > /data1/test2'")
        container_volume.stop()

        self.hpe_create_snapshot(snapshot_names[1], driver=HPE3PAR,
                                 virtualCopyOf=volume_name, expirationHours='2')

        container_snapshot2 = client.containers.run(BUSYBOX, "sh", detach=True,
                                                    name=container_names[2], tty=True, stdin_open=True,
                                                    volumes=[snapshot_names[1] + ':/data1']
                                                    )
        self.tmp_containers.append(container_snapshot2.id)
        self.hpe_inspect_container_volume_mount(snapshot_names[1], container_names[2])
        self.hpe_verify_snapshot_mount(snapshot_names[1])

        ExecResult3 = container_snapshot2.exec_run("sh -c 'ls data1/'")
        self.assertEqual(ExecResult3.exit_code, 0)
        self.assertEqual(ExecResult3.output, b"test1\ntest2\n")
        ExecResult4 = container_snapshot2.exec_run("sh -c 'cat /data1/test1'")
        self.assertEqual(ExecResult4.exit_code, 0)
        self.assertEqual(ExecResult4.output, b"snapshot_data1\n")
        ExecResult5 = container_snapshot2.exec_run("sh -c 'cat /data1/test2'")
        self.assertEqual(ExecResult5.exit_code, 0)
        self.assertEqual(ExecResult5.output, b"snapshot_data2\n")
        container_snapshot2.stop()

        self.hpe_inspect_container_volume_unmount(snapshot_names[0], container_names[1])
        self.hpe_inspect_container_volume_unmount(snapshot_names[1], container_names[2])

        container_volume.remove()
        container_snapshot1.remove()
        container_snapshot2.remove()

        self.hpe_verify_volume_unmount(volume_name)

        for snapshot in snapshot_names:
            self.hpe_verify_snapshot_unmount(snapshot)
            self.hpe_delete_snapshot(volume_name, snapshot)
            self.hpe_verify_snapshot_deleted(volume_name, snapshot)
        inspect_volume_snapshot = self.client.inspect_volume(volume_name)
        if 'Snapshots' not in inspect_volume_snapshot['Status']:
            pass
        else:
            snapshots = inspect_volume_snapshot['Status']['Snapshots']
            snapshot_list = []
            for j in range(len(snapshots)):
                snapshot_list.append(snapshots[j]['Name'])
            for snapshot in snapshot_names:
                self.assertNotIn(snapshot, snapshot_list)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_mount_unmount_volume_with_qos(self):
        '''
           This is a test to verify mount and unmount operations of qos enabled volume.

           Steps:
           1. Create volume with qosName and verify if volume got created in docker host and 3PAR array
           2. Create a container and mount volume to it.
           3. Inspect containers and verify the volume is mounted or not
           4. Verify if VLUN is available in 3Par array.
           5. Write data on volume
           6. Unmount the volume
           8. Verify if VLUN entry is not available in 3Par array.
           9. Read the data from the volume
           10. Unmount volume and remove container.
           11. Delete volume and verify it is not present in 3par array.

        '''
        client = docker.from_env(version=TEST_API_VERSION)
        volume_name = helpers.random_name()
        container_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        vvset_name = helpers.random_name()
        self.hpe_create_verify_vvs_with_qos(vvs_name=vvset_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, qos_name=vvset_name,
                                        size=THIN_SIZE, provisioning='thin')
        container = client.containers.run(BUSYBOX,"sh", detach=True,
                                          name=container_name, tty=True, stdin_open=True,
                                          volumes=[volume_name + ':/insidecontainer']
        )
        self.tmp_containers.append(container.id)
        # assert container.wait()['StatusCode'] == 0
        self.hpe_verify_volume_created(volume_name, vvset_name,
                                       size=THIN_SIZE, provisioning='thin')
        self.hpe_inspect_container_volume_mount(volume_name,container_name)
        self.hpe_verify_volume_mount(volume_name)
        container.exec_run("sh -c 'echo \"QoS rule\" > /insidecontainer/test'")
        container.stop()
        self.hpe_inspect_container_volume_unmount(volume_name,container_name)
        self.hpe_verify_volume_unmount(volume_name)
        container.start()
        ExecResult = container.exec_run("cat /insidecontainer/test")
        self.assertEqual(ExecResult.exit_code, 0)
        self.assertEqual(ExecResult.output, b"QoS rule\n")
        container.stop()
        container.remove()
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)
        self.hpe_remove_vvs_qos(vvs_name=vvset_name)

    def test_volume_mount_multiple_containers(self):
        '''
           This will test a volume mount operation to multiple containers within same node.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a container1 and mount volume to it with command to create a file in 3Par volume.
           3. Create a container2 and mount the same volume to it
           4. Write data from container2 and verify the data of container1.
           6. Create a container3 and mount the same volume in read-only mode.
           7. Read the data from container3.
           8. Stop container1, container2 & container3.
           9. Remove all containers.
           10. Delete volume and verify removal from 3par array.
        '''
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
        # assert container1.wait()['StatusCode'] == 0
        container1.exec_run("sh -c 'echo \"This volume will be shared between containers.\" > /data1/Example1.txt'")

        container2 = client.containers.run(BUSYBOX, "sh", detach=True, name=mounters[1],
                                           volumes=[volume_name + ':/data1'],
                                           tty=True, stdin_open=True
        )
        self.tmp_containers.append(container2.id)
        # assert container2.wait()['StatusCode'] == 0
        self.hpe_inspect_container_volume_mount(volume_name, mounters[1])
        self.hpe_verify_volume_mount(volume_name)
        container2.exec_run("sh -c 'echo \"Both containers will use this.\" >> /data1/Example1.txt'")
        ExecResult1 = container2.exec_run("cat /data1/Example1.txt")
        self.assertEqual(ExecResult1.output,
                         b'This volume will be shared between containers.\nBoth containers will use this.\n')
        self.assertEqual(ExecResult1.exit_code, 0)

        container3 = client.containers.run(BUSYBOX, "sh", detach=True, name=mounters[2],
                                           volumes=[volume_name + ':/data1:ro'],
                                           tty=True, stdin_open=True
        )
        self.tmp_containers.append(container3.id)
        # assert container3.wait()['StatusCode'] == 0
        self.hpe_inspect_container_volume_mount(volume_name, mounters[2])
        self.hpe_verify_volume_mount(volume_name)
        ExecResult2 = container3.exec_run("cat /data1/Example1.txt")
        self.assertEqual(ExecResult2.output,
                         b'This volume will be shared between containers.\nBoth containers will use this.\n')
        self.assertEqual(ExecResult2.exit_code, 0)

        ExecResult3 = container3.exec_run("touch /data1/Example2.txt")
        self.assertEqual(ExecResult3.output,
                         b'touch: /data1/Example2.txt: Read-only file system\n')
        self.assertNotEqual(ExecResult3.exit_code, 0)

        container1.stop()
        self.hpe_verify_volume_mount(volume_name)
        container2.stop()
        self.hpe_inspect_container_volume_mount(volume_name, mounters[1])
        self.hpe_verify_volume_mount(volume_name)

        container3.stop()
        self.hpe_inspect_container_volume_unmount(volume_name, mounters[2])
        self.hpe_verify_volume_unmount(volume_name)
        container_list = client.containers.list(all=True)
        for ctnr in container_list:
            try:
                self.client.remove_container(ctnr.id)
            except docker.errors.APIError:
                continue
        # removed_ctnr_list = client.containers.list(all=True)
        # assert len(removed_ctnr_list) == 1
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)




