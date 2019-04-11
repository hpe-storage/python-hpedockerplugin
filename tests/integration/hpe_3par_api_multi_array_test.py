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
from hpe3parclient.client import HPE3ParClient
import urllib3


urllib3.disable_warnings()


# Importing test data from YAML config file
#with open("tests/integration/testdata/test_config.yml", 'r') as ymlfile:
with open("testdata/test_config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# Declaring Global variables and assigning the values from YAML config file
PLUGIN_TYPE = cfg['plugin']['type']
HOST_OS = cfg['platform']['os']
THIN_SIZE = cfg['volumes']['thin_size']
ETCD = cfg['etcd']['container']
USER_CPG = cfg['backend']['user_cpg']
USER_CPG2 = cfg['backend2']['user_cpg']
MULTI_CPG = cfg['backend']['multi_cpg']
SNAP_CPG = cfg['snapshot']['snap_cpg']
SNAP_CPG2 = cfg['snapshot2']['snap_cpg']
HPE3PAR_API_URL = cfg['backend']['3Par_api_url']
HPE3PAR2_API_URL = cfg['backend2']['3Par_api_url']
DOMAIN = cfg['qos']['domain']
DOMAIN2 = cfg['qos']['domain2']

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
hpe_3par_cli2 = HPE3ParClient(HPE3PAR2_API_URL, True, False, None, True)

@requires_api_version('1.20')
class MultiArrayTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

    @classmethod
    def setUpClass(cls):

        hpe_3par_cli.login('3paradm', '3pardata')
        hpe_3par_cli2.login('3paradm', '3pardata')

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

        delete_vol = ["python_vol_1_snap", "python_vol_1","python_vol_2_snap","python_vol_2","python_vol_3", "python_vol_4","python_vol_5","python_vol_6","python_vol_7","python_vol_8","python_vol_9"]
        delete_vvset = ["python_vvset_6", "python_vvset_7", "python_vvset_8"]

#*****below hardcoded teardown function to remove vlun entry in case of already managed volume fails.
        try:
            hpe_3par_cli2.deleteVLUN("python_vol_5",0,hostname="python_host_5")
            hpe_3par_cli2.deleteHost("python_host_5") 
        except:
            pass

        for vvset_name in delete_vvset:
            try:
                hpe_3par_cli2.deleteVolumeSet(vvset_name)
            except:
                pass

        for vol_name in delete_vol:
            try:
                hpe_3par_cli.deleteVolume(vol_name)
            except:
                pass

        for vol_name in delete_vol:
            try:
                hpe_3par_cli2.deleteVolume(vol_name)
            except:
                pass

        hpe_3par_cli.logout()
        hpe_3par_cli2.logout()

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


    def test_default_array_in_presence_of_multiarray(self):

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)
        clone_name = helpers.random_name()
        self.tmp_volumes.append(clone_name)
        container_name = helpers.random_name()
        self.tmp_volumes.append(container_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='full')
        self.hpe_verify_volume_created(volume_name,provisioning='full',
                                       size=THIN_SIZE)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='full')
        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                               virtualCopyOf=volume_name, size=int(THIN_SIZE))
        self.hpe_verify_snapshot_created(volume_name, snapshot_name)
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                      cloneOf=volume_name)
        self.hpe_inspect_volume(clone, size=int(THIN_SIZE),
                                provisioning='full')
        self.hpe_verify_volume_created(clone_name, size=THIN_SIZE,
                                       provisioning='full', clone=True)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        
        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                               binds= volume_name + ':/data1')
        container_info = self.hpe_mount_volume(BUSYBOX, command='sh',
                              detach=True, tty=True, stdin_open=True,
                          name=container_name, host_config=host_conf)
        container_id = container_info['Id']
        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name)
        self.hpe_unmount_volume(container_id)
        # Verifying in 3par
        self.hpe_verify_volume_unmount(volume_name)
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)
        self.client.remove_container(container_id)

        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)


    def test_multi_array_support(self):
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)

        clone_name = helpers.random_name()
        self.tmp_volumes.append(clone_name)

        container_name= helpers.random_name()
        self.tmp_containers.append(container_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, 
                                        size=THIN_SIZE, provisioning='full',
                                        backend="backend2"
                                       )
        self.hpe_verify_volume_created(volume_name, provisioning='full', 
                                       size=THIN_SIZE, backend="backend2")
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE), 
                                provisioning='full', backend="backend2")

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                               virtualCopyOf=volume_name, size=int(THIN_SIZE),
                               backend="backend2")
        self.hpe_verify_snapshot_created(volume_name, snapshot_name,
                                         backend="backend2")

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                      cloneOf=volume_name)
        self.hpe_inspect_volume(clone, size=int(THIN_SIZE),
                                provisioning='full')
        self.hpe_verify_volume_created(clone_name, size=THIN_SIZE,
                                       provisioning='full', clone=True, 
                                       backend="backend2")

        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                               binds= volume_name + ':/data1')
        container_info = self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, host_config=host_conf
                              )

        container_id = container_info['Id']
        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name, backend="backend2")

        self.hpe_unmount_volume(container_id)
        # Verifying in 3par
        self.hpe_verify_volume_unmount(volume_name, backend="backend2")
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)
        self.client.remove_container(container_id)

        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name, backend="backend2")

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name, backend="backend2")

        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)


    def test_create_volume_in_both_array_randomly(self):

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume_name1 = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume_name2 = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume_name3 = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='full')

        volume1 = self.hpe_create_volume(volume_name1, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='thin',
                                        backend="backend2")

        volume2 = self.hpe_create_volume(volume_name2, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='full')

        volume3 = self.hpe_create_volume(volume_name3, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='thin',
                                        backend="backend2")

        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='full')
        self.hpe_inspect_volume(volume1, size=int(THIN_SIZE),
                                provisioning='thin', backend="backend2")
        self.hpe_inspect_volume(volume2, size=int(THIN_SIZE),
                                provisioning='full')
        self.hpe_inspect_volume(volume3, size=int(THIN_SIZE),
                                provisioning='thin', backend="backend2")

        self.hpe_verify_volume_created(volume_name, provisioning='full',
                                       size=THIN_SIZE)
        self.hpe_verify_volume_created(volume_name1, provisioning='thin',
                                       size=THIN_SIZE, backend="backend2")
        self.hpe_verify_volume_created(volume_name2, provisioning='full',
                                       size=THIN_SIZE)
        self.hpe_verify_volume_created(volume_name3, provisioning='thin',
                                       size=THIN_SIZE, backend="backend2")

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

        self.hpe_delete_volume(volume1)
        self.hpe_verify_volume_deleted(volume_name1, backend="backend2")

        self.hpe_delete_volume(volume2)
        self.hpe_verify_volume_deleted(volume_name2)

        self.hpe_delete_volume(volume3)
        self.hpe_verify_volume_deleted(volume_name3, backend="backend2")


    def test_create_delete_volume_from_both_array(self):

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume_name1 = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE))
        self.hpe_verify_volume_created(volume_name, size=THIN_SIZE)

        volume1 = self.hpe_create_volume(volume_name1, driver=HPE3PAR,
                                        size=THIN_SIZE, backend="backend2")
        self.hpe_inspect_volume(volume1, size=int(THIN_SIZE),
                                backend="backend2")
        self.hpe_verify_volume_created(volume_name1, size=THIN_SIZE, 
                                               backend="backend2")

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

        self.hpe_delete_volume(volume1)
        self.hpe_verify_volume_deleted(volume_name1, backend="backend2")


    def test_multi_array_to_manage_volume_and_snapshot(self):

        vol_name = "python_vol_1"
        sizeMiB = 1024
        try:
            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB,
                                       {'snapCPG': SNAP_CPG2})
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        snap_name = "python_vol_1_snap"
        try:
            hpe_3par_cli2.createSnapshot(snap_name, vol_name)
        except Exception as e:
            print("Unable to create volume {}: {}".format(snap_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume_name1= helpers.random_name()
        self.tmp_volumes.append(volume_name1)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        importVol=vol_name, backend="backend2")
        self.hpe_inspect_volume(volume, importVol=vol_name, size=1,
                                provisioning='full', backend="backend2")
        self.hpe_verify_volume_created(volume_name, importVol=volume_name,
                                size=1, provisioning='full', backend="backend2")

        volume1 = self.hpe_create_volume(volume_name1, driver=HPE3PAR,
                                       importVol=snap_name, backend="backend2")
        self.hpe_inspect_snapshot(volume1, snapshot_name=volume_name1,
                                  size=1, importVol=snap_name,
                                  virtualCopyOf=volume_name,backend="backend2")
        self.hpe_verify_snapshot_created(volume_name, volume_name1,
                                       size=1, importVol=volume_name1,
                                       provisioning='full', backend="backend2")

        self.hpe_delete_volume(volume1)
        self.hpe_verify_volume_deleted(volume_name1, backend="backend2")

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name, backend="backend2")


    def test_multi_array_to_manage_snapshot_without_volume(self):

        vol_name = "python_vol_2"
        sizeMiB = 1024
        try:
            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB,
                                       {'snapCPG': SNAP_CPG2})
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        snap_name = "python_vol_2_snap"
        try:
            hpe_3par_cli2.createSnapshot(snap_name, vol_name)
        except Exception as e:
            print("Unable to create volume {}: {}".format(snap_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                       importVol=snap_name, backend="backend2")
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)


    def test_multi_array_along_with_importvol_option(self):

        vol_name = "python_vol_3"
        sizeMiB = 1024
        try:
            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB,
                                       {'snapCPG': SNAP_CPG2})
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        importVol=vol_name, backend="backend2")
        self.hpe_inspect_volume(volume, importVol=vol_name, size=1,
                                provisioning='full', backend="backend2")
        self.hpe_verify_volume_created(volume_name, importVol=volume_name,
                               size=1, provisioning='full', backend="backend2")

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name, backend="backend2")


    def test_multi_array_to_manage_non_existing_volume(self):


        vol_name = "python_vol_4"
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        importVol=vol_name, backend="backend2")
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 404)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)


    def test_multi_array_to_manage_already_attached_volume(self):

        vol_name = "python_vol_5"
        host_name = "python_host_5"
        sizeMiB = 1024
        try:

            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB)
            hpe_3par_cli2.createHost(host_name,optional = {'domain': DOMAIN2})
            hpe_3par_cli2.createVLUN(vol_name, lun=0, hostname=host_name)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                            importVol=vol_name, backend='backend2')
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

        hpe_3par_cli2.deleteVLUN(vol_name,0,hostname=host_name)
        hpe_3par_cli2.deleteHost(host_name)
        hpe_3par_cli2.deleteVolume(vol_name)


    def test_multi_array_to_manage_volume_of_vvset_with_flashcache(self):

        urllib3.disable_warnings()
        vol_name = "python_vol_6"
        vvset_name = "python_vvset_6"
        sizeMiB = 1024
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB)
            hpe_3par_cli2.createVolumeSet(vvset_name, setmembers=[vol_name])
            hpe_3par_cli2.modifyVolumeSet(vvset_name, flashCachePolicy=1)
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
                                importVol=vol_name, backend='backend2')

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,size=1,
                                  virtualCopyOf=volume_name,backend='backend2')
        self.hpe_verify_snapshot_created(volume_name, snapshot_name,
                                                 backend='backend2')
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name,
                                                 backend='backend2')

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=1, provisioning='full',
                                flash_cache=True)
        self.hpe_verify_volume_created(clone_name,size='1',provisioning='full',
                                       clone=True,backend='backend2')
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name, backend='backend2')

        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/data1')
        container_info = self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, host_config=host_conf
                              )

        container_id = container_info['Id']
        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name, backend='backend2')

        self.hpe_unmount_volume(container_id)
        # Verifying in 3par
        self.hpe_verify_volume_unmount(volume_name, backend='backend2')
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)
        self.client.remove_container(container_id)

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name,backend='backend2')

        hpe_3par_cli2.deleteVolumeSet(vvset_name)


    def test_multi_array_to_manage_volume_of_vvset_with_qos(self):

        vol_name = "python_vol_8"
        vvset_name = "python_vvset_8"
        sizeMiB = 1024
        qosRules = {'priority': 2,'ioMinGoal': 300, 'ioMaxLimit': 1000}
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB)
            hpe_3par_cli2.createVolumeSet(vvset_name, setmembers=[vol_name])
            hpe_3par_cli2.createQoSRules("python_vvset_8", qosRules)
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)
        clone_name = helpers.random_name()
        self.tmp_volumes.append(clone_name)
        container_name = helpers.random_name()
        self.tmp_volumes.append(container_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                importVol=vol_name, backend='backend2')
        self.hpe_verify_volume_created(volume_name,provisioning='full', size=1,
                                     importVol=volume_name, backend='backend2',
                                     vvs_name=vvset_name, qos='true')
        self.hpe_inspect_volume(volume,provisioning='full',size=1,enabled=True,
                                importVol=vol_name, backend='backend2',
                                maxIOPS='1000 IOs/sec', minIOPS='300 IOs/sec',
                                priority='Normal',vvset_name=vvset_name)

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                               size=1, virtualCopyOf=volume_name,
                               backend="backend2")
        self.hpe_verify_snapshot_created(volume_name, snapshot_name,
                                         size=1, backend="backend2")

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                      cloneOf=volume_name)
        self.hpe_inspect_volume(clone, provisioning='full', size=1)
        self.hpe_verify_volume_created(clone_name, clone=True, size=1,
                                       provisioning='full', backend="backend2")

        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                               binds= volume_name + ':/data1')
        container_info = self.hpe_mount_volume(BUSYBOX, command='sh', detach=True,
                              tty=True, stdin_open=True,
                              name=container_name, host_config=host_conf
                              )

        container_id = container_info['Id']
        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name, backend="backend2")

        self.hpe_unmount_volume(container_id)
        # Verifying in 3par
        self.hpe_verify_volume_unmount(volume_name, backend="backend2")
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)
        self.client.remove_container(container_id)

        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name, backend="backend2")

        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)

        hpe_3par_cli2.deleteVolumeSet(vvset_name)

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name, backend="backend2")


    def test_multi_array_to_manage_volume_of_vvset_without_flashcache(self):

        urllib3.disable_warnings()
        vol_name = "python_vol_7"
        vvset_name = "python_vvset_7"
        sizeMiB = 1024
        try:
            print("Create volume {}".format(vol_name))
            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB)
            hpe_3par_cli2.createVolumeSet(vvset_name, setmembers=[vol_name])
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        importVol=vol_name, backend='backend2')
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 404)

        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)


    def test_multi_array_for_both_ISCSI_and_FC(self):

        urllib3.disable_warnings()
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume_name1 = helpers.random_name()
        self.tmp_volumes.append(volume_name1)

        container_name= helpers.random_name()
        self.tmp_containers.append(container_name)
        container_name1= helpers.random_name()
        self.tmp_containers.append(container_name1)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='full')
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='full')
        self.hpe_verify_volume_created(volume_name,provisioning='full',
                                       size=THIN_SIZE)

        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name + ':/data1')
        container_info = self.hpe_mount_volume(BUSYBOX, command='sh',
                              detach=True, tty=True, stdin_open=True,
                           name=container_name, host_config=host_conf)
        container_id = container_info['Id']
        self.hpe_inspect_container_volume_mount(volume_name, container_name)

        volume1 = self.hpe_create_volume(volume_name1, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='full',
                                        backend='backend3')
        self.hpe_inspect_volume(volume1, size=int(THIN_SIZE),
                                provisioning='full', backend='backend3')
        self.hpe_verify_volume_created(volume_name1,provisioning='full',
                                       size=THIN_SIZE, backend='backend3')

        host_conf1 = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                                binds= volume_name1 + ':/data1')
        container_info1 = self.hpe_mount_volume(BUSYBOX, command='sh',
                              detach=True, tty=True, stdin_open=True,
                           name=container_name1, host_config=host_conf1)
        container_id1 = container_info1['Id']
        self.hpe_inspect_container_volume_mount(volume_name1, container_name1)


        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name)
        try:
            self.hpe_verify_volume_mount(volume_name1, backend='backend3')
        except Exception as ex:
            pass
        self.hpe_unmount_volume(container_id)
        self.hpe_unmount_volume(container_id1)
        # Verifying in 3par
        self.hpe_verify_volume_unmount(volume_name)
        self.hpe_verify_volume_unmount(volume_name1, backend='backend3')
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)
        self.client.remove_container(container_id)
        self.hpe_inspect_container_volume_unmount(volume_name1, container_name1)
        self.client.remove_container(container_id1)

        self.hpe_delete_volume(volume)
        self.hpe_delete_volume(volume1)
        self.hpe_verify_volume_deleted(volume_name)
        self.hpe_verify_volume_deleted(volume_name1, backend='backend3')



    def test_multi_array_to_manage_volume_and_snapshot_which_created_with_backend_name(self):

        vol_name = "python_vol_1"
        sizeMiB = 1024
        try:
            hpe_3par_cli2.createVolume(vol_name, USER_CPG2, sizeMiB,
                                       {'snapCPG': SNAP_CPG2})
        except Exception as e:
            print("Unable to create volume {}: {}".format(vol_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        volume_name1= helpers.random_name()
        self.tmp_volumes.append(volume_name1)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        importVol=vol_name, backend="backend2")
        self.hpe_inspect_volume(volume, importVol=vol_name, size=1,
                                provisioning='full', backend="backend2")
        self.hpe_verify_volume_created(volume_name, importVol=volume_name,
                                size=1, provisioning='full', backend="backend2")

        inspect_volume = self.client.inspect_volume(volume['Name'])
        backend_name = inspect_volume['Status']['volume_detail']['3par_vol_name']

        snap_name = "python_vol_1_snap"
        try:
            hpe_3par_cli2.createSnapshot(snap_name, backend_name)
        except Exception as e:
            print("Unable to create volume {}: {}".format(snap_name, e))

        volume1 = self.hpe_create_volume(volume_name1, driver=HPE3PAR,
                                       importVol=snap_name, backend="backend2")
        self.hpe_inspect_snapshot(volume1, snapshot_name=volume_name1,
                                  size=1, importVol=snap_name,
                                  virtualCopyOf=volume_name,backend="backend2")
        self.hpe_verify_snapshot_created(volume_name, volume_name1,
                                       size=1, importVol=volume_name1,
                                       provisioning='full', backend="backend2")

        self.hpe_delete_volume(volume1)
        self.hpe_verify_volume_deleted(volume_name1, backend="backend2")


    def test_multiarray_with_edit_priviledge_user(self):

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume_name1 = helpers.random_name()
        self.tmp_volumes.append(volume_name1)
        container_name = helpers.random_name()
        self.tmp_volumes.append(container_name)
        container_name1 = helpers.random_name()
        self.tmp_volumes.append(container_name1)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='full')
        self.hpe_verify_volume_created(volume_name,provisioning='full',
                                       size=THIN_SIZE)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='full')

        host_conf = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                               binds= volume_name + ':/data1')
        container_info = self.hpe_mount_volume(BUSYBOX, command='sh',
                              detach=True, tty=True, stdin_open=True,
                          name=container_name, host_config=host_conf)
        container_id = container_info['Id']
        self.hpe_inspect_container_volume_mount(volume_name, container_name)
        # Verifying in 3par
        self.hpe_verify_volume_mount(volume_name)
        self.hpe_unmount_volume(container_id)
        # Verifying in 3par
        self.hpe_verify_volume_unmount(volume_name)
        self.hpe_inspect_container_volume_unmount(volume_name, container_name)
        self.client.remove_container(container_id)

        volume1 = self.hpe_create_volume(volume_name1, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='full',
                                        backend='backend4')
        self.hpe_verify_volume_created(volume_name1,provisioning='full',
                                       size=THIN_SIZE, backend='backend4')
        self.hpe_inspect_volume(volume1, size=int(THIN_SIZE),
                                       provisioning='full')

        host_conf1 = self.hpe_create_host_config(volume_driver=HPE3PAR,
                                               binds= volume_name1 + ':/data1')
        try: 
            container_info1 = self.hpe_mount_volume(BUSYBOX, command='sh',
                                   detach=True, tty=True, stdin_open=True,
                             name=container_name1, host_config=host_conf1)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)

        self.client.remove_container(container_name1, force=True)

        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)
        self.hpe_delete_volume(volume1)
        self.hpe_verify_volume_deleted(volume_name1, backend='backend4')
