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
        self._quota_id = None

    def execute(self):
        # import pdb
        # pdb.set_trace()
        try:
            fstore = self._share_name
            self._quota_id = self._mediator.update_capacity_quotas(
                fstore, self._size, self._fpg_name, self._vfs_name)

            share = self._update_share_metadata(self._quota_id, add=True)

            LOG.info("Updated quota metadata for share: %s" % share)

        except exception.ShareBackendException as ex:
            msg = "Set quota failed. Msg: %s" % six.text_type(ex)
            LOG.error(msg)
            raise exception.SetQuotaFailed(reason=msg)

    def unexecute(self):
        if self._quota_id:
            try:
                self._mediator.remove_quota(self._quota_id)
                self._update_share_metadata(self._quota_id, add=False)
            except Exception:
                LOG.error("ERROR: Undo quota failed for %s" %
                          self._share_name)

    def _update_share_metadata(self, quota_id, add=True):
        share = self._share_etcd.get_share(self._share_name)
        if add:
            share['quota_id'] = quota_id
        elif 'quota_id' in share:
            share.pop('quota_id')
        self._share_etcd.save_share(share)
        return share

# class UnsetQuotaCmd(cmd.Cmd):
#     def __init__(self, file_mgr, share_name):
#         self._file_mgr = file_mgr
#         self._share_etcd = file_mgr.get_etcd()
#         self._mediator = file_mgr.get_mediator()
#         self._share_name = share_name
#
#     def execute(self):
#         try:
#             share = self._share_etcd.get_share(self._share_name)
#             quota_id = share['quota_id']
#             self._mediator.remove_quota(quota_id)
#             self._update_share_metadata(share)
#         except Exception:
#             LOG.error("ERROR: Unset quota failed for %s" %
#                       self._share_name)
#
#     def unexecute(self):
#         pass
#
#     def _update_share_metadata(self, share):
#         if 'quota_id' in share:
#             share.pop('quota_id')
#             self._share_etcd.save_share(share)
