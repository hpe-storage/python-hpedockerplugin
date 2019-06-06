import docker
import yaml
import os
from .base import TEST_API_VERSION, BUSYBOX
from . import helpers
from .helpers import requires_api_version
from .hpe_3par_manager import HPE3ParBackendVerification, HPE3ParVolumePluginTest
from hpe3parclient.client import HPE3ParClient


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
HPE3PAR_API_URL = cfg['backend']['3Par_api_url']
HPE3PAR_IP = cfg['backend']['3Par_IP']

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

@requires_api_version('1.21')
class ScheduleTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

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
        try:
            hpe_3par_cli.setSSHOptions(HPE3PAR_IP, '3paradm', '3pardata')
            hpe_3par_cli.deleteSchedule("dailyOnceSchedule")
        except:
            pass
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



    def test_create_schedule(self):
        '''
           This is a create schedule positive testcase with all required parameters passed.

           Steps:
           1. Create a source volume with provisioning='thin'.
           2. Create a snapshot for the above created source volume, also passing schedule parameters
           3. Verify if source volume and its properties are present in 3PAR array.
           4. Verify if snapshot volume and its schedule properties are present in the 3PAR array.
           5. Inspect this source volume.
           6. Delete this snapshot volume.
           7. Verify if snapshot volume is removed from 3PAR array.
           8. Verify if source volume is removed from 3PAR array.
        '''
        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()
        schedule_name = "dailyOnceSchedule" 
        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                       size=THIN_SIZE, provisioning='thin')

        snapshot = self.hpe_create_volume(snapshot_name, driver=HPE3PAR, 
				       virtualCopyOf=volume['Name'], scheduleFrequency="10 2 * * *", scheduleName="dailyOnceSchedule", snapshotPrefix="pqr",expHrs="5", retHrs="3")

        self.hpe_verify_volume_created(volume_name, driver=HPE3PAR, size=THIN_SIZE, provisioning='thin')
        self.hpe_verify_snapshot_created(volume_name, snapshot_name)


        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='thin',snapshot_name=snapshot['Options']['virtualCopyOf'])

        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume['Name'], size=THIN_SIZE)


        self.hpe_verify_snapshot_schedule(schedule_name, snapshot) 

        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_create_schedule_without_mandatory_schedule_parameters(self):

        '''
           This is a create schedule negative testcase with all required parameters passed.

           Steps:
           1. Create a source volume with provisioning='thin'.
           2. Create a snapshot for the above created source volume, withput passing mandatory 'scheduleFrequency' parameter.
           3. Verify resp of exception and assert.
           4. Verify if snapshot volume is not present on 3PAR array.
           5. Delete created source volume.
           6. Verify the sourve volume is deleted.
        '''
        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()

        self.tmp_volumes.append(volume_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, size=THIN_SIZE, provisioning='thin')
        try:
            snapshot = self.hpe_create_volume(snapshot_name, driver=HPE3PAR, virtualCopyOf=volume['Name'], scheduleName="dailyOnceSchedule", snapshotPrefix="pqr")

        except Exception as ex:
            resp = str(ex)
            self.assertIn("Invalid input received:", resp)
        self.hpe_volume_not_created(snapshot_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)


    def test_create_schedule_with_nonexistent_source_vol(self):


        '''
           This is a create schedule negative testcase with all required parameters passed.

           Steps:
           1. Create a snapshot passing source volume that does not exist.
           2. Verify response of exception and assert.
           3. Verify if snapshot volume is not present on 3PAR array.
           4. Verify the source volume is not present on the 3PAR array.
        '''

        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()

        try:
            snapshot = self.hpe_create_volume(snapshot_name, driver=HPE3PAR, virtualCopyOf=volume_name ,scheduleFrequency="10 2 * * *", scheduleName="dailyOnceSchedule", snapshotPrefix="pqr")

        except Exception as ex:
            resp = str(ex)
            self.assertIn("source volume: " '{}' " does not exist".format(volume_name), resp)

        self.hpe_volume_not_created(volume_name)
        self.hpe_volume_not_created(snapshot_name)
