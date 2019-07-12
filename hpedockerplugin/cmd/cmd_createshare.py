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
        self._share_created_at_backend = False
        self._share_created_in_etcd = False

    def unexecute(self):
        share_name = self._share_args['name']
        LOG.info("cmd::unexecute: Removing share entry from ETCD: %s" %
                 share_name)

        # Leaving the share entry in ETCD intact so that user can inspect
        # the share and look for the reason of failure. Moreover, Docker
        # daemon has the entry for this share as we returned success on the
        # main thread. So it would be better that the user removes this failed
        # share explicitly so that Docker daemon also updates its database
        if self._share_created_at_backend:
            LOG.info("CreateShareCmd:Undo Deleting share from backend: %s"
                     % share_name)
            self._mediator.delete_share(self._share_args['id'])
            LOG.info("CreateShareCmd:Undo Deleting fstore from backend: %s"
                     % share_name)
            self._mediator.delete_file_store(self._share_args['fpg'],
                                             share_name)

    def execute(self):
        share_name = self._share_args['name']
        try:
            LOG.info("Creating share %s on the backend" % share_name)
            share_id = self._mediator.create_share(self._share_args)
            self._share_created_at_backend = True
            self._share_args['id'] = share_id
            self._etcd.save_share(self._share_args)
            self._share_created_in_etcd = True
        except Exception as ex:
            msg = "Share creation failed [share_name: %s, error: %s" %\
                  (share_name, six.text_type(ex))
            LOG.error(msg)
            self.unexecute()
            raise exception.ShareCreationFailed(msg)
