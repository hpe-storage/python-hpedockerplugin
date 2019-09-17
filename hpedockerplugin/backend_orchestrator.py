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
import abc
import json
from oslo_log import log as logging
import os
import six
import uuid
import hpedockerplugin.volume_manager as mgr
import hpedockerplugin.etcdutil as util
import threading
import hpedockerplugin.backend_async_initializer as async_initializer
from twisted.internet import threads

LOG = logging.getLogger(__name__)

DEFAULT_BACKEND_NAME = "DEFAULT"


class Orchestrator(object):
    def __init__(self, host_config, backend_configs, def_backend_name):
        LOG.info('calling initialize manager objs')
        self._def_backend_name = def_backend_name
        self._etcd_client = self._get_etcd_client(host_config)
        self._initialize_orchestrator(host_config)
        self._manager = self.initialize_manager_objects(host_config,
                                                        backend_configs)
        # This is the dictionary which have the volume -> backend map entries
        # cache after doing an etcd volume read operation.
        self.volume_backends_map = {}
        self.volume_backend_lock = threading.Lock()

    @staticmethod
    def _initialize_orchestrator(host_config):
        pass

    def get_default_backend_name(self):
        return self._def_backend_name

    @abc.abstractmethod
    def _get_etcd_client(self, host_config):
        pass

    @staticmethod
    def _get_node_id():
        # Save node-id if it doesn't exist
        node_id_file_path = '/etc/hpedockerplugin/.node_id'
        if not os.path.isfile(node_id_file_path):
            node_id = str(uuid.uuid4())
            with open(node_id_file_path, 'w') as node_id_file:
                node_id_file.write(node_id)
        else:
            with open(node_id_file_path, 'r') as node_id_file:
                node_id = node_id_file.readline()

        return node_id

    def initialize_manager_objects(self, host_config, backend_configs):
        manager_objs = {}
        node_id = self._get_node_id()

        for backend_name, config in backend_configs.items():
            try:
                LOG.info('INITIALIZING backend: %s asynchronously'
                         % backend_name)

                # First initialize the manager_objs key with state as
                # INITIALIZING
                volume_mgr = {}
                volume_mgr['backend_state'] = 'INITIALIZING'
                volume_mgr['mgr'] = None
                manager_objs[backend_name] = volume_mgr

                thread = async_initializer.BackendInitializerThread(
                    self,
                    manager_objs,
                    host_config,
                    config,
                    self._etcd_client,
                    node_id,
                    backend_name
                )
                thread.start()

            except Exception as ex:
                LOG.error('MAIN-THREAD: INITIALIZING backend: %s FAILED '
                          'Error: %s'
                          % (backend_name, six.text_type(ex)))

        LOG.info("Backends INITIALIZED => %s" % manager_objs.keys())

        return manager_objs

    def get_volume_backend_details(self, volname):
        LOG.info('Getting details for volume : %s ' % (volname))

        if volname in self.volume_backends_map:
            current_backend = self.volume_backends_map[volname]
            LOG.debug(' Returning the backend details from cache %s , %s'
                      % (volname, current_backend))
            return current_backend
        else:
            return self.add_cache_entry(volname)

    def add_cache_entry(self, volname):
        # Using this style of locking
        # https://docs.python.org/3/library/threading.html
        self.volume_backend_lock.acquire()
        try:
            vol = self.get_meta_data_by_name(volname)
            if vol is not None and 'backend' in vol:
                current_backend = vol['backend']
                # populate the volume backend map for caching
                LOG.debug(' Populating cache %s, %s '
                          % (volname, current_backend))
                self.volume_backends_map[volname] = current_backend
                return current_backend
            else:
                # throw an exception for the condition
                # where the backend can't be read from volume
                # metadata in etcd
                LOG.info(' vol obj read from etcd : %s' % vol)
                return self._def_backend_name
        finally:
            self.volume_backend_lock.release()

    def _execute_request_for_backend(self, backend_name, request, volname,
                                     *args, **kwargs):
        LOG.info(' Operating on backend : %s on volume %s '
                 % (backend_name, volname))
        LOG.info(' Request %s ' % request)
        LOG.info(' with  args %s ' % str(args))
        LOG.info(' with  kwargs is %s ' % str(kwargs))
        volume_mgr_info = self._manager.get(backend_name)
        if volume_mgr_info:
            volume_mgr = volume_mgr_info['mgr']
            if volume_mgr is not None:
                # populate the volume backend map for caching
                return getattr(volume_mgr, request)(volname, *args, **kwargs)
        msg = "ERROR: Backend '%s' was NOT initialized successfully." \
              " Please check hpe.conf for incorrect entries and rectify " \
              "it." % backend_name
        LOG.error(msg)
        return json.dumps({u'Err': msg})

    def __undeferred_execute_request__(self, request, volname,
                                       *args, **kwargs):
        backend = self.get_volume_backend_details(volname)
        return self._execute_request_for_backend(
            backend,
            request,
            volname,
            *args,
            **kwargs
        )

    def _execute_request(self, request, volname, *args, **kwargs):
        backend = self.get_volume_backend_details(volname)
        d = threads.deferToThread(self._execute_request_for_backend,
                                  backend,
                                  request,
                                  volname,
                                  *args,
                                  **kwargs)
        d.addCallback(self.callback_func)
        return d

    def callback_func(self, response):
        return response

    @abc.abstractmethod
    def get_manager(self, host_config, config, etcd_util,
                    node_id, backend_name):
        pass

    @abc.abstractmethod
    def get_meta_data_by_name(self, name):
        pass


