from hpedockerplugin import fileutil
import mock
from testtools import TestCase


class TestFileSystemCreationFailureWithRetry(TestCase):
    def test_retry_on_create_filesystem():
        with mock.patch.object(fileutil, 'mkfs') as mock_mkfs:
            mock_mkfs.side_effect = \
                [Exception("ex1"),
                 Exception("ex2"),
                 Exception("ex3")]
        try:
            fileutil.create_filesystem("/dev/sde")
        except Exception as ex:
            super.assertEqual(len(mock_mkfs.mock_calls),
                              len(mock_mkfs.side_effect))
            print ex.message
