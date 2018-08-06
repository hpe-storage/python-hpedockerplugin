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

This class will be top-level orchestrator for invoking volume operations
like create, list, mount, unmount, remove operations on different backends.

"backend" here refers to grouping of details for particular 3PAR array

Eg.

[3par1]


"""
from oslo_log import log as logging
import hpedockerplugin.volume_manager as mgr
from config import setupcfg

LOG = logging.getLogger(__name__)

CONFIG_FILE = '/etc/hpedockerplugin/hpe.conf'
CONFIG = ['--config-file', CONFIG_FILE]
DEFAULT_BACKEND_NAME = "DEFAULT"


class Orchestrator(object):
    def __init__(self, hpedefaultconfig):
        self.default_config = hpedefaultconfig
        LOG.info('calling initialize manager objs')
        self._manager = self.initialize_manager_objects(
            self.default_config)

    def initialize_manager_objects(self, defaultconfig):
        manager_objs = {}

        for backend_name in setupcfg.get_all_backends(CONFIG):
            LOG.info('INITIALIZING backend  : %s' % backend_name)
            manager_objs[backend_name] = mgr.VolumeManager(
                setupcfg.backend_config(CONFIG, backend_name),
                defaultconfig)

        return manager_objs

    def get_volume_backend_details(self, volname):
        LOG.info('Getting details for volume : %s ' % (volname))
        etcd_util = mgr.VolumeManager._get_etcd_util(self.default_config)
        vol = etcd_util.get_vol_byname(volname)

        current_backend = DEFAULT_BACKEND_NAME
        if vol is not None and 'backend' in vol:
            current_backend = vol['backend']

        return current_backend

    def volumedriver_remove(self, volname):
        backend = self.get_volume_backend_details(volname)
        return self._manager[backend].remove_volume(volname)

    def volumedriver_unmount(self, volname, vol_mount, mount_id):
        backend = self.get_volume_backend_details(volname)
        return self._manager[backend].unmount_volume(volname,
                                                     vol_mount,
                                                     mount_id)

    def volumedriver_create(self, volname, vol_size,
                            vol_prov, vol_flash,
                            compression_val, vol_qos,
                            mount_conflict_delay, current_backend,
                            rcg_name):

        return self._manager[current_backend].create_volume(
            volname,
            vol_size,
            vol_prov,
            vol_flash,
            compression_val,
            vol_qos,
            mount_conflict_delay,
            current_backend,
            rcg_name)

    def clone_volume(self, src_vol_name, clone_name, size):
        backend = self.get_volume_backend_details(src_vol_name)
        return self._manager[backend].clone_volume(src_vol_name, clone_name,
                                                   size)

    def create_snapshot(self, src_vol_name, schedName, snapshot_name,
                        snapPrefix, expiration_hrs, exphrs, retention_hrs,
                        rethrs, mount_conflict_delay, has_schedule,
                        schedFrequency):
        backend = self.get_volume_backend_details(src_vol_name)
        return self._manager[backend].create_snapshot(src_vol_name,
                                                      schedName,
                                                      snapshot_name,
                                                      snapPrefix,
                                                      expiration_hrs,
                                                      exphrs,
                                                      retention_hrs,
                                                      rethrs,
                                                      mount_conflict_delay,
                                                      has_schedule,
                                                      schedFrequency, backend)

    def mount_volume(self, volname, vol_mount, mount_id):
        backend = self.get_volume_backend_details(volname)
        return self._manager[backend].mount_volume(volname,
                                                   vol_mount, mount_id)

    def get_path(self, volname):
        backend = self.get_volume_backend_details(volname)
        return self._manager[backend].get_path(volname)

    def get_volume_snap_details(self, volname, snapname, qualified_name):
        backend = self.get_volume_backend_details(volname)
        return self._manager[backend].get_volume_snap_details(volname,
                                                              snapname,
                                                              qualified_name)

    def manage_existing(self, volname, existing_ref):
        backend = self.get_volume_backend_details(volname)
        return self._manager[backend].manage_existing(volname, existing_ref)

    def volumedriver_list(self):
        return self._manager[DEFAULT_BACKEND_NAME].list_volumes()