class VolumeBackendOrchestrator(Orchestrator):
    def __init__(self, host_config, backend_configs, def_backend_name):
        super(VolumeBackendOrchestrator, self).__init__(
            host_config, backend_configs, def_backend_name)

    def _get_etcd_client(self, host_config):
        # return util.HpeVolumeEtcdClient(
        return util.EtcdUtil(
            host_config.host_etcd_ip_address,
            host_config.host_etcd_port_number,
            host_config.host_etcd_client_cert,
            host_config.host_etcd_client_key)

    def get_manager(self, host_config, config, etcd_client,
                    node_id, backend_name):
        return mgr.VolumeManager(host_config, config, etcd_client,
                                 node_id, backend_name)

    def get_meta_data_by_name(self, name):
        vol = self._etcd_client.get_vol_byname(name)
        if vol and 'display_name' in vol:
            return vol
        return None

    def volume_exists(self, name):
        vol = self._etcd_client.get_vol_byname(name)
        return vol is not None

    def get_path(self, volname):
        return self._execute_request('get_path', volname)

    def volumedriver_remove(self, volname):
        ret_val = self._execute_request('remove_volume', volname)
        with self.volume_backend_lock:
            LOG.debug('Removing entry for volume %s from cache' %
                      volname)
            # This if condition is to make the test code happy
            if volname in self.volume_backends_map and \
               ret_val is not None:
                del self.volume_backends_map[volname]
        return ret_val

    def volumedriver_unmount(self, volname, vol_mount, mount_id):
        return self._execute_request('unmount_volume',
                                     volname,
                                     vol_mount,
                                     mount_id)

    def volumedriver_create(self, volname, vol_size,
                            vol_prov, vol_flash,
                            compression_val, vol_qos,
                            fs_mode, fs_owner,
                            mount_conflict_delay, cpg,
                            snap_cpg, current_backend, rcg_name):
        ret_val = self._execute_request_for_backend(
            current_backend,
            'create_volume',
            volname,
            vol_size,
            vol_prov,
            vol_flash,
            compression_val,
            vol_qos,
            fs_mode, fs_owner,
            mount_conflict_delay,
            cpg,
            snap_cpg,
            current_backend,
            rcg_name)

        return ret_val

    def clone_volume(self, src_vol_name, clone_name, size, cpg,
                     snap_cpg, clone_options):
        # Imran: Redundant call to get_volume_backend_details
        # Why is backend being passed to clone_volume when it can be
        # retrieved from src_vol or use DEFAULT if src_vol doesn't have it
        backend = self.get_volume_backend_details(src_vol_name)
        LOG.info('orchestrator clone_opts : %s' % (clone_options))
        return self._execute_request('clone_volume', src_vol_name, clone_name,
                                     size, cpg, snap_cpg, backend,
                                     clone_options)

    def create_snapshot(self, src_vol_name, schedName, snapshot_name,
                        snapPrefix, expiration_hrs, exphrs, retention_hrs,
                        rethrs, mount_conflict_delay, has_schedule,
                        schedFrequency):
        # Imran: Redundant call to get_volume_backend_details
        # Why is backend being passed to clone_volume when it can be
        # retrieved from src_vol or use DEFAULT if src_vol doesn't have it
        backend = self.get_volume_backend_details(src_vol_name)
        return self._execute_request('create_snapshot',
                                     src_vol_name,
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
        return self._execute_request('mount_volume', volname,
                                     vol_mount, mount_id)

    def get_volume_snap_details(self, volname, snapname, qualified_name):
        return self._execute_request('get_volume_snap_details', volname,
                                     snapname, qualified_name)

    def manage_existing(self, volname, existing_ref, backend, manage_opts):
        ret_val = self._execute_request_for_backend(
            backend, 'manage_existing', volname, existing_ref,
            backend, manage_opts)
        self.add_cache_entry(volname)
        return ret_val

    def volumedriver_list(self):
        # Use the first volume manager list volumes
        volume_mgr = None
        volume_mgr_info = self._manager.get('DEFAULT')
        if volume_mgr_info:
            volume_mgr = volume_mgr_info['mgr']
        else:
            volume_mgr_info = self._manager.get('DEFAULT_BLOCK')
            if volume_mgr_info:
                volume_mgr = volume_mgr_info['mgr']

        if volume_mgr:
            return volume_mgr.list_volumes()
        else:
            return []
