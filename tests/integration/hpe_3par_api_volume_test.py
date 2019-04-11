import pytest
import docker
import yaml
import os
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
class VolumesTest(HPE3ParBackendVerification,HPE3ParVolumePluginTest):

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


    def test_thin_prov_volume(self):
        '''
           This is a volume create test with provisioning as 'thin'.

           Steps:
           1. Create a volume with provisioning=thin.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='thin')
        self.hpe_verify_volume_created(name, size=THIN_SIZE,
                                       provisioning='thin')
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                provisioning='thin')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_full_prov_volume(self):
        '''
           This is a volume create test with provisioning as 'full'.

           Steps:
           1. Create a volume with provisioning=full.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR,
                                        size=FULL_SIZE, provisioning='full')
        # Verifying in 3par array
        self.hpe_verify_volume_created(name, size=FULL_SIZE,
                                       provisioning='full')
        self.hpe_inspect_volume(volume, size=int(FULL_SIZE),
                                provisioning='full')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_flash_cache_volume(self):
        '''
           This is a volume create test with adaptive flash-cache policy.

           Steps:
           1. Create a volume with flash-cache=true.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR,
                                        size=THIN_SIZE, flash_cache='true')
        # Verifying in 3par array
        self.hpe_verify_volume_created(name, size=THIN_SIZE,
                                       flash_cache='true')
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                flash_cache='true')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_dedup_prov_volume(self):
        '''
           This is a volume create test with provisioning as 'dedup'.

           Steps:
           1. Create a volume with provisioning=dedup.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR,
                                        size=DEDUP_SIZE, provisioning='dedup')
        # Verifying in 3par array
        self.hpe_verify_volume_created(name, size=DEDUP_SIZE,
                                       provisioning='dedup')
        self.hpe_inspect_volume(volume, size=int(DEDUP_SIZE),
                                provisioning='dedup')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_thin_compressed_volume(self):
        '''
           This is a volume create test with provisioning as 'thin' and compression as 'true'.

           Steps:
           1. Create a volume with provisioning=thin and compression=true.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''

        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR, size=COMPRESS_SIZE,
                                        provisioning='thin', compression='true')
        # Verifying in 3par array
        self.hpe_verify_volume_created(name, size=COMPRESS_SIZE,
                                       provisioning='thin', compression='true')
        self.hpe_inspect_volume(volume, size=int(COMPRESS_SIZE),
                                provisioning='thin', compression='true')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_dedup_compressed_volume(self):
        '''
           This is a volume create test with provisioning as 'dedup' and compression as 'true'.

           Steps:
           1. Create a volume with provisioning=dedup and compression=true.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR, size=COMPRESS_SIZE,
                                        provisioning='dedup', compression='true')
        # Verifying in 3par array
        self.hpe_verify_volume_created(name, size=COMPRESS_SIZE,
                                       provisioning='dedup', compression='true')
        self.hpe_inspect_volume(volume, size=int(COMPRESS_SIZE),
                                provisioning='dedup', compression='true')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_list_volumes_clones(self):
        '''
           This is a volume list test.

           Steps:
           1. Create a volume with different volume properties.
           2. Verify if all volumes are present in docker volume list.
        '''
        volume_names = []
        clone_names = []
        i=0; j=0
        for i in range(3):
            volume_names.append(helpers.random_name())
        for j in range(2):
            clone_names.append(helpers.random_name())
        for name in volume_names:
            self.tmp_volumes.append(name)
        for names in clone_names:
            self.tmp_volumes.append(names)

        volume1 = self.hpe_create_volume(volume_names[0], driver=HPE3PAR)
        volume2 = self.hpe_create_volume(volume_names[1], driver=HPE3PAR,
                                         size=THIN_SIZE, provisioning='thin')
        volume3 = self.hpe_create_volume(volume_names[2], driver=HPE3PAR,
                                         size=THIN_SIZE, flash_cache='true')
        clone1 = self.hpe_create_volume(clone_names[0], driver=HPE3PAR,
                                        cloneOf=volume_names[0])
        clone2 = self.hpe_create_volume(clone_names[1], driver=HPE3PAR,
                                        cloneOf=volume_names[2])

        self.hpe_verify_volume_created(volume_names[0])
        self.hpe_verify_volume_created(volume_names[1],
                                       size=THIN_SIZE, provisioning='thin')
        self.hpe_verify_volume_created(volume_names[2],
                                       size=THIN_SIZE, flash_cache='true')
        self.hpe_verify_volume_created(clone_names[0], size='100',
                                       provisioning='thin', clone=True)
        self.hpe_verify_volume_created(clone_names[1], size=THIN_SIZE,
                                       flash_cache='true', clone=True)

        result = self.client.volumes()
        self.assertIn('Volumes', result)
        volumes = result['Volumes']
        volume = [volume1, volume2, volume3, clone1, clone2]
        for vol in volume:
            self.assertIn(vol, volumes)

    @requires_api_version('1.25')
    def test_force_remove_volumes_clones(self):
        '''
           This is a remove volumes test with force option.

           Steps:
           1. Create a volume with different volume properties.
           2. Verify if all volumes are removed forcefully.
        '''
        volume_names = []
        clone_names = []
        i=0; j=0
        for i in range(3):
            volume_names.append(helpers.random_name())
        for j in range(2):
            clone_names.append(helpers.random_name())
        for name in volume_names:
            self.tmp_volumes.append(name)
        for names in clone_names:
            self.tmp_volumes.append(names)

        volume1 = self.hpe_create_volume(volume_names[0], driver=HPE3PAR)
        volume2 = self.hpe_create_volume(volume_names[1], driver=HPE3PAR,
                                         size=THIN_SIZE, provisioning='thin')
        volume3 = self.hpe_create_volume(volume_names[2], driver=HPE3PAR,
                                         size=THIN_SIZE, flash_cache='true')
        clone1 = self.hpe_create_volume(clone_names[0], driver=HPE3PAR,
                                        cloneOf=volume_names[0])
        clone2 = self.hpe_create_volume(clone_names[1], driver=HPE3PAR,
                                        cloneOf=volume_names[2])

        self.hpe_verify_volume_created(volume_names[0])
        self.hpe_verify_volume_created(volume_names[1],
                                       size=THIN_SIZE, provisioning='thin')
        self.hpe_verify_volume_created(volume_names[2],
                                       size=THIN_SIZE, flash_cache='true')
        self.hpe_verify_volume_created(clone_names[0], size='100',
                                       provisioning='thin', clone=True)
        self.hpe_verify_volume_created(clone_names[1], size=THIN_SIZE,
                                       flash_cache='true', clone=True)
        volumes = [volume1, volume2, volume3, clone1, clone2]
        for volume in volumes:
            self.hpe_delete_volume(volume, force=True)
            self.hpe_verify_volume_deleted(volume['Name'])

    def test_clone_without_options(self):
        '''
        This is a clone volume test without options.

        Steps:
        1. Create a volume without volume properties.
        2. Create a clone of this volume.
        3. Inspect the cloned volume.
        4. Verify the clone in 3par array.
        5. Delete the clone and volume both.
        6. Verify the removal of volumes in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR)
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone)
        self.hpe_verify_volume_created(clone_name, size='100',
                                       provisioning='thin', clone=True)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_full_prov_clone(self):
        '''
        This is a clone volume test with source volume provisioning as full.

        Steps:
        1. Create a volume with volume provisioning as full.
        2. Create a clone of this volume.
        3. Inspect the cloned volume.
        4. Verify the clone in 3par array.
        5. Delete the clone and volume both.
        6. Verify the removal of volumes in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size='10', provisioning='full')
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       size='20', cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=20,
                                provisioning='full')
        self.hpe_verify_volume_created(clone_name, size='20',
                                       provisioning='full', clone=True)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_dedup_prov_clone(self):
        '''
         This is a clone volume test with source volume provisioning as dedup.

         Steps:
         1. Create a volume with volume provisioning as dedup.
         2. Create a clone of this volume.
         3. Inspect the cloned volume.
         4. Verify the clone in 3par array.
         5. Delete the clone and volume both.
         6. Verify the removal of volumes in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=DEDUP_SIZE, provisioning='dedup')
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=int(DEDUP_SIZE),
                                provisioning='dedup')
        self.hpe_verify_volume_created(clone_name, size=DEDUP_SIZE,
                                       provisioning='dedup', clone=True)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_flash_cache_clone(self):
        '''
         This is a clone volume test with source volume flash-cache as true.

         Steps:
         1. Create a volume with volume flash-cache as true.
         2. Create a clone of this volume.
         3. Inspect the cloned volume.
         4. Verify the clone in 3par array.
         5. Delete the clone and volume both.
         6. Verify the removal of volumes in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, flash_cache='true')
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=int(THIN_SIZE),
                                flash_cache='true')
        self.hpe_verify_volume_created(clone_name, size=THIN_SIZE,
                                       flash_cache='true', clone=True)
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_thin_compressed_clone(self):
        '''
         This is a clone volume test with source volume compression as true.

         Steps:
         1. Create a volume with volume compression as true.
         2. Create a clone of this volume.
         3. Inspect the cloned volume.
         4. Verify the clone in 3par array.
         5. Delete the clone and volume both.
         6. Verify the removal of volumes in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=COMPRESS_SIZE, compression='true')
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=int(COMPRESS_SIZE),
                                compression='true')
        self.hpe_verify_volume_created(clone_name, size=COMPRESS_SIZE, clone=True,
                                       provisioning='thin', compression='true')
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_dedup_compressed_clone(self):
        '''
         This is a clone volume test with source volume provisioning as dedup and compression as true.

         Steps:
         1. Create a volume with volume provisioning=dedup and compression=true.
         2. Create a clone of this volume.
         3. Inspect the cloned volume.
         4. Verify the clone in 3par array.
         5. Delete the clone and volume both.
         6. Verify the removal of volumes in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, size=COMPRESS_SIZE,
                                        provisioning='dedup', compression='true')
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(clone, size=int(COMPRESS_SIZE),
                                compression='true', provisioning='dedup')
        self.hpe_verify_volume_created(clone_name, size=COMPRESS_SIZE, clone=True,
                                       provisioning='dedup', compression='true')
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_volume_snapshot(self):
        '''
         This is a snapshot test.

         Steps:
         1. Create a volume.
         2. Create a snapshot of this volume.
         3. Inspect the snapshot.
         4. Verify the snapshot in 3par array.
         5. Delete the snapshot and volume both.
         6. Verify the removal of volume and snapshot in 3par array.
        '''
        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(snapshot_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='thin')
        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                            virtualCopyOf=volume_name)
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=THIN_SIZE)
        self.hpe_verify_snapshot_created(volume_name, snapshot_name)
        self.hpe_delete_snapshot(volume_name, snapshot_name)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)

    def test_snapshot_expiration_retention(self):
        '''
         This is a snapshot test with expiration and retention end period.

         Steps:
         1. Create a volume.
         2. Create a snapshot of this volume with expiration and retention end period.
         3. Inspect the snapshot.
         4. Verify the snapshot in 3par array.
         5. Delete the snapshot.
         6. Verify the presence of snapshot in 3par array.
        '''
        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=FULL_SIZE, provisioning='full')
        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                 virtualCopyOf=volume_name, expirationHours='10',
                                 retentionHours='5')
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=FULL_SIZE,
                                  expirationHours='10', retentionHours='5')
        self.hpe_verify_snapshot_created(volume_name, snapshot_name, expirationHours='10',
                                         retentionHours='5')
        self.hpe_delete_snapshot(volume_name, snapshot_name, retention=True)
        self.hpe_verify_snapshot_created(volume_name, snapshot_name, expirationHours='10',
                                         retentionHours='5')

    def test_remove_snapshot_within_retention(self):
        '''
         This is a snapshot test with retention end period.

         Steps:
         1. Create a volume.
         2. Create a snapshot of this volume with retention end period.
         3. Inspect the snapshot.
         4. Verify the snapshot in 3par array.
         5. Delete the snapshot.
         6. Verify the presence of snapshot in 3par array.
        '''
        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, flash_cache='true')
        snapshot = self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                 virtualCopyOf=volume_name, retentionHours='1')
        self.hpe_inspect_snapshot(snapshot, snapshot_name=snapshot_name,
                                  virtualCopyOf=volume_name, size=THIN_SIZE,
                                  retentionHours='1')
        self.hpe_delete_snapshot(volume_name, snapshot_name, retention=True)
        inspect_volume_snapshot = self.client.inspect_volume(volume_name)
        snapshots = inspect_volume_snapshot['Status']['Snapshots']
        snapshot_list = []
        i = 0
        for i in range(len(snapshots)):
            snapshot_list.append(snapshots[i]['Name'])
        self.assertIn(snapshot_name, snapshot_list)

        inspect_snapshot = self.client.inspect_volume(snapshot_name)
        self.assertEqual(inspect_snapshot['Status']['snap_detail']['retention_hours'], 1)
        self.hpe_verify_snapshot_created(volume_name, snapshot_name,
                                         retentionHours='1')

    def test_snapshot_retention_greater_than_expiration(self):
        '''
         This is a snapshot test with retention end period greater than expiration period.

         Steps:
         1. Create a volume.
         2. Create a snapshot of this volume with retention end period greater than expiration period.
         3. Verify the error.
         4. Verify the absence of snapshot in 3par array.
        '''
        volume_name = helpers.random_name()
        snapshot_name = helpers.random_name()
        self.tmp_volumes.append(snapshot_name)
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size=THIN_SIZE, provisioning='thin')
        try:
            self.hpe_create_snapshot(snapshot_name, driver=HPE3PAR,
                                     virtualCopyOf=volume_name, expirationHours='4',
                                     retentionHours='5')
        except docker.errors.APIError as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        inspect_volume_snapshot = self.client.inspect_volume(volume_name)
        if 'Snapshots' not in inspect_volume_snapshot['Status']:
            pass
        else:
            snapshots = inspect_volume_snapshot['Status']['Snapshots']
            snapshot_list = []
            i = 0
            for i in range(len(snapshots)):
                snapshot_list.append(snapshots[i]['Name'])
            self.assertNotIn(snapshot_name, snapshot_list)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_name)

    def test_snapshots_list(self):
        '''
         This is a snapshot list test.

         Steps:
         1. Create a volume.
         2. Create a few snapshots of this volume with expiration and retention end period.
         3. Inspect the snapshot.
         4. Verify the snapshot in 3par array.
         5. Delete all snapshots.
         6. Verify the presence/absence of snapshot in 3par array.
        '''
        volume_name = helpers.random_name()
        snapshot_names = []
        i = 0; j = 0
        for i in range(3):
            snapshot_names.append(helpers.random_name())
            self.tmp_volumes.append(snapshot_names[i])
        self.tmp_volumes.append(volume_name)
        self.hpe_create_volume(volume_name, driver=HPE3PAR,
                               size=COMPRESS_SIZE, provisioning='dedup',
                               compression='true')
        snapshot1 = self.hpe_create_snapshot(snapshot_names[0], driver=HPE3PAR,
                                             virtualCopyOf=volume_name)
        snapshot2 = self.hpe_create_snapshot(snapshot_names[1], driver=HPE3PAR,
                                             virtualCopyOf=volume_name, expirationHours='2')
        snapshot3 = self.hpe_create_snapshot(snapshot_names[2], driver=HPE3PAR,
                                             virtualCopyOf=volume_name, expirationHours='6',
                                             retentionHours='3')
        self.hpe_inspect_snapshot(snapshot1, snapshot_name=snapshot_names[0],
                                  virtualCopyOf=volume_name, size=COMPRESS_SIZE)
        self.hpe_inspect_snapshot(snapshot2, snapshot_name=snapshot_names[1],
                                  virtualCopyOf=volume_name, size=COMPRESS_SIZE,
                                  expirationHours='2')
        self.hpe_inspect_snapshot(snapshot3, snapshot_name=snapshot_names[2],
                                  virtualCopyOf=volume_name, size=COMPRESS_SIZE,
                                  expirationHours='6', retentionHours='3')
        self.hpe_verify_snapshot_created(volume_name, snapshot_names[0])
        self.hpe_verify_snapshot_created(volume_name, snapshot_names[1], expirationHours='2')
        self.hpe_verify_snapshot_created(volume_name, snapshot_names[2], expirationHours='6',
                                         retentionHours='3')
        inspect_volume_snapshot = self.client.inspect_volume(volume_name)
        snapshots = inspect_volume_snapshot['Status']['Snapshots']
        snapshot_list = []
        for j in range(len(snapshots)):
            snapshot_list.append(snapshots[j]['Name'])
        for snapshot in snapshot_names:
            self.assertIn(snapshot, snapshot_list)
        self.hpe_delete_snapshot(volume_name, snapshot_names[0])
        self.hpe_delete_snapshot(volume_name, snapshot_names[1])
        self.hpe_delete_snapshot(volume_name, snapshot_names[2], retention=True)
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_names[0])
        self.hpe_verify_snapshot_deleted(volume_name, snapshot_names[1])
        self.hpe_verify_snapshot_created(volume_name, snapshot_names[2], retentionHours='3')

    def test_thin_compressed_volume_15GB(self):
        '''
           This is a volume create test with provisioning as 'thin' and compression enabled.

           Steps:
           1. Create a volume with provisioning=thin size=15 GB.
           2. Verify the volume is not created with 'docker volume ls'
           3. Verify the volume is not created from 3Par side.
        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size='15', provisioning='thin', compression='true')
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

    def test_full_prov_compressed_volume(self):
        '''
           This is a volume create test with provisioning as 'full' and compression enabled.

           Steps:
           1. Create a volume with provisioning=full size=16 GB.
           2. Verify the volume is not created with 'docker volume ls'
           3. Verify the volume is not created from 3Par side.
        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            volume = self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size='16', provisioning='full', compression='true')
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

    def test_dedup_compressed_volume_15GB(self):
        '''
           This is a volume create test with provisioning as 'dedup' and compression enabled.

           Steps:
           1. Create a volume with provisioning=dedup size=15 GB.
           2. Verify the volume is not created with 'docker volume ls'
           3. Verify the volume is not created from 3Par side.
        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        try:
            self.hpe_create_volume(volume_name, driver=HPE3PAR,
                                        size='15', provisioning='dedup', compression='true')
        except Exception as ex:
            resp = ex.status_code
            self.assertEqual(resp, 500)
        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

    def test_thin_prov_compressed_flashcache_volume(self):
        '''
           This is a volume create test with provisioning as 'thin' and compression & flashcache enabled.

           Steps:
           1. Create a volume with provisioning=thin size=17 GB compression and flashcache enabled.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR, size=COMPRESS_SIZE,
                                        provisioning='thin', compression='true', flash_cache='true')
        # Verifying in 3par array
        self.hpe_verify_volume_created(name, size=COMPRESS_SIZE,
                                       provisioning='thin', compression='true', flash_cache='true')
        self.hpe_inspect_volume(volume, size=int(COMPRESS_SIZE),
                                provisioning='thin', compression='true', flash_cache='true')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_dedup_prov_compressed_flashcache_volume(self):
        '''
           This is a volume create test with provisioning as 'thin' and compression & flashcache enabled.

           Steps:
           1. Create a volume with provisioning=dedup size=17 GB compression and flashcache enabled.
           2. Verify if volume and its properties are present in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR, size=COMPRESS_SIZE,
                                        provisioning='dedup', compression='true', flash_cache='true')
        # Verifying in 3par array
        self.hpe_verify_volume_created(name, size=COMPRESS_SIZE,
                                       provisioning='dedup', compression='true', flash_cache='true')
        self.hpe_inspect_volume(volume, size=int(COMPRESS_SIZE),
                                provisioning='dedup', compression='true', flash_cache='true')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)

    def test_volume_existent_qos(self):
        '''
           This is a volume create test with qosName as pre-created VVSet name.

           Steps:
           1. Create VVset and configure QoS rule in 3par array.
           2. Create a volume with qosName.
           2. Verify if volume is a member of vvset in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from vvset and deleted from 3Par array.
        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        vvset_name = helpers.random_name()
        self.hpe_create_verify_vvs_with_qos(vvs_name=vvset_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, qos_name=vvset_name)
        self.hpe_verify_volume_created(volume_name, vvset_name)
        self.hpe_inspect_volume(volume)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)
        self.hpe_remove_vvs_qos(vvs_name=vvset_name)

    def test_volume_non_existent_qos(self):
        '''
           This is a volume create test with qosName as VVSet name which does not exist in 3par array.

           Steps:
           1. Create a volume with qosName.
           2. Error must be displayed.
           3. Verify volume doesn't get created.
        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        vvset_name = helpers.random_name()
        try:
            self.hpe_create_volume(volume_name, driver=HPE3PAR, qos_name=vvset_name)
        except Exception as ex:
            resp = ex.status_code
            self.assertNotEqual(resp, 200)

        self.hpe_volume_not_created(volume_name)
        self.hpe_verify_volume_deleted(volume_name)

    def test_volume_qos_with_flash_cache(self):
        '''
           This is a volume create test with flashcache, qosName as pre-created VVSet name.

           Steps:
           1. Create VVset and configure QoS rule in 3par array.
           2. Create a volume with qosName, flash-cache and other driver options.
           2. Verify if volume is a member of vvset in 3Par array.
           3. Inspect this volume.
           4. Delete this volume.
           5. Verify if volume is removed from vvset and deleted from 3Par array.
        '''
        volume_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        vvset_name = helpers.random_name()
        self.hpe_create_verify_vvs_with_qos(vvs_name=vvset_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, qos_name=vvset_name,
                                        size=FULL_SIZE, flash_cache='true', provisioning='full')
        self.hpe_verify_volume_created(volume_name, vvset_name,
                                       size=FULL_SIZE, provisioning='full', flash_cache='true')
        self.hpe_inspect_volume(volume, size=int(FULL_SIZE),
                                flash_cache='true', provisioning='full')
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)
        self.hpe_remove_vvs_qos(vvs_name=vvset_name)

    def test_clone_qos_name(self):
        '''
         This is a clone volume test with source volume with qos rule.

         Steps:
         1. Create a volume with volume provisioning as dedup, qosName and driver options.
         2. Create a clone of this volume.
         3. Inspect the cloned volume.
         4. Verify the clone in 3par array.
         5. Delete the clone and volume both.
         6. Verify the removal of volumes in 3par array.
        '''
        volume_name = helpers.random_name()
        clone_name = helpers.random_name()
        self.tmp_volumes.append(volume_name)
        self.tmp_volumes.append(clone_name)
        vvset_name = helpers.random_name()
        self.hpe_create_verify_vvs_with_qos(vvs_name=vvset_name)
        volume = self.hpe_create_volume(volume_name, driver=HPE3PAR, qos_name=vvset_name,
                                        size=DEDUP_SIZE, flash_cache='true', provisioning='dedup')
        clone = self.hpe_create_volume(clone_name, driver=HPE3PAR,
                                       cloneOf=volume_name)

        self.hpe_inspect_volume(volume, size=int(DEDUP_SIZE),
                                flash_cache='true', provisioning='dedup')
        self.hpe_inspect_volume(clone, size=int(DEDUP_SIZE),
                                flash_cache='true', provisioning='dedup')
        self.hpe_verify_volume_created(volume_name, vvset_name,
                                       size=DEDUP_SIZE, provisioning='dedup', flash_cache='true')
        self.hpe_verify_volume_created(clone_name, vvset_name, clone=True,
                                       size=DEDUP_SIZE, provisioning='dedup', flash_cache='true')
        self.hpe_delete_volume(clone)
        self.hpe_verify_volume_deleted(clone_name)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(volume_name)
        self.hpe_remove_vvs_qos(vvs_name=vvset_name)

    def test_mountConflictDelay_volume(self):
        '''
               This is a volume create test with provisioning as 'thin'.

               Steps:
               1. Create a volume with mountConflictDelay=60.
               2. Verify if volume and its properties are present in 3Par array.
               3. Inspect this volume.
               4. Delete this volume.
               5. Verify if volume is removed from 3Par array.
        '''
        name = helpers.random_name()
        self.tmp_volumes.append(name)
        volume = self.hpe_create_volume(name, driver=HPE3PAR,
                                        size=THIN_SIZE, mountConflictDelay='60')
        self.hpe_verify_volume_created(name, size=THIN_SIZE)
        self.hpe_inspect_volume(volume, size=int(THIN_SIZE),
                                mountConflictDelay=60)
        self.hpe_delete_volume(volume)
        self.hpe_verify_volume_deleted(name)
