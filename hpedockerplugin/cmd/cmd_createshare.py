import six

from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception

LOG = logging.getLogger(__name__)


class CreateShareCmd(cmd.Cmd):
    def __init__(self, file_mgr, share_args):
        self._file_mgr = file_mgr
        self._etcd = file_mgr.get_etcd()
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._config = file_mgr.get_config()
        self._backend = file_mgr.get_backend()
        self._share_args = share_args
        self._status = 'CREATING'

    def unexecute(self):
        share_name = self._share_args['name']
        LOG.info("cmd::unexecute: Removing share entry from ETCD: %s" %
                 share_name)
        self._etcd.delete_share(share_name)
        if self._status == "AVAILABLE":
            LOG.info("cmd::unexecute: Deleting share from backend: %s" %
                     share_name)
            self._mediator.delete_share(self._share_args['id'])
            self._mediator.delete_file_store(self._share_args['fpg'],
                                             share_name)

    def execute(self):
        share_etcd = self._file_mgr.get_etcd()
        share_name = self._share_args['name']
        try:
            LOG.info("Creating share %s on the backend" % share_name)
            share_id = self._mediator.create_share(self._share_args)
            self._share_args['id'] = share_id
        except Exception as ex:
            msg = "Share creation failed [share_name: %s, error: %s" %\
                  (share_name, six.text_type(ex))
            LOG.error(msg)
            self.unexecute()
            raise exception.ShareCreationFailed(msg)

        try:
            self._status = 'AVAILABLE'
            self._share_args['status'] = self._status
            share_etcd.save_share(self._share_args)
        except Exception as ex:
            msg = "Share creation failed [share_name: %s, error: %s" %\
                  (share_name, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareCreationFailed(msg)
