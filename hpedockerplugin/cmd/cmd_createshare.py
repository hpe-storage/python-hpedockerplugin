import six

from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin.cmd.cmd_claimavailableip import ClaimAvailableIPCmd
from hpedockerplugin.cmd.cmd_createfpg import CreateFpgCmd
from hpedockerplugin.cmd.cmd_createvfs import CreateVfsCmd

from hpedockerplugin import exception
from hpedockerplugin.hpe import share

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
        self._share_cnt_incremented = False

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
        if self._share_cnt_incremented:
            fpg_metadata = self._fp_etcd.get_fpg_metadata(
                self._backend,
                self._share_args['cpg'],
                self._share_args['fpg']
            )
            cnt = int(fpg_metadata['share_cnt']) - 1
            fpg_metadata['share_cnt'] = cnt
            fpg_metadata['reached_full_capacity'] = False
            self._fp_etcd.save_fpg_metadata(self._backend,
                                            self._share_args['cpg'],
                                            self._share_args['fpg'],
                                            fpg_metadata)

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
            # Increment count only if it is Docker managed FPG
            if self._share_args.get('docker_managed'):
                self._increment_share_cnt_for_fpg()
        except Exception as ex:
            msg = "Share creation failed [share_name: %s, error: %s" %\
                  (share_name, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareCreationFailed(msg)

    # FPG lock is already acquired in this flow
    def _increment_share_cnt_for_fpg(self):
        cpg_name = self._share_args['cpg']
        fpg_name = self._share_args['fpg']
        LOG.info("Incrementing share count for FPG %s..." % fpg_name)
        fpg = self._fp_etcd.get_fpg_metadata(self._backend,
                                             cpg_name,
                                             fpg_name)
        cnt = fpg.get('share_cnt', 0) + 1
        fpg['share_cnt'] = cnt
        LOG.info("Checking if count reached full capacity...")
        if cnt >= share.MAX_SHARES_PER_FPG:
            LOG.info("Full capacity on FPG %s reached" % fpg_name)
            fpg['reached_full_capacity'] = True
        LOG.info("Saving modified share count %s to ETCD for FPG %s"
                 % (cnt, fpg_name))
        self._fp_etcd.save_fpg_metadata(self._backend, cpg_name,
                                        fpg_name, fpg)
        self._share_cnt_incremented = True
