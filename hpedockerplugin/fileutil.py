# (c) Copyright [2016] Hewlett Packard Enterprise Development LP
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from sh import blkid
from sh import mkfs
from sh import mkdir
from sh import mount
from sh import umount
import subprocess
from sh import rm
from oslo_log import log as logging
from hpedockerplugin.i18n import _, _LI
import hpedockerplugin.exception as exception
import six

from twisted.python.filepath import FilePath
from retrying import retry

LOG = logging.getLogger(__name__)

prefix = "/opt/hpe/data/hpedocker-"


def has_filesystem(path):
    try:
        if blkid("-p", "-u", "filesystem", path) == '':
            return False
    except Exception as ex:
        msg = (_LI('exception is : %s'), six.text_type(ex))
        LOG.info(msg)
        if ex.stdout == '':
            return False
    return True


def retry_if_io_error(exception1):
    LOG.info("Retry attempted on mkfs due to exception")
    return isinstance(exception1, exception.HPEPluginFileSystemException)


@retry(retry_on_exception=retry_if_io_error,
       stop_max_attempt_number=3,
       wait_fixed=20000)
def create_filesystem(path):
    try:
        # Create filesystem without user intervention, -F
        # NEED to be extra careful here!!!!
        # mkfs("-t", "ext4", "-F", path)
        # The containerized version of the plugin runs on Alpine
        # and there is no default mkfs. Therefore, we link
        # mkfs to mkfs.ext4 in our Dockerfile, so no need to
        # specify -t ext4.
        mkfs("-F", path)
    except Exception as ex:
        msg = (_('create file system failed exception is : %s'),
               six.text_type(ex))
        LOG.error(msg)
        raise exception.HPEPluginFileSystemException(reason=msg)
    return True


def mkdir_for_mounting(path, mount_prefix):
    try:
        data = path.split("/")
        # TODO: Investigate what triggers OS Brick to return a
        # /dev/mapper vs. /dev/disk/by-path path
        if 'mapper' in data:
            uuid = data[3]
        else:
            uuid = data[4]

        if mount_prefix:
            global prefix
            prefix = mount_prefix

        LOG.info('MOUNT PREFIX : %s' % prefix)

        directory = prefix + uuid
        mkdir("-p", directory)
    except Exception as ex:
        msg = (_('Make directory failed exception is : %s'), six.text_type(ex))
        LOG.error(msg)
        raise exception.HPEPluginMakeDirException(reason=msg)
    return directory


def mount_dir(src, tgt):
    try:
        mount("-t", "ext4", src, tgt)
    except Exception as ex:
        msg = (_('exception is : %s'), six.text_type(ex))
        LOG.error(msg)
        raise exception.HPEPluginMountException(reason=msg)
    return True


def umount_dir(tgt):
    # For some reason sh.mountpoint does not work, so
    # using subprocess instead.
    result = subprocess.Popen(["mountpoint", "-q", tgt])

    # we must explictly wait for the process to finish.
    # Otherwise, we do not get the correct result
    result.wait()
    if result.returncode == 0:
        try:
            umount("-l", tgt)
        except Exception as ex:
            msg = (_('exception is : %s'), six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginUMountException(reason=msg)
    return True


def remove_dir(tgt):
    path = FilePath(tgt)
    if path.exists:
        try:
            rm("-rf", tgt)
        except Exception as ex:
            msg = (_('exception is : %s'), six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginRemoveDirException(reason=msg)
    return True


def remove_file(tgt):
    path = FilePath(tgt)
    if path.exists:
        try:
            rm(tgt)
        except Exception as ex:
            msg = (_('exception is : %s'), six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginRemoveDirException(reason=msg)
    return True
