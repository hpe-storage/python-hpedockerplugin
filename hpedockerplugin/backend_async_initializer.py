# (c) Copyright [2016] Hewlett Packard Enterprise Development LP
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""
Class starts a thread for each backend defined in hpe.conf
for asynchronous initialization and reports the status of
initialization via the manager_objs backed to the caller.

"""

import threading
import hpedockerplugin.volume_manager as mgr
from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class BackendInitializerThread(threading.Thread):
    def __init__(self, manager_objs,
                 host_config,
                 config,
                 etcd_util,
                 node_id,
                 backend_name):
        threading.Thread.__init__(self)
        self.manager_objs = manager_objs
        self.backend_name = backend_name
        self.host_config = host_config
        self.config = config
        self.etcd_util = etcd_util
        self.node_id = node_id

    def run(self):
        LOG.info("Starting initializing backend " + self.backend_name)

        volume_mgr = {}
        try:
            volume_mgr_obj = mgr.VolumeManager(
                self.host_config,
                self.config,
                self.etcd_util,
                self.node_id,
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
