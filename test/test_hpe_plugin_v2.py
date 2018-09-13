import logging
import testtools

import test.createvolume_tester as createvolume_tester
import test.createreplicatedvolume_tester as createrepvolume_tester
import test.clonevolume_tester as clonevolume_tester
import test.createsnapshot_tester as createsnapshot_tester
import test.fake_3par_data as data
import test.getvolume_tester as getvolume_tester
import test.mountvolume_tester as mountvolume_tester
import test.removesnapshot_tester as removesnapshot_tester
import test.removevolume_tester as removevolume_tester
# import revertsnapshot_tester
import test.unmountvolume_tester as unmountvolume_tester

logger = logging.getLogger('hpedockerplugin')
logger.level = logging.DEBUG
fh = logging.FileHandler('./unit_tests_run.log')
fh.setLevel(logging.DEBUG)
fmt = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
fh.setFormatter(fmt)
logger.addHandler(fh)

BKEND_3PAR_PP_REP = '3par_pp_rep'
BKEND_3PAR_AP_SYNC_REP = '3par_ap_sync_rep'
BKEND_3PAR_AP_ASYNC_REP = '3par_ap_async_rep'
BKEND_3PAR_AP_STREAMING_REP = '3par_ap_streaming_rep'


def tc_banner_decorator(func):
    def banner_wrapper(self, *args, **kwargs):
        # logger = logging.getLogger(__name__)
        logger.info('Starting - %s' % func.__name__)
        logger.info('========================================================'
                    '===========')
        func(self, *args, **kwargs)
        logger.info('Finished - %s' % func.__name__)
        logger.info('========================================================'
                    '===========\n\n')
    return banner_wrapper


