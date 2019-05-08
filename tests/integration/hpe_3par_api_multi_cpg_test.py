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
MULTI_CPG = cfg['backend']['multi_cpg']
HPE3PAR_API_URL = cfg['backend']['3Par_api_url']
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
class MultiCpgTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

    @classmethod
    def setUpClass(cls):

        hpe_3par_cli.login('3paradm', '3pardata')

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

        hpe_3par_cli.logout()

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


    def test_multi_cpg(self):
    
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)

        clone_name = helpers.random_name()
        self.tmp_volumes.append(clone_name)


        container_name= helpers.random_name()
        self.tmp_containers.append(container_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin',cpg=MULTI_CPG)


        self.hpe_verify_volume_created(volume_name,provisioning='thin',size=THIN_SIZE, cpg=MULTI_CPG)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='thin', cpg=MULTI_CPG)

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=int(THIN_SIZE))
        self.hpe_verify_snapshot_created(volume_name, snapshot_name)
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=int(THIN_SIZE),
                                provisioning='thin')
        self.hpe_verify_volume_created(clone_name, size=THIN_SIZE,
                                       provisioning='thin', clone=True)
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

    def test_multi_snapcpg(self):
        
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)

        clone_name = helpers.random_name()
        self.tmp_volumes.append(clone_name)


        container_name= helpers.random_name()
        self.tmp_containers.append(container_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin',snapcpg=MULTI_CPG)


        self.hpe_verify_volume_created(volume_name,provisioning='thin',size=THIN_SIZE, snapcpg=MULTI_CPG)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='thin', snapcpg=MULTI_CPG)

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=int(THIN_SIZE), snapcpg=MULTI_CPG)
        self.hpe_verify_snapshot_created(volume_name, snapshot_name, snapcpg=MULTI_CPG)
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=int(THIN_SIZE),
                                provisioning='thin', snapcpg=MULTI_CPG)
        self.hpe_verify_volume_created(clone_name, size=THIN_SIZE,
                                       provisioning='thin', clone=True, snapcpg=MULTI_CPG)
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

    def test_multi_cpg_snapcpg(self):
        
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)

        clone_name = helpers.random_name()
        self.tmp_volumes.append(clone_name)

        container_name= helpers.random_name()
        self.tmp_containers.append(container_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin',cpg=MULTI_CPG, snapcpg=MULTI_CPG)


        self.hpe_verify_volume_created(volume_name,provisioning='thin',size=THIN_SIZE, cpg=MULTI_CPG, snapcpg=MULTI_CPG)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='thin', cpg=MULTI_CPG, snapcpg=MULTI_CPG)

        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=int(THIN_SIZE), snapcpg=MULTI_CPG)
        self.hpe_verify_snapshot_created(volume_name, snapshot_name, snapcpg=MULTI_CPG)
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=int(THIN_SIZE),
                                provisioning='thin', snapcpg=MULTI_CPG)
        self.hpe_verify_volume_created(clone_name, size=THIN_SIZE,
                                       provisioning='thin', clone=True, snapcpg=MULTI_CPG)
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

    def test_multi_cpg_with_cloneof_option(self):

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        clone_name = helpers.random_name()
        self.tmp_volumes.append(clone_name)

        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')

        self.hpe_verify_volume_created(volume_name,provisioning='thin',size=THIN_SIZE)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='thin')

        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name, cpg=MULTI_CPG)

        self.hpe_inspect_volume(clone, size=int(THIN_SIZE),
                                provisioning='thin', cpg=MULTI_CPG)
        self.hpe_verify_volume_created(clone_name, size=THIN_SIZE,
                                       provisioning='thin', clone=True, cpg=MULTI_CPG)
        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=clone_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=clone_name, size=int(THIN_SIZE))
        self.hpe_verify_snapshot_created(clone_name, snapshot_name)
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)


        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)


    def test_multi_cpg_with_virtualcopyof_option(self):

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)

        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)

        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=THIN_SIZE, provisioning='thin')

        self.hpe_verify_volume_created(volume_name,provisioning='thin',size=THIN_SIZE)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='thin')
        try:
            snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                                virtualCopyOf=volume_name, cpg=MULTI_CPG)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)

        try:
            snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                                virtualCopyOf=volume_name, snapcpg=MULTI_CPG)
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)


    def test_multi_cpg_with_vvset_and_qos(self):

        vvset_name = "multicpg_vvset_1"
        qosRules = {'priority': 2,'ioMinGoal': 300, 'ioMaxLimit': 1000}
        try:
            print("Create vvset {}".format(vvset_name))
            hpe_3par_cli.createVolumeSet(vvset_name, domain=DOMAIN)
            hpe_3par_cli.createQoSRules("multicpg_vvset_1", qosRules)
        except Exception as e:
            print("Unable to create vvset {}: {}".format(vvset_name, e))

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                cpg=MULTI_CPG, qos_name=vvset_name)
        self.hpe_verify_volume_created(volume_name,provisioning='thin',cpg=MULTI_CPG,qos='true', vvs_name=vvset_name)
        self.hpe_inspect_volume(volume, provisioning='thin', cpg=MULTI_CPG, enabled=True,
                                maxIOPS='1000 IOs/sec', minIOPS='300 IOs/sec', priority='Normal',vvset_name=vvset_name)

        hpe_3par_cli.deleteVolumeSet(vvset_name)

    def test_multi_cpg_with_flashcache_option(self):

        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                cpg=MULTI_CPG, flash_cache='true' )
        self.hpe_verify_volume_created(volume_name,provisioning='thin',cpg=MULTI_CPG, flash_cache='true')
        self.hpe_inspect_volume(volume, provisioning='thin', cpg=MULTI_CPG, flash_cache='true')

