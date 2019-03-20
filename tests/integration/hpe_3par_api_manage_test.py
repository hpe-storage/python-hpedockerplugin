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
import urllib3
from hpe3parclient import client, exceptions
from hpe3parclient.client import HPE3ParClient
urllib3.disable_warnings()

# Importing test data from YAML config file
#with open("tests/integration/testdata/test_config.yml", 'r') as ymlfile:
with open("testdata/test_config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# Declaring Global variables and assigning the values from YAML config file
PLUGIN_TYPE = cfg['plugin']['type']
HOST_OS = cfg['platform']['os']
THIN_SIZE = cfg['volumes']['thin_size']
FULL_SIZE = cfg['volumes']['full_size']
ETCD = cfg['etcd']['container']
USER_CPG = cfg['backend']['user_cpg']
SNAP_CPG = cfg['snapshot']['snap_cpg']
HPE3PAR_API_URL = cfg['backend']['3Par_api_url']
HPE3PAR_IP = cfg['backend']['3Par_IP']
DOMAIN = cfg['qos']['domain']

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

hpe_3par_cli = HPE3ParClient(HPE3PAR_API_URL, True, False, None, True)

@requires_api_version('1.20')
class ManageVolumeTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

    @classmethod
    def setUpClass(cls):
        hpe_3par_cli.login('3paradm', '3pardata')
        pass
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

        delete_vol = ["python_snap_5", "python_vol_1","python_vol_2","python_vol_3", "python_vol_4","python_vol_5","python_vol_6","python_vol_7","python_vol_8","python_vol_9"]

        for vol_name in delete_vol:
            try:
                hpe_3par_cli.deleteVolume(vol_name)
            except:
                pass

        hpe_3par_cli.logout()
#        pass
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


    def test_manage_volume(self):
        '''
           This is a manage volume test case.

           Steps:
           1. Create volume on 3par array from CLI
           2. Manage the volume from docker using importVol option
           3. Create the snapshot and clone of volume
           4. Mount the volume
        '''
        vol_name = "python_vol_1"
        sizeMiB = 1024
        try:
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        container_name= helpers.random_name()
        snapshot_name= helpers.random_name()
        self.tmp_volumes.append(snapshot_name)
        clone_name= helpers.random_name()
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                importVol=vol_name)
        self.hpe_verify_volume_created(volume_name,provisioning='full',importVol=volume_name, size=1)
        self.hpe_inspect_volume(volume, size=1,
                                provisioning='full', importVol=vol_name)

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=1)
        self.hpe_verify_snapshot_created(volume_name, snapshot_name)
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=1,
                                provisioning='full')
        self.hpe_verify_volume_created(clone_name, size='1',
                                       provisioning='full', clone=True)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)

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
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)

    def test_manage_non_existing_volume(self):

        vol_name = "Not_Exist"
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                    importVol=vol_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 404)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

    def test_manage_volume_with_size_option(self):
        
        vol_name = "python_vol_2"
        sizeMiB = 1024
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                            size=5, importVol=vol_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

        hpe_3par_cli.deleteVolume(vol_name)

    def test_manage_volume_which_is_in_vvset_with_qos(self):

        vol_name = "python_vol_3"
        vvset_name = "python_vvset_3"
        sizeMiB = 1024
        qosRules = {'priority': 2,'ioMinGoal': 300, 'ioMaxLimit': 1000}
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
            hpe_3par_cli.createVolumeSet(vvset_name, setmembers=[vol_name])
            hpe_3par_cli.createQoSRules("python_vvset_3", qosRules)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                importVol=vol_name)
        self.hpe_verify_volume_created(volume_name,provisioning='full',importVol=volume_name, size=1)
        self.hpe_inspect_volume(volume, size=1, provisioning='full', importVol=vol_name, enabled=True,
                                maxIOPS='1000 IOs/sec', minIOPS='300 IOs/sec', priority='Normal',vvset_name=vvset_name)

        hpe_3par_cli.deleteVolumeSet(vvset_name)

    def test_manage_volume_which_is_in_vvset_without_qos(self):

        vol_name = "python_vol_4"
        vvset_name = "python_vvset_4"
        sizeMiB = 1024
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
            hpe_3par_cli.createVolumeSet(vvset_name, setmembers=[vol_name])
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                            importVol=vol_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 404)
        self.hpe_volume_not_created(volume_name)

        hpe_3par_cli.deleteVolumeSet(vvset_name)
        hpe_3par_cli.deleteVolume(vol_name)

    def test_manage_snap_without_managing_volume(self):
        '''
           This is a volume mount test.

           Steps:
           1. Create volume and verify if volume got created in docker host and 3PAR array
           2. Create a host config file to setup container.
           3. Create a container and mount volume to it.
           4. Verify if VLUN is available in 3Par array.
        '''
        vol_name = "python_vol_5"
        snap_name = "python_snap_5"
        sizeMiB = 1024
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB, {'snapCPG': SNAP_CPG})
            hpe_3par_cli.createSnapshot(snap_name, vol_name)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))
        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(snapshot_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                    importVol=snap_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)


    def test_manage_volume_with_other_option(self):

        vol_name = "python_vol_6"
        sizeMiB = 1024
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                            virtualCopyOf=vol_name, importVol=vol_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

        hpe_3par_cli.deleteVolume(vol_name)

    def test_manage_attached_volume(self):
        '''
           This is a volume mount test.

        '''

        vol_name = "python_vol_7"
        host_name = "python_host_7"
        sizeMiB = 1024
        try:

            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
            hpe_3par_cli.createHost(host_name,optional = {'domain': DOMAIN})
            hpe_3par_cli.createVLUN(vol_name, lun=0, hostname=host_name)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                            virtualCopyOf=vol_name, importVol=vol_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

        hpe_3par_cli.deleteVLUN(vol_name,0,hostname=host_name)
        hpe_3par_cli.deleteHost(host_name)
        hpe_3par_cli.deleteVolume(vol_name)


    def test_manage_volume_which_is_in_vvset_with_flashcache(self):

        urllib3.disable_warnings()
        vol_name = "python_vol_8"
        vvset_name = "python_vvset_8"
        sizeMiB = 1024
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
            hpe_3par_cli.createVolumeSet(vvset_name, setmembers=[vol_name])
            hpe_3par_cli.modifyVolumeSet(vvset_name, flashCachePolicy=1)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        container_name= helpers.random_name()
        snapshot_name= helpers.random_name()
        clone_name= helpers.random_name()
        self.tmp_volumes.append(snapshot_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                importVol=vol_name)

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=1)
        self.hpe_verify_snapshot_created(volume_name, snapshot_name)
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=1,
                                provisioning='full', flash_cache=True)
        self.hpe_verify_volume_created(clone_name, size='1',
                                       provisioning='full', clone=True)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)

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
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)

        hpe_3par_cli.deleteVolumeSet(vvset_name)

    def test_manage_volume_which_is_in_vvset_with_flashcache_and_qos(self):

        vol_name = "python_vol_9"
        vvset_name = "python_vvset_9"
        sizeMiB = 1024
        qosRules = {'priority': 2,'ioMinGoal': 300, 'ioMaxLimit': 1000}
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli.createVolume(vol_name, USER_CPG, sizeMiB)
            hpe_3par_cli.createVolumeSet(vvset_name, setmembers=[vol_name])
            hpe_3par_cli.modifyVolumeSet(vvset_name, flashCachePolicy=1)
            hpe_3par_cli.createQoSRules(vvset_name, qosRules)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                importVol=vol_name)
        self.hpe_verify_volume_created(volume_name,provisioning='full',importVol=volume_name, flash_cache='true', vvs_name=vvset_name, qos='true', size=1)
        self.hpe_inspect_volume(volume, size=1, provisioning='full', importVol=vol_name, flash_cache=True,
                                maxIOPS='1000 IOs/sec', minIOPS='300 IOs/sec', priority='Normal',vvset_name=vvset_name)

        hpe_3par_cli.deleteVolumeSet(vvset_name)