# TODO: Make this class abstract
# Base test class containing common tests
class HpeDockerUnitTestsBase(object):

    """
    CREATE VOLUME related tests
    """
    @tc_banner_decorator
    def test_create_volume_default(self):
        test = createvolume_tester.TestCreateVolumeDefault()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_volume_with_invalid_name(self):
        test = createvolume_tester.TestCreateVolumeInvalidName()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_thick_volume(self):
        test = createvolume_tester.TestCreateThickVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_dedup_volume(self):
        test = createvolume_tester.TestCreateDedupVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_import_volume(self):
        test = createvolume_tester.TestImportVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_import_volume_with_other_option(self):
        test = createvolume_tester.TestImportVolumeOtherOption()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_volume_with_qos(self):
        test = createvolume_tester.TestCreateVolumeWithQOS()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_volume_with_invalid_qos(self):
        test = createvolume_tester.TestCreateVolumeWithInvalidQOS()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_volume_with_mutually_exclusive_list(self):
        test = createvolume_tester.TestCreateVolumeWithMutuallyExclusiveList()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_volume_with_flashcache_and_qos(self):
        test = createvolume_tester.TestCreateVolumeWithFlashCacheAndQOS()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_volume_with_flashcache(self):
        test = createvolume_tester.TestCreateVolumeWithFlashCache()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_volume_flashcache_addtovvs_fails(self):
        test = createvolume_tester.TestCreateVolumeFlashCacheAddToVVSFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_compressed_volume(self):
        test = createvolume_tester.TestCreateCompressedVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_compressed_volume_Negative_Size(self):
        test = createvolume_tester.TestCreateCompressedVolumeNegativeSize()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_compressed_volume_No_HW_Support(self):
        test = createvolume_tester.TestCreateCompressedVolNoHardwareSupport()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_vol_with_qos_and_flash_cache_etcd_save_fails(self):
        test = createvolume_tester.\
            TestCreateVolWithQosAndFlashCacheEtcdSaveFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_vol_with_flash_cache_etcd_save_fails(self):
        test = createvolume_tester.\
            TestCreateVolWithFlashCacheEtcdSaveFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_vol_set_flash_cache_fails(self):
        test = createvolume_tester.TestCreateVolSetFlashCacheFails()
        test.run_test(self)

    """
    REPLICATION related tests
    """
    @tc_banner_decorator
    def test_create_default_replicated_volume_fails(self):
        test = createrepvolume_tester.TestCreateVolumeDefaultFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_pp_replicated_volume_and_rcg(self):
        test = createrepvolume_tester.TestCreateReplicatedVolumeAndRCG(
            backend_name=BKEND_3PAR_PP_REP)
        test.run_test(self)

    @tc_banner_decorator
    def test_create_ap_sync_replicated_volume_and_rcg(self):
        test = createrepvolume_tester.TestCreateReplicatedVolumeAndRCG(
            backend_name=BKEND_3PAR_AP_SYNC_REP)
        test.run_test(self)

    @tc_banner_decorator
    def test_create_ap_async_replicated_volume_and_rcg(self):
        test = createrepvolume_tester.TestCreateReplicatedVolumeAndRCG(
            backend_name=BKEND_3PAR_AP_ASYNC_REP)
        test.run_test(self)

    @tc_banner_decorator
    def test_create_ap_streaming_replicated_volume_and_rcg(self):
        test = createrepvolume_tester.TestCreateReplicatedVolumeAndRCG(
            backend_name=BKEND_3PAR_AP_STREAMING_REP)
        test.run_test(self)

    @tc_banner_decorator
    def test_create_pp_replicated_volume_and_rcg_create_fails(self):
        test = createrepvolume_tester.\
            TestCreateReplicatedVolumeAndRCGCreateFails(
                backend_name=BKEND_3PAR_PP_REP)
        test.run_test(self)

    @tc_banner_decorator
    def test_create_ap_sync_replicated_volume_and_rcg_create_fails(self):
        test = createrepvolume_tester.\
            TestCreateReplicatedVolumeAndRCGCreateFails(
                backend_name=BKEND_3PAR_AP_SYNC_REP)
        test.run_test(self)

    @tc_banner_decorator
    def test_create_ap_async_replicated_volume_and_rcg_create_fails(self):
        test = createrepvolume_tester.\
            TestCreateReplicatedVolumeAndRCGCreateFails(
                backend_name=BKEND_3PAR_AP_ASYNC_REP)
        test.run_test(self)

    @tc_banner_decorator
    def test_create_ap_streaming_replicated_volume_and_rcg_create_fails(self):
        test = createrepvolume_tester.\
            TestCreateReplicatedVolumeAndRCGCreateFails(
                backend_name=BKEND_3PAR_AP_STREAMING_REP)
        test.run_test(self)

    """
    CLONE VOLUME related tests
    """
    @tc_banner_decorator
    def test_clone_default(self):
        test = clonevolume_tester.TestCloneDefault()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_default_etcd_fails(self):
        test = clonevolume_tester.TestCloneDefaultEtcdSaveFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_offline_copy(self):
        test = clonevolume_tester.TestCloneOfflineCopy()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_offline_copy_fails(self):
        test = clonevolume_tester.TestCloneOfflineCopyFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_invalid_source_volume(self):
        test = clonevolume_tester.TestCloneInvalidSourceVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_with_invalid_size(self):
        test = clonevolume_tester.TestCloneWithInvalidSize()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_dedup_volume(self):
        test = clonevolume_tester.TestCloneDedupVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_with_flashcache(self):
        test = clonevolume_tester.TestCloneWithFlashCache()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_with_qos(self):
        test = clonevolume_tester.TestCloneWithQOS()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_with_flashcache_add_to_vvset_fails(self):
        test = clonevolume_tester.TestCloneWithFlashCacheAddVVSetFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_compressed_volume(self):
        test = clonevolume_tester.TestCloneCompressedVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_set_flashcache_fails(self):
        test = clonevolume_tester.TestCloneSetFlashCacheFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_with_flashcache_etcd_save_fails(self):
        test = clonevolume_tester.TestCloneWithFlashCacheEtcdSaveFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_with_flashcache_and_qos_etcd_save_fails(self):
        test = clonevolume_tester.TestCloneWithFlashCacheAndQOSEtcdSaveFails()
        test.run_test(self)

    """
    CREATE REVERT SNAPSHOT related tests
    """
    # @tc_banner_decorator
    # def test_snap_revert_volume_default(self):
    #     test = revertsnapshot_tester.TestCreateSnapRevertVolume()
    #     test.run_test(self)
    #
    # @tc_banner_decorator
    # def test_snap_revert_nonexist_volume(self):
    #     test = revertsnapshot_tester.TestSnapRevertVolumeNotExist()
    #     test.run_test(self)
    #
    # @tc_banner_decorator
    # def test_snap_revert_nonexist_snap(self):
    #     test = revertsnapshot_tester.TestSnapRevertSnapNotExist()
    #     test.run_test(self)

    """
    CREATE SNAPSHOT related tests
    """
    @tc_banner_decorator
    def test_create_snapshot_default(self):
        test = createsnapshot_tester.TestCreateSnapshotDefault()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snapshot_with_expiry_retention_times(self):
        test = \
            createsnapshot_tester.TestCreateSnapshotWithExpiryRetentionTimes()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snapshot_with_duplicate_name(self):
        test = createsnapshot_tester.TestCreateSnapshotDuplicateName()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snapshot_etcd_save_fails(self):
        test = createsnapshot_tester.TestCreateSnapshotEtcdSaveFails()
        test.run_test(self)

    """
    REMOVE VOLUME related tests
    """
    @tc_banner_decorator
    def test_remove_regular_volume(self):
        rm_regular_vol = removevolume_tester.TestRemoveVolume.Regular()
        test = removevolume_tester.TestRemoveVolume(rm_regular_vol)
        test.run_test(self)

    def test_remove_replicated_volume_role_primary(self):
        params = {'role': data.ROLE_PRIMARY}
        rm_rep_vol = removevolume_tester.TestRemoveVolume.ReplicatedVolume(
            params)
        test = removevolume_tester.TestRemoveVolume(rm_rep_vol)
        test.run_test(self)

    def test_remove_replicated_volume_role_secondary(self):
        params = {'role': data.ROLE_SECONDARY}
        rm_rep_vol = removevolume_tester.TestRemoveVolume.ReplicatedVolume(
            params)
        test = removevolume_tester.TestRemoveVolume(rm_rep_vol)
        test.run_test(self)

    def test_remove_last_replicated_volume(self):
        params = {'role': data.ROLE_PRIMARY, 'rm_last_volume': True}
        rm_rep_vol = removevolume_tester.TestRemoveVolume.ReplicatedVolume(
            params)
        test = removevolume_tester.TestRemoveVolume(rm_rep_vol)
        test.run_test(self)

    def test_remove_non_existent_volume(self):
        test = removevolume_tester.TestRemoveNonExistentVolume()
        test.run_test(self)

    def test_remove_volume_with_child_snapshot(self):
        test = removevolume_tester.TestRemoveVolumeWithChildSnapshot()
        test.run_test(self)

    """
    REMOVE SNAPSHOT related tests
    """
    @tc_banner_decorator
    def test_remove_snapshot(self):
        test = removesnapshot_tester.TestRemoveSnapshot()
        test.run_test(self)

    # @tc_banner_decorator
    # def test_remove_multilevel_snapshot(self):
    #     test = removesnapshot_tester.TestRemoveMultilevelSnapshot()
    #     test.run_test(self)

    # @tc_banner_decorator
    # def test_remove_snapshot_with_child_snapshots(self):
    #     test = removesnapshot_tester.TestRemoveSnapshotWithChildSnapshots()
    #     test.run_test(self)

    @tc_banner_decorator
    def test_remove_non_existing_snapshot(self):
        test = removesnapshot_tester.TestRemoveNonExistentSnapshot()
        test.run_test(self)

    """
    UNMOUNT VOLUME related tests
    """
    @tc_banner_decorator
    def test_unmount_volume_remove_host(self):
        test = unmountvolume_tester.TestUnmountLastVolumeForHost()
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_snap_remove_host(self):
        test = unmountvolume_tester.TestUnmountLastVolumeForHost(is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_volume_keep_host(self):
        test = unmountvolume_tester.TestUnmountOneVolumeForHost()
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_snap_keep_host(self):
        test = unmountvolume_tester.TestUnmountOneVolumeForHost(is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_vol_once_mounted_twice_on_this_node(self):
        test = unmountvolume_tester.TestUnmountVolOnceMountedTwiceOnThisNode()
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_snap_once_mounted_twice_on_this_node(self):
        test = unmountvolume_tester.TestUnmountVolOnceMountedTwiceOnThisNode(
            is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_vol_mounted_twice_on_this_node(self):
        # This is a special test case which makes use of the same tester
        # to execute this TC twice. The idea
        # is to start with a volume which has two mount-ids i.e. it has been
        # mounted twice. This TC tries to unmount it twice and checks if
        # node_mount_info got removed from the volume object
        test = unmountvolume_tester.TestUnmountVolMountedTwiceOnThisNode(
            tc_run_cnt=2)
        # This will not un-mount the volume - just removes one mount-id
        test.run_test(self)
        # This will un-mount the volume as the last mount-id gets removed
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_snap_mounted_twice_on_this_node(self):
        # This is a special test case which makes use of the same tester
        # to execute this TC twice. The idea
        # is to start with a volume which has two mount-ids i.e. it has been
        # mounted twice. This TC tries to unmount it twice and checks if
        # node_mount_info got removed from the volume object
        test = unmountvolume_tester.TestUnmountVolMountedTwiceOnThisNode(
            tc_run_cnt=2, is_snap=True)
        # This will not un-mount the volume - just removes one mount-id
        test.run_test(self)
        # This will un-mount the volume as the last mount-id gets removed
        test.run_test(self)

    """
    INSPECT SNAPSHOT related tests
    """
    @tc_banner_decorator
    def test_sync_snapshots(self):
        test = getvolume_tester.TestSyncSnapshots()
        test.run_test(self)

    @tc_banner_decorator
    def test_qos_vol(self):
        test = getvolume_tester.TestQosVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_vol(self):
        test = getvolume_tester.TestCloneVolume()
        test.run_test(self)


class HpeDockerISCSIUnitTests(HpeDockerUnitTestsBase, testtools.TestCase):
    @property
    def protocol(self):
        return 'ISCSI'

    @tc_banner_decorator
    def test_clone_with_CHAP(self):
        test = clonevolume_tester.TestCloneWithCHAP()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_iscsi_host(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostNoVLUN()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_iscsi_host(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostNoVLUN(is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_existing_nsp(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostVLUNExist()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_existing_nsp(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostVLUNExist(
            is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_chap_on(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostChapOn()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_chap_on(self):
        test = mountvolume_tester.TestMountVolumeISCSIHostChapOn(is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_modify_iscsi_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeModifyISCSIHostVLUNExists()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_modify_iscsi_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeModifyISCSIHostVLUNExists(
            is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_no_iscsi_host_no_vlun(self):
        test = mountvolume_tester.TestMountVolumeNoISCSIHostNoVLUN()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_no_iscsi_host_no_vlun(self):
        test = mountvolume_tester.TestMountVolumeNoISCSIHostNoVLUN(
            is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_vol_fencing_forced_unmount(self):
        test = mountvolume_tester.TestVolFencingForcedUnmount()
        test.run_test(self)

    @tc_banner_decorator
    def test_snap_fencing_forced_unmount(self):
        test = mountvolume_tester.TestVolFencingForcedUnmount(is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_vol_fencing_graceful_unmount(self):
        test = mountvolume_tester.TestVolFencingGracefulUnmount()
        test.run_test(self)

    @tc_banner_decorator
    def test_snap_fencing_graceful_unmount(self):
        test = mountvolume_tester.TestVolFencingGracefulUnmount(is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_vol_fencing_mount_twice_same_node(self):
        test = mountvolume_tester.TestVolFencingMountTwiceSameNode()
        test.run_test(self)

    @tc_banner_decorator
    def test_snap_fencing_mount_twice_same_node(self):
        test = mountvolume_tester.TestVolFencingMountTwiceSameNode(
            is_snap=True)
        test.run_test(self)


class HpeDockerFCUnitTests(HpeDockerUnitTestsBase, testtools.TestCase):
    @property
    def protocol(self):
        return 'FC'

    @tc_banner_decorator
    def test_mount_volume_modify_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeModifyHostVLUNExists()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_modify_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeModifyHostVLUNExists(
            is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_no_fc_host_no_vlun(self):
        test = mountvolume_tester.TestMountVolumeNoFCHostNoVLUN()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_no_fc_host_no_vlun(self):
        test = mountvolume_tester.TestMountVolumeNoFCHostNoVLUN(
            is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_fc_host(self):
        test = mountvolume_tester.TestMountVolumeFCHost()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_fc_host(self):
        test = mountvolume_tester.TestMountVolumeFCHost(is_snap=True)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_fc_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeFCHostVLUNExists()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_fc_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeFCHostVLUNExists(is_snap=True)
        test.run_test(self)
