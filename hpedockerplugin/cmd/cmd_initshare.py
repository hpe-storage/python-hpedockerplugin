from oslo_log import log as logging
from hpedockerplugin.cmd import cmd

LOG = logging.getLogger(__name__)


class InitializeShareCmd(cmd.Cmd):
    def __init__(self, backend, share_name, share_etcd):
        self._backend = backend
        self._share_name = share_name
        self._share_etcd = share_etcd

    def execute(self):
        LOG.info("Initializing metadata for share %s..." % self._share_name)
        self._share_etcd.save_share({
            'name': self._share_name,
            'backend': self._backend,
            'status': 'CREATING'
        })
        LOG.info("Metadata initialized for share %s..." % self._share_name)

    def _unexecute(self):
        self._share_etcd.delete_share(self._share_name)
