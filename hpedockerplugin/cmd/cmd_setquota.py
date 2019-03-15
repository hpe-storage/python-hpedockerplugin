import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception

LOG = logging.getLogger(__name__)


class SetQuotaCmd(cmd.Cmd):
    def __init__(self, file_mgr, cpg_name, fpg_name, vfs_name,
                 share_name, size):
        self._file_mgr = file_mgr
        self._share_etcd = file_mgr.get_etcd()
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._backend = file_mgr.get_backend()
        self._share_name = share_name
        self._size = size
        self._cpg_name = cpg_name
        self._fpg_name = fpg_name
        self._vfs_name = vfs_name

    def execute(self):
        # import pdb
        # pdb.set_trace()
        try:
            fstore = self._share_name
            result = self._mediator.update_capacity_quotas(
                fstore, self._size, self._fpg_name, self._vfs_name)

            self._update_share_metadata()

            LOG.info("update quota result: %s" % result)

        except exception.ShareBackendException as ex:
            msg = "Set quota failed. Msg: %s" % six.text_type(ex)
            LOG.error(msg)
            raise exception.SetQuotaFailed(reason=msg)

    def unexecute(self):
        pass

    def _update_share_metadata(self):
        pass
