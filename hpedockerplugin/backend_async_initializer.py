import threading
import hpedockerplugin.volume_manager as mgr
import time
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
        print ("Starting initializing backend " + self.backend_name)
        self.manager_objs[self.backend_name] = mgr.VolumeManager(
            self.host_config,
            self.config,
            self.etcd_util,
            self.backend_name)
        LOG.info("Backend '%s' INITIALIZED!" % self.backend_name)
