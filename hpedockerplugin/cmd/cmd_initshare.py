from oslo_log import log as logging
from hpedockerplugin.cmd import cmd

LOG = logging.getLogger(__name__)


class InitializeShareCmd(cmd.Cmd):
    def __init__(self, backend, share_args, share_etcd):
        self._backend = backend
        self._share_args = share_args
        self._share_etcd = share_etcd

    def execute(self):
        LOG.info("Initializing status for share %s..." %
                 self._share_args['name'])
        self._share_args['status'] = 'CREATING'
        self._share_etcd.save_share(self._share_args)
        LOG.info("Status initialized for share %s" %
                 self._share_args['name'])

    # Using unexecute to mark share as FAILED
    def unexecute(self):
        LOG.info("Marking status of share %s as FAILED..." %
                 self._share_args['name'])
        self._share_args['status'] = 'FAILED'
        self._share_etcd.save_share(self._share_args)
        LOG.info("Marked status of share %s as FAILED" % self._share_name)
