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
        LOG.info("Delting share %s..." % self._share_info['name'])
        with self._fp_etcd.get_fpg_lock(
                self._backend, self._cpg_name, self._fpg_name):
            self._remove_quota()
            self._delete_share()
            remaining_cnt = self._decrement_share_cnt()
            if remaining_cnt == 0:
                self._delete_fpg()
        return json.dumps({u"Err": ''})

    def _unexecute(self):
        pass

    def _remove_quota(self):
        try:
            share = self._etcd.get_share(self._share_info['name'])
            if 'quota_id' in share:
                quota_id = share.pop('quota_id')
                self._mediator.remove_quota(quota_id)
                self._share_etcd.save_share(share)
        except Exception as ex:
            LOG.error("ERROR: Remove quota failed for %s. %s"
                      % (self._share_name, six.text_type(ex)))

    def _delete_share(self):
        share_name = self._share_info['name']
        LOG.info("cmd_deleteshare:remove_share: Removing %s..." % share_name)
        try:
            self._mediator.delete_share(self._share_info['id'])
            LOG.info("file_manager:remove_share: Removed %s" % share_name)

        except Exception as e:
            msg = 'Failed to remove share %(share_name)s from backend: %(e)s'\
                  % ({'share_name': share_name, 'e': six.text_type(e)})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

        try:
            LOG.info("Removing share entry from ETCD: %s..." % share_name)
            self._etcd.delete_share(share_name)
            LOG.info("Removed share entry from ETCD: %s" % share_name)
        except KeyError:
            msg = 'Warning: Failed to delete share key: %s from ' \
                  'ETCD due to KeyError' % share_name
            LOG.warning(msg)

    def _decrement_share_cnt(self):
        fpg = self._fp_etcd.get_fpg_metadata(self._backend,
                                             self._cpg_name,
                                             self._fpg_name)
        cnt = int(fpg['share_cnt']) - 1
        fpg['share_cnt'] = cnt
        fpg['reached_full_capacity'] = False
        self._fp_etcd.save_fpg_metadata(self._backend,
                                        self._cpg_name,
                                        self._fpg_name,
                                        fpg)
        return cnt

    def _delete_fpg(self):
        self._mediator.delete_fpg(self._fpg_name)
        self._fp_etcd.delete_fpg_metadata(
            self._backend, self._cpg_name, self._fpg_name
        )
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend
                )
            except Exception as ex:
                msg = "WARNING: Metadata for backend %s is not present" %\
                      self._backend
                LOG.warning(msg)
            else:
                # Release IP to server IP pool
                ips_in_use = backend_metadata['ips_in_use']
                # 'vfsIPs': [(IP1, Subnet1), (IP2, Subnet2)...],
                vfs_ip = self._share_info.get('vfsIPs')[0]
                ip_to_release = vfs_ip[0]
                ips_in_use.remove(ip_to_release)

                # Remove FPG from default FPG list
                default_fpgs = backend_metadata.get('default_fpgs')
                if default_fpgs:
                    default_fpg = default_fpgs.get(self._cpg_name)
                    if self._fpg_name == default_fpg:
                        LOG.info("Removing default FPG entry [cpg:%s,"
                                 "fpg:%s..."
                                 % (self._cpg_name, self._fpg_name))
                        del default_fpgs[self._cpg_name]

                # Update backend metadata
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)
