import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception


LOG = logging.getLogger(__name__)
FPG_SIZE = 64


class CreateFpgCmd(cmd.Cmd):
    def __init__(self, file_mgr, cpg_name, fpg_name, set_default_fpg=False):
        self._file_mgr = file_mgr
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._backend = file_mgr.get_backend()
        self._cpg_name = cpg_name
        self._fpg_name = fpg_name
        self._set_default_fpg = set_default_fpg

    def execute(self):
        with self._fp_etcd.get_fpg_lock(self._backend, self._cpg_name,
                                        self._fpg_name):
            LOG.info("Creating FPG %s on the backend using CPG %s" %
                     (self._fpg_name, self._cpg_name))
            try:
                self._mediator.create_fpg(self._cpg_name, self._fpg_name)
                if self._set_default_fpg:
                    self._old_fpg_name = self._set_as_default_fpg()

                fpg_metadata = {
                    'fpg': self._fpg_name,
                    'fpg_size': FPG_SIZE,
                    'reached_full_capacity': False
                }
                self._fp_etcd.save_fpg_metadata(self._backend,
                                                self._cpg_name,
                                                self._fpg_name,
                                                fpg_metadata)

            except (exception.ShareBackendException,
                    exception.EtcdMetadataNotFound) as ex:
                msg = "Create new FPG %s failed. Msg: %s" \
                      % (self._fpg_name, six.text_type(ex))
                LOG.error(msg)
                raise exception.FpgCreationFailed(reason=msg)

    def unexecute(self):
        if self._set_default_fpg:
            self._unset_as_default_fpg()

    def _set_as_default_fpg(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend)
                default_fpgs = backend_metadata['default_fpgs']
                default_fpgs.update({self._cpg_name: self._fpg_name})

                # Save updated backend_metadata
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)
            except exception.EtcdMetadataNotFound as ex:
                LOG.error("ERROR: Failed to set default FPG for backend %s"
                          % self._backend)
                raise ex

    def _unset_as_default_fpg(self):
        pass
        # TODO:
        # self._cpg_name,
        # self._fpg_name,
        # self._old_fpg_name
