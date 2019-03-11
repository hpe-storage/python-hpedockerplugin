import threading
import hpedockerplugin.volume_manager as mgr
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BackendInitializerThread(threading.Thread):
    def __init__(self, manager_objs,
                 host_config,
                 config,
                 etcd_util,
                 backend_name):
        threading.Thread.__init__(self)
        self.manager_objs = manager_objs
        self.backend_name = backend_name
        self.host_config = host_config
        self.config = config
        self.etcd_util = etcd_util

    def run(self):
        LOG.info("Starting initializing backend " + self.backend_name)
        # First initialize the manager_objs key with state as
        # INITIALIZING
        volume_mgr = {}
        volume_mgr['backend_state'] = 'INITIALIZING'
        volume_mgr['mgr'] = None

        self.manager_objs[self.backend_name] = volume_mgr

        try:
            volume_mgr_obj = mgr.VolumeManager(
                self.host_config,
                self.config,
                self.etcd_util,
                self.backend_name)
            volume_mgr['mgr'] = volume_mgr_obj
            volume_mgr['backend_state'] = 'OK'

        except Exception as ex:
            volume_mgr['mgr'] = None
            volume_mgr['backend_state'] = 'FAILED'
            LOG.error('INITIALIZING backend: %s FAILED Error: %s'
                      % (self.backend_name, ex))
        finally:
            LOG.info('in finally : %s , %s ' % (self.backend_name, volume_mgr))
            self.manager_objs[self.backend_name] = volume_mgr
