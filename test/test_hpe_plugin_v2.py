import testtools
import createvolume_tester
import clonevolume_tester
import createsnapshot_tester
import getvolume_tester
import mountvolume_tester
import removesnapshot_tester
import revertsnapshot_tester
import unmountvolume_tester


# TODO: Make this class abstract
# Base test class containing common tests
class HpeDockerUnitTestsBase(object):

    """
    CREATE VOLUME related tests
    """
    def test_create_volume_default(self):
        test = createvolume_tester.TestCreateVolumeDefault()
        test.run_test(self)

    def test_create_thick_volume(self):
        test = createvolume_tester.TestCreateThickVolume()
        test.run_test(self)

    def test_create_dedup_volume(self):
        test = createvolume_tester.TestCreateDedupVolume()
        test.run_test(self)

    def test_create_volume_with_qos(self):
        test = createvolume_tester.TestCreateVolumeWithQOS()
        test.run_test(self)

    def test_create_volume_with_invalid_qos(self):
        test = createvolume_tester.TestCreateVolumeWithInvalidQOS()
        test.run_test(self)

    def test_create_volume_with_mutually_exclusive_list(self):
        test = createvolume_tester.TestCreateVolumeWithMutuallyExclusiveList()
        test.run_test(self)

    def test_create_volume_with_flashcache_and_qos(self):
        test = createvolume_tester.TestCreateVolumeWithFlashCacheAndQOS()
        test.run_test(self)

    def test_create_volume_with_flashcache(self):
        test = createvolume_tester.TestCreateVolumeWithFlashCache()
        test.run_test(self)

    def test_create_volume_flashcache_addtovvs_fails(self):
        test = createvolume_tester.TestCreateVolumeFlashCacheAddToVVSFails()
        test.run_test(self)

    def test_create_compressed_volume(self):
        test = createvolume_tester.TestCreateCompressedVolume()
        test.run_test(self)

    def test_create_compressed_volume_Negative_Size(self):
        test = createvolume_tester.TestCreateCompressedVolumeNegativeSize()
        test.run_test(self)

    def test_create_compressed_volume_No_HW_Support(self):
        test = createvolume_tester.TestCreateCompressedVolNoHardwareSupport()
        test.run_test(self)

    def test_create_vol_with_qos_and_flash_cache_etcd_save_fails(self):
        test = createvolume_tester.\
            TestCreateVolWithQosAndFlashCacheEtcdSaveFails()
        test.run_test(self)

    def test_create_vol_with_flash_cache_etcd_save_fails(self):
        test = createvolume_tester.\
            TestCreateVolWithFlashCacheEtcdSaveFails()
        test.run_test(self)

    def test_create_vol_set_flash_cache_fails(self):
        test = createvolume_tester.TestCreateVolSetFlashCacheFails()
        test.run_test(self)

    """
    CLONE VOLUME related tests
    """
    def test_clone_default(self):
        test = clonevolume_tester.TestCloneDefault()
        test.run_test(self)

    def test_clone_default_etcd_fails(self):
        test = clonevolume_tester.TestCloneDefaultEtcdSaveFails()
        test.run_test(self)

    def test_clone_offline_copy(self):
        test = clonevolume_tester.TestCloneOfflineCopy()
        test.run_test(self)

    def test_clone_offline_copy_fails(self):
        test = clonevolume_tester.TestCloneOfflineCopyFails()
        test.run_test(self)

    def test_clone_invalid_source_volume(self):
        test = clonevolume_tester.TestCloneInvalidSourceVolume()
        test.run_test(self)

    def test_clone_with_invalid_size(self):
        test = clonevolume_tester.TestCloneWithInvalidSize()
        test.run_test(self)

    def test_clone_dedup_volume(self):
        test = clonevolume_tester.TestCloneDedupVolume()
        test.run_test(self)

    def test_clone_with_flashcache(self):
        test = clonevolume_tester.TestCloneWithFlashCache()
        test.run_test(self)

    def test_clone_with_qos(self):
        test = clonevolume_tester.TestCloneWithQOS()
        test.run_test(self)

    def test_clone_with_flashcache_add_to_vvset_fails(self):
        test = clonevolume_tester.TestCloneWithFlashCacheAddVVSetFails()
        test.run_test(self)

    def test_clone_compressed_volume(self):
        test = clonevolume_tester.TestCloneCompressedVolume()
        test.run_test(self)

    """
    CREATE REVERT SNAPSHOT related tests
    """
    def test_snap_revert_volume_default(self):
        test = revertsnapshot_tester.TestCreateSnapRevertVolume()
        test.run_test(self)

    def test_snap_revert_nonexist_volume(self):
        test = revertsnapshot_tester.TestSnapRevertVolumeNotExist()
        test.run_test(self)

    def test_snap_revert_nonexist_snap(self):
        test = revertsnapshot_tester.TestSnapRevertSnapNotExist()
        test.run_test(self)

    """
    CREATE SNAPSHOT related tests
    """
    def test_create_snapshot_default(self):
        test = createsnapshot_tester.TestCreateSnapshotDefault()
        test.run_test(self)

    def test_create_snapshot_with_expiry_retention_times(self):
        test = \
            createsnapshot_tester.TestCreateSnapshotWithExpiryRetentionTimes()
        test.run_test(self)

    def test_create_snapshot_with_duplicate_name(self):
        test = createsnapshot_tester.TestCreateSnapshotDuplicateName()
        test.run_test(self)

    """
    REMOVE VOLUME related tests
    """
    def test_remove_snapshot(self):
        test = removesnapshot_tester.TestRemoveSnapshot()
        test.run_test(self)

    def test_remove_multilevel_snapshot(self):
        test = removesnapshot_tester.TestRemoveMultilevelSnapshot()
        test.run_test(self)

    def test_remove_snapshot_with_child_snapshots(self):
        test = removesnapshot_tester.TestRemoveSnapshotWithChildSnapshots()
        test.run_test(self)

    def test_remove_non_existing_snapshot(self):
        test = removesnapshot_tester.TestRemoveNonExistentSnapshot()
        test.run_test(self)

    """
    UNMOUNT VOLUME related tests
    """
    def test_unmount_volume_remove_host(self):
        test = unmountvolume_tester.TestUnmountLastVolumeForHost()
        test.run_test(self)

    def test_unmount_volume_keep_host(self):
        test = unmountvolume_tester.TestUnmountOneVolumeForHost()
        test.run_test(self)

    """
    INSPECT SNAPSHOT related tests
    """
    def test_sync_snapshots(self):
        test = getvolume_tester.TestSyncSnapshots()
        test.run_test(self)

    def test_qos_vol(self):
        test = getvolume_tester.TestQosVolume()
        test.run_test(self)

    def test_clone_vol(self):
        test = getvolume_tester.TestCloneVolume()
        test.run_test(self)


