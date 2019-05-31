import json
import six
from threading import Thread

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
        share_name = self._share_info['name']
        LOG.info("Deleting share %s..." % share_name)
        # Most likely nothing got created at the backend when share is
        # not in AVAILABLE state
        if self._share_info['status'] == 'FAILED':
            LOG.info("Share %s is in FAILED state. Removing from ETCD..."
                     % share_name)
            ret_val, status = self._delete_share_from_etcd(share_name)
            return ret_val

        elif self._share_info['status'] == 'CREATING':
            msg = ("Share %s is in CREATING state. Please wait for it to be "
                   "in AVAILABLE or FAILED state and then attempt remove."
                   % share_name)
            LOG.info(msg)
            return json.dumps({"Err": msg})

        try:
            self._delete_share()
        except exception.ShareBackendException as ex:
            return json.dumps({"Err": ex.msg})

        ret_val, status = self._delete_share_from_etcd(share_name)
        if not status:
            return ret_val

        thread = Thread(target=self._continue_delete_on_thread)
        thread.start()
        return json.dumps({u"Err": ''})

    def _continue_delete_on_thread(self):
        self._delete_file_store()
        with self._fp_etcd.get_fpg_lock(
                self._backend, self._cpg_name, self._fpg_name
        ):
            # If shares are not present on FPG after this delete, then
            # delete the FPG too.
            if not self._mediator.shares_present_on_fpg(self._fpg_name):
                if self._fpg_owned_by_docker():
                    self._delete_fpg()
                    self._update_backend_metadata()

    def unexecute(self):
        pass

    def _update_backend_metadata(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend
                )
                self._release_ip(backend_metadata)
                self._remove_fpg_from_default_fpgs(backend_metadata)
                # Update backend metadata
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)
            except Exception as ex:
                msg = "WARNING: Metadata for backend %s is not " \
                      "present. Exception: %s" % \
                      (self._backend, six.text_type(ex))
                LOG.warning(msg)

    def _fpg_owned_by_docker(self):
        LOG.info("Checking if FPG %s is owned by Docker..." % self._fpg_name)
        try:
            self._fp_etcd.get_fpg_metadata(
                self._backend, self._cpg_name, self._fpg_name)
            LOG.info("FPG %s is owned by Docker!" % self._fpg_name)
            return True
        except exception.EtcdMetadataNotFound:
            LOG.info("FPG %s is NOT owned by Docker!" % self._fpg_name)
            return False

    def _delete_share(self):
        """Deletes share from the backend

        :returns: None

        :raises: :class:`~hpedockerplugin.exception.ShareBackendException

        """
        share_name = self._share_info['name']
        LOG.info("Start delete share %s..." % share_name)
        if self._share_info.get('id'):
            LOG.info("Deleting share %s from backend..." % share_name)
            self._mediator.delete_share(self._share_info['id'])
            LOG.info("Share %s deleted from backend" % share_name)

    def _delete_file_store(self):
        share_name = self._share_info['name']
        try:
            LOG.info("Deleting file store %s from backend..." % share_name)
            self._mediator.delete_file_store(self._fpg_name, share_name)
            LOG.info("File store %s deleted from backend" % share_name)
        except Exception as e:
            msg = 'Failed to remove file store %(share_name)s from backend: ' \
                  '%(e)s' \
                  % ({'share_name': share_name, 'e': six.text_type(e)})
            LOG.error(msg)

    def _delete_share_from_etcd(self, share_name):
        """Deletes share from ETCD. If delete fails, sets the share status
           as FAILED

        :returns: 1. JSON dict with or without error message based on whether
                     operation was successful or not
                  2. Boolean indicating if operation was successful or not

        :raises: None

        """
        try:
            LOG.info("Removing share entry from ETCD: %s..." % share_name)
            self._etcd.delete_share(share_name)
            LOG.info("Removed share entry from ETCD: %s" % share_name)
            return json.dumps({'Err': ''}), True

        except (exception.EtcdMetadataNotFound,
                exception.HPEPluginEtcdException,
                KeyError) as ex:
            msg = "Delete share '%s' from ETCD failed: Reason: %s" \
                  % (share_name, ex.msg)
            LOG.error(msg)
            LOG.info("Setting FAILED state for share %s..." % share_name)
            self._share_info['status'] = 'FAILED'
            self._share_info['detailedStatus'] = msg
            try:
                self._etcd.save_share(self._share_info)
            except exception.HPEPluginSaveFailed as ex:
                msg = "FATAL: Failed while saving share '%s' in FAILED " \
                      "state to ETCD. Check if ETCD is running." % share_name
                LOG.error(msg)
                return json.dumps({'Err': msg}), False

    def _delete_fpg(self):
        LOG.info("Deleting FPG %s from backend..." % self._fpg_name)
        self._mediator.delete_fpg(self._fpg_name)
        self._delete_fpg_from_etcd()

    def _delete_fpg_from_etcd(self):
        LOG.info("Deleting FOG %s/%s/%s from ETCD..." %
                 (self._backend, self._cpg_name, self._fpg_name))
        self._fp_etcd.delete_fpg_metadata(
            self._backend, self._cpg_name, self._fpg_name
        )

    def _release_ip(self, backend_metadata):
        vfs_ip = self._share_info.get('vfsIPs')[0]
        ip_to_release = vfs_ip[0]
        LOG.info("Releasing IP %s to IP Pool..." % ip_to_release)

        # Release IP to server IP pool
        ips_in_use = backend_metadata['ips_in_use']

        # 'vfsIPs': [(IP1, Subnet1), (IP2, Subnet2)...],
        ips_in_use.remove(ip_to_release)

    def _remove_fpg_from_default_fpgs(self, backend_metadata):
        # Remove FPG from default FPG list
        default_fpgs = backend_metadata.get('default_fpgs')
        if default_fpgs:
            fpg_list = default_fpgs.get(self._cpg_name)
            if self._fpg_name in fpg_list:
                LOG.info("Removing default FPG entry [cpg:%s,"
                         "fpg:%s..."
                         % (self._cpg_name, self._fpg_name))
                fpg_list.remove(self._fpg_name)

                # If last fpg got removed from the list, remove
                # the CPG entry from default_fpgs
                if not fpg_list:
                    del default_fpgs[self._cpg_name]
