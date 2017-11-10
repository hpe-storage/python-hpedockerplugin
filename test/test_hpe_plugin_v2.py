import testtools
import createvolume_tester
import clonevolume_tester
import createsnapshot_tester
import removesnapshot_tester


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

    def test_create_volume_with_flashcache(self):
        test = createvolume_tester.TestCreateVolumeWithFlashCache()
        test.run_test(self)

    def test_create_volume_flashcache_addtovvs_fails(self):
        test = createvolume_tester.TestCreateVolumeFlashCacheAddToVVSFails()
        test.run_test(self)

    def test_create_compressed_volume(self):
        test = createvolume_tester.TestCreateCompressedVolume()
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

    def test_clone_with_flashcache_add_to_vvset_fails(self):
        test = clonevolume_tester.TestCloneWithFlashCacheAddVVSetFails()
        test.run_test(self)

    def test_clone_with_CHAP(self):
        test = clonevolume_tester.TestCloneWithCHAP()
        test.run_test(self)

    def test_clone_without_CHAP(self):
        test = clonevolume_tester.TestCloneWithoutCHAP()
        test.run_test(self)

    def test_clone_compressed_volume(self):
        test = clonevolume_tester.TestCloneCompressedVolume()
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


class HpeDockerISCSIUnitTests(HpeDockerUnitTestsBase, testtools.TestCase):
    @property
    def protocol(self):
        return 'ISCSI'


class HpeDockerFCUnitTests(HpeDockerUnitTestsBase, testtools.TestCase):
    @property
    def protocol(self):
        return 'FC'
