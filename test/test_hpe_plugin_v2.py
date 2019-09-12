import logging
import testtools

from config import setupcfg
from hpedockerplugin.hpe import hpe3par_opts as plugin_opts

import test.createshare_tester as createshare_tester
import test.createvolume_tester as createvolume_tester
import test.createreplicatedvolume_tester as createrepvolume_tester
import test.clonevolume_tester as clonevolume_tester
import test.createsnapshot_tester as createsnapshot_tester
import test.deleteshare_tester as deleteshare_tester
import test.fake_3par_data as data
import test.getvolume_tester as getvolume_tester
import test.listvolume_tester as listvolume_tester
import test.mountshare_tester as mountshare_tester
import test.mountvolume_tester as mountvolume_tester
import test.removesnapshot_tester as removesnapshot_tester
import test.removevolume_tester as removevolume_tester

# import revertsnapshot_tester
import test.unmountshare_tester as unmountshare_tester
import test.unmountvolume_tester as unmountvolume_tester

logger = logging.getLogger('hpedockerplugin')
logger.level = logging.DEBUG
fh = logging.FileHandler('./unit_tests_run.log')
fh.setLevel(logging.DEBUG)
# fmt = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
formatter = logging.Formatter('%(asctime)-12s [%(levelname)s] '
                              '%(name)s [%(thread)d] '
                              '%(threadName)s %(message)s')
fh.setFormatter(formatter)
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
    def _get_real_config_file(self):
        return '/etc/hpedockerplugin/hpe.conf'

    def _get_test_config_file(self):
        cfg_file_name = './test/config/hpe_%s.conf' % \
                        self.protocol.lower()
        return cfg_file_name

    def _get_configs(self, cfg_param):
        host_config = setupcfg.get_host_config(
            cfg_param, setupcfg.CONF)
        host_config.set_override('ssh_hosts_key_file',
                                 data.KNOWN_HOSTS_FILE)
        backend_configs = setupcfg.get_all_backend_configs(
            cfg_param, setupcfg.CONF, plugin_opts.hpe3par_opts)
        return {'block': (host_config, backend_configs)}

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
    def test_import_already_managed_volume(self):
        test = createvolume_tester.TestImportAlreadyManagedVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_import_volume_with_different_domain(self):
        test = createvolume_tester.TestImportVolumeDifferentDomain()
        test.run_test(self)

    @tc_banner_decorator
    def test_import_volume_with_invalid_options(self):
        test = createvolume_tester.TestImportVolumeWithInvalidOptions()
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

    @tc_banner_decorator
    def test_create_vol_with_mutually_exclusive_opts(self):
        test = createvolume_tester.\
            TestCreateVolumeWithMutuallyExclusiveOptions()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_vol_with_invalid_options(self):
        test = createvolume_tester.TestCreateVolumeWithInvalidOptions()
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

    @tc_banner_decorator
    def test_create_replicated_vol_with_invalid_opts(self):
        test = createrepvolume_tester.\
            TestCreateReplicatedVolumeWithInvalidOptions()
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
    def test_clone_from_base_volume_active_task(self):
        test = clonevolume_tester.TestCloneFromBaseVolumeActiveTask()
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

    @tc_banner_decorator
    def test_clone_volume_with_invalid_options(self):
        test = clonevolume_tester.TestCloneVolumeWithInvalidOptions()
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

    @tc_banner_decorator
    def test_create_snapshot_invalid_options(self):
        test = createsnapshot_tester.TestCreateSnapshotInvalidOptions()
        test.run_test(self)

    """
    CREATE SNAPSHOT SCHEDULE related tests
    """
    @tc_banner_decorator
    def test_create_snap_schedule(self):
        test = createsnapshot_tester.TestCreateSnpSchedule()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snap_schedule_neg_freq(self):
        test = createsnapshot_tester.TestCreateSnpSchedNegFreq()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snap_schedule_neg_prefx(self):
        test = createsnapshot_tester.TestCreateSnpSchedNegPrefx()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snap_schedule_inv_prefx_len(self):
        test = createsnapshot_tester.TestCreateSnpSchedInvPrefxLen()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snap_schedule_no_schedname(self):
        test = createsnapshot_tester.TestCreateSnpSchedNoSchedName()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snap_schedule_with_ret_to_base(self):
        test = createsnapshot_tester.TestCreateSnpSchedwithRetToBase()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snap_schedule_ret_exp_neg(self):
        test = createsnapshot_tester.TestCreateSnpSchedRetExpNeg()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_snap_schedule_inv_sched_freq(self):
        test = createsnapshot_tester.TestCreateSnpSchedInvSchedFreq()
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

    @tc_banner_decorator
    def test_remove_snapshot_schedule(self):
        test = removesnapshot_tester.TestRemoveSnapshotSchedule()
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

    @tc_banner_decorator
    def test_unmount_vol_not_owned_by_this_node(self):
        # This is a special test case which makes use of the same tester
        # to execute this TC twice. The idea
        # is to start with a volume which has two mount-ids i.e. it has been
        # mounted twice. This TC tries to unmount it twice and checks if
        # node_mount_info got removed from the volume object
        test = unmountvolume_tester.TestUnmountVolNotOwnedByThisNode()
        test.run_test(self)

    """
    INSPECT VOLUME/SNAPSHOT related tests
    """
    @tc_banner_decorator
    def test_sync_snapshots(self):
        test = getvolume_tester.TestSyncSnapshots()
        test.run_test(self)

    @tc_banner_decorator
    def test_qos_vol(self):
        test = getvolume_tester.TestGetVolumeWithQos()
        test.run_test(self)

    @tc_banner_decorator
    def test_clone_vol(self):
        test = getvolume_tester.TestCloneVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_get_vol_with_get_qos_fails(self):
        test = getvolume_tester.TestGetVolumeWithGetQoSFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_get_rcg_vol(self):
        test = getvolume_tester.TestGetRcgVolume()
        test.run_test(self)

    @tc_banner_decorator
    def test_get_rcg_vol_fails(self):
        test = getvolume_tester.TestGetRcgVolumeFails()
        test.run_test(self)

    """
    LIST VOLUMES related tests
    """
    @tc_banner_decorator
    def test_list_volumes(self):
        test = listvolume_tester.TestListVolumeDefault()
        test.run_test(self)

    @tc_banner_decorator
    def test_list_no_volumes(self):
        test = listvolume_tester.TestListNoVolumes()
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
    def test_mount_ap_replicated_volume_fc_host_rcg_normal(self):
        vol_params = {'vol_type': 'replicated',
                      'rep_type': 'active-passive',
                      'rcg_state': 'normal'}
        test = mountvolume_tester.TestMountVolumeFCHost(vol_params=vol_params)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_ap_replicated_volume_fc_host_rcg_failover(self):
        vol_params = {'vol_type': 'replicated',
                      'rep_type': 'active-passive',
                      'rcg_state': 'failover'}
        test = mountvolume_tester.TestMountVolumeFCHost(vol_params=vol_params)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_ap_replicated_volume_fc_host_rcg_recover(self):
        vol_params = {'vol_type': 'replicated',
                      'rep_type': 'active-passive',
                      'rcg_state': 'recover'}
        test = mountvolume_tester.TestMountVolumeFCHost(vol_params=vol_params)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_ap_replicated_volume_fc_host_rcgs_ungettable(self):
        vol_params = {'vol_type': 'replicated',
                      'rep_type': 'active-passive',
                      'rcg_state': 'rcgs_not_gettable'}
        test = mountvolume_tester.TestMountVolumeFCHost(vol_params=vol_params)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_ap_replicated_volume_fc_host_pri_rcg_gettable(self):
        vol_params = {'vol_type': 'replicated',
                      'rep_type': 'active-passive',
                      'rcg_state': 'only_primary_rcg_gettable'}
        test = mountvolume_tester.TestMountVolumeFCHost(vol_params=vol_params)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_ap_replicated_volume_fc_host_sec_rcg_gettable(self):
        vol_params = {'vol_type': 'replicated',
                      'rep_type': 'active-passive',
                      'rcg_state': 'only_secondary_rcg_gettable'}
        test = mountvolume_tester.TestMountVolumeFCHost(vol_params=vol_params)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_volume_fc_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeFCHostVLUNExists()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_snap_fc_host_vlun_exists(self):
        test = mountvolume_tester.TestMountVolumeFCHostVLUNExists(is_snap=True)
        test.run_test(self)