class HpeDockerISCSIUnitTests(HpeDockerUnitTestsBase, testtools.TestCase):
    @property
    def protocol(self):
        return 'ISCSI'

    def test_clone_with_CHAP(self):
        test = clonevolume_tester.TestCloneWithCHAP()
        test.run_test(self)

    def test_mount_volume_iscsi_host(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostNoVLUN()
        test.run_test(self)

    def test_mount_volume_existing_nsp(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostVLUNExist()
        test.run_test(self)

    def test_mount_volume_chap_on(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostChapOn()
        test.run_test(self)

    def test_mount_volume_modify_iscsi_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeModifyISCSIHostVLUNExists()
        test.run_test(self)

    def test_mount_volume_no_iscsi_host_no_vlun(self):
        test = mountvolume_tester.TestMountVolumeNoISCSIHostNoVLUN()
        test.run_test(self)


class HpeDockerFCUnitTests(HpeDockerUnitTestsBase, testtools.TestCase):
    @property
    def protocol(self):
        return 'FC'

    def test_mount_volume_modify_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeModifyHostVLUNExists()
        test.run_test(self)

    def test_mount_volume_no_fc_host_no_vlun(self):
        test = mountvolume_tester.TestMountVolumeNoFCHostNoVLUN()
        test.run_test(self)

    def test_mount_volume_fc_host(self):
        test = mountvolume_tester.TestMountVolumeFCHost()
        test.run_test(self)

    def test_mount_volume_fc_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeFCHostVLUNExists()
        test.run_test(self)
