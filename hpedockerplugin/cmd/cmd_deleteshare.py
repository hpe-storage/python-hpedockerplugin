import json
import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception

LOG = logging.getLogger(__name__)


class DeleteShareCmd(cmd.Cmd):
    def __init__(self, file_mgr, share_info):
        self._file_mgr = file_mgr
        self._etcd = file_mgr.get_etcd()
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._backend = file_mgr.get_backend()
        self._share_info = share_info
        self._cpg_name = share_info['cpg']
        self._fpg_name = share_info['fpg']

    def execute(self):
        with self._fp_etcd.get_fpg_lock(self._backend,
                                        self._fpg_name) as lock:
            self._delete_share()
            self._update_share_cnt()
        return json.dumps({u"Err": ''})

    def _unexecute(self):
        if self._set_default_fpg:
            self._unset_as_default_fpg()

    def _delete_share(self):
        share_name = self._share_info['name']
        LOG.info("cmd_deleteshare:remove_share: Removing %s..." % share_name)
        try:
            self._mediator.delete_share(self._share_info)
            LOG.info("file_manager:remove_share: Removed %s" % share_name)

        except Exception as e:
            msg = 'Failed to remove share %(share_name)s from backend: %(e)s'\
                  % ({'share_name': share_name, 'e': six.text_type(e)})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

        try:
            LOG.info("Removing share entry from ETCD: %s..." % share_name)
            self._etcd.delete_share(self._share_info)
            LOG.info("Removed share entry from ETCD: %s" % share_name)
        except KeyError:
            msg = 'Warning: Failed to delete share key: %s from ' \
                  'ETCD due to KeyError' % share_name
            LOG.warning(msg)

    def _update_share_cnt(self):
        fpg = self._fp_etcd.get_fpg_metadata(self._backend,
                                             self._cpg_name,
                                             self._fpg_name)
        fpg['share_cnt'] = fpg['share_cnt'] - 1
        fpg['reached_full_capacity'] = False
        self._fp_etcd.save_fpg_metadata(self._backend,
                                        self._cpg_name,
                                        self._fpg_name,
                                        fpg)