# TODO: Unit tests for share need more work
# To be taken up after creating intial PR
class HpeDockerShareUnitTests(testtools.TestCase):
    def _get_real_config_file(self):
        return '/etc/hpedockerplugin/hpe.conf'

    def _get_test_config_file(self):
        cfg_file_name = './test/config/hpe.conf'
        return cfg_file_name

    def _get_configs(self, cfg_param):
        host_config = setupcfg.get_host_config(
            cfg_param, setupcfg.FILE_CONF)
        host_config.set_override('ssh_hosts_key_file',
                                 data.KNOWN_HOSTS_FILE)
        backend_configs = setupcfg.get_all_backend_configs(
            cfg_param, setupcfg.FILE_CONF, plugin_opts.hpe3par_file_opts)
        return {'file': (host_config, backend_configs)}

    @property
    def protocol(self):
        return 'file'

    @tc_banner_decorator
    def test_create_first_default_share(self):
        test = createshare_tester.TestCreateFirstDefaultShare()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_second_default_share(self):
        test = createshare_tester.TestCreateSecondDefaultShare()
        test.run_test(self)

    @tc_banner_decorator
    def test_create_share_on_legacy_fpg(self):
        test = createshare_tester.TestCreateShareOnLegacyFpg()
        test.run_test(self)

    # TODO: TC to be enabled once tester class implementation is done
    @tc_banner_decorator
    def test_create_first_default_share_set_quota_fails(self):
        test = createshare_tester.TestCreateFirstDefaultShareSetQuotaFails()
        test.run_test(self)

    @tc_banner_decorator
    def test_remove_regular_share(self):
        del_regular_share = deleteshare_tester.TestDeleteShare.Regular()
        test = deleteshare_tester.TestDeleteShare(del_regular_share)
        test.run_test(self)

    @tc_banner_decorator
    def test_remove_share_with_acl(self):
        params = {'share_with_acl': True}
        del_regular_share = deleteshare_tester.TestDeleteShare.Regular(params)
        test = deleteshare_tester.TestDeleteShare(del_regular_share)
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_share(self):
        test = mountshare_tester.TestMountNfsShare()
        test.run_test(self)

    @tc_banner_decorator
    def test_mount_share_with_acl(self):
        test = mountshare_tester.TestMountNfsShareWithAcl()
        test.run_test(self)

    @tc_banner_decorator
    def test_unmount_share(self):
        test = unmountshare_tester.TestUnmountNfsShare()
        test.run_test(self)
