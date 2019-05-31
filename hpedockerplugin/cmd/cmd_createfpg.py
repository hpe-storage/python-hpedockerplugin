import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception


LOG = logging.getLogger(__name__)
FPG_SIZE = 16


class CreateFpgCmd(cmd.Cmd):
    def __init__(self, file_mgr, cpg_name, fpg_name, set_default_fpg=False):
        self._file_mgr = file_mgr
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._backend = file_mgr.get_backend()
        self._cpg_name = cpg_name
        self._fpg_name = fpg_name
        self._set_default_fpg = set_default_fpg
        self._backend_fpg_created = False
        self._default_set = False
        self._fpg_metadata_saved = False

    def execute(self):
        with self._fp_etcd.get_fpg_lock(self._backend, self._cpg_name,
                                        self._fpg_name):
            LOG.info("Creating FPG %s on the backend using CPG %s" %
                     (self._fpg_name, self._cpg_name))
            try:
                config = self._file_mgr.get_config()
                fpg_size = FPG_SIZE
                if config.hpe3par_default_fpg_size:
                    fpg_size = int(config.hpe3par_default_fpg_size)
                    LOG.info("Default FPG size overridden to %s" % fpg_size)

                self._mediator.create_fpg(
                    self._cpg_name,
                    self._fpg_name,
                    fpg_size
                )
                self._backend_fpg_created = True

                if self._set_default_fpg:
                    self._add_to_default_fpg()
                    self._default_set = True

                fpg_metadata = {
                    'fpg': self._fpg_name,
                    'fpg_size': fpg_size,
                }
                self._fp_etcd.save_fpg_metadata(self._backend,
                                                self._cpg_name,
                                                self._fpg_name,
                                                fpg_metadata)
                self._fpg_metadata_saved = True
            except (exception.ShareBackendException,
                    exception.EtcdMetadataNotFound) as ex:
                msg = "Create new FPG %s failed. Msg: %s" \
                      % (self._fpg_name, six.text_type(ex))
                LOG.error(msg)
                raise exception.FpgCreationFailed(reason=msg)

    def unexecute(self):
        if self._backend_fpg_created:
            LOG.info("Deleting FPG %s from backend..." % self._fpg_name)
            try:
                self._mediator.delete_fpg(self._fpg_name)
            except Exception as ex:
                LOG.error("Undo: Failed to delete FPG %s from backend. "
                          "Exception: %s" % (self._fpg_name,
                                             six.text_type(ex)))
        if self._default_set:
            LOG.info("Removing FPG %s as default FPG..." % self._fpg_name)
            try:
                self._remove_as_default_fpg()
            except Exception as ex:
                LOG.error("Undo: Failed to remove as default FPG "
                          "%s. Exception: %s" % (self._fpg_name,
                                                 six.text_type(ex)))

        if self._fpg_metadata_saved:
            LOG.info("Removing metadata for FPG %s..." % self._fpg_name)
            try:
                self._fp_etcd.delete_fpg_metadata(self._backend,
                                                  self._cpg_name,
                                                  self._fpg_name)
            except Exception as ex:
                LOG.error("Undo: Delete FPG metadata failed."
                          "[backend: %s, cpg: %s, fpg: %s]. "
                          "Exception: %s" % (self._backend,
                                             self._cpg_name,
                                             self._fpg_name,
                                             six.text_type(ex)))

    def _add_to_default_fpg(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend)
                default_fpgs = backend_metadata.get('default_fpgs')
                if default_fpgs:
                    fpg_list = default_fpgs.get(self._cpg_name)
                    if fpg_list:
                        fpg_list.append(self._fpg_name)
                    else:
                        default_fpgs[self._cpg_name] = [self._fpg_name]
                else:
                    backend_metadata['default_fpgs'] = {
                        self._cpg_name: [self._fpg_name]
                    }

                # Save updated backend_metadata
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)
            except exception.EtcdMetadataNotFound as ex:
                LOG.error("ERROR: Failed to set default FPG for backend %s"
                          % self._backend)
                raise ex
            except Exception as ex:
                msg = "Failed to update default FPG list with FPG %s. " \
                      "Exception: %s " % (self._fpg_name, six.text_type(ex))
                LOG.error(msg)
                raise exception.HPEPluginEtcdException(reason=msg)

    def _remove_as_default_fpg(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend)
                default_fpgs = backend_metadata['default_fpgs']
                if default_fpgs:
                    fpg_list = default_fpgs.get(self._cpg_name)
                    if fpg_list:
                        fpg_list.remove(self._fpg_name)
                        if not fpg_list:
                            backend_metadata.pop('default_fpgs')

                    # Save updated backend_metadata
                    self._fp_etcd.save_backend_metadata(self._backend,
                                                        backend_metadata)
            except exception.EtcdMetadataNotFound as ex:
                LOG.error("ERROR: Failed to remove default FPG for backend %s"
                          % self._backend)
                raise ex
