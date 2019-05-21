import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception

LOG = logging.getLogger(__name__)


class GenerateFpgVfsNamesCmd(cmd.Cmd):
    def __init__(self, backend, cpg, fp_etcd):
        self._backend = backend
        self._cpg_name = cpg
        self._fp_etcd = fp_etcd

    def execute(self):
        return self._generate_default_fpg_vfs_names()

    def _generate_default_fpg_vfs_names(self):
        LOG.info("Cmd: Generating default FPG and VFS names...")
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend)
                counter = int(backend_metadata.get('counter', 0)) + 1
                backend_metadata['counter'] = counter
                new_fpg_name = "DockerFpg_%s" % counter
                new_vfs_name = "DockerVfs_%s" % counter

                # Save updated backend_metadata
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)
                return new_fpg_name, new_vfs_name
            except exception.EtcdMetadataNotFound:
                new_fpg_name = "DockerFpg_0"
                new_vfs_name = "DockerVfs_0"

                # Default FPG must be created at the backend first and then
                # only, default_fpgs can be updated in ETCD
                backend_metadata = {
                    'ips_in_use': [],
                    'ips_locked_for_use': [],
                    'counter': 0
                }
                LOG.info("Backend metadata entry for backend %s not found."
                         "Creating %s..." %
                         (self._backend, six.text_type(backend_metadata)))
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)
                LOG.info("Cmd: Returning FPG %s and VFS %s" %
                         (new_fpg_name, new_vfs_name))
                return new_fpg_name, new_vfs_name

    def unexecute(self):
        # May not require implementation
        pass
