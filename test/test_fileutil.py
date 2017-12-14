from hpedockerplugin import fileutil
import mock
from testtools import TestCase
import time

class TestFileSystemCreationFailureWithRetry(TestCase):
    def test_retry_on_create_filesystem(self):
        start_time = time.time()
        with mock.patch.object(fileutil, 'mkfs') as mock_mkfs:
            mock_mkfs.side_effect = \
                [Exception("ex1"),
                 Exception("ex2"),
                 Exception("ex3")]
        try:
            fileutil.create_filesystem("/dev/sde")
        except Exception as ex:
            print ex.message
        finally:
            end_time = time.time()
            print 'Duration : %d ' % (end_time - start_time)
            self.assertTrue((end_time - start_time) >= 40)
