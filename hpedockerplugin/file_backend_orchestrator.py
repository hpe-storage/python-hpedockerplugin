import json
from oslo_log import log as logging

from hpedockerplugin.backend_orchestrator import Orchestrator
import hpedockerplugin.etcdutil as util
import hpedockerplugin.file_manager as fmgr

LOG = logging.getLogger(__name__)


class FileBackendOrchestrator(Orchestrator):

    fp_etcd_client = None

    def __init__(self, host_config, backend_configs):
        super(FileBackendOrchestrator, self).__init__(
            host_config, backend_configs)

        # self._fp_etcd_client = util.HpeFilePersonaEtcdClient(
        #     host_config.host_etcd_ip_address,
        #     host_config.host_etcd_port_number,
        #     host_config.host_etcd_client_cert,
        #     host_config.host_etcd_client_key)

    def _get_manager(self, host_config, config, etcd_client,
                     backend_name):
        if not FileBackendOrchestrator.fp_etcd_client:
            FileBackendOrchestrator.fp_etcd_client = \
                util.HpeFilePersonaEtcdClient(
                    host_config.host_etcd_ip_address,
                    host_config.host_etcd_port_number,
                    host_config.host_etcd_client_cert,
                    host_config.host_etcd_client_key)

        return fmgr.FileManager(host_config, config, etcd_client,
                                FileBackendOrchestrator.fp_etcd_client,
                                backend_name)

    def _get_etcd_client(self, host_config):
        # Reusing volume code for ETCD client
        return util.HpeShareEtcdClient(
            host_config.host_etcd_ip_address,
            host_config.host_etcd_port_number,
            host_config.host_etcd_client_cert,
            host_config.host_etcd_client_key)

    def get_meta_data_by_name(self, name):
        LOG.info("Fetching share details from ETCD: %s" % name)
        share = self._etcd_client.get_share(name)
        if share:
            LOG.info("Returning share details: %s" % share)
            return share
        LOG.info("Share details not found in ETCD: %s" % name)
        return None

    def create_share(self, **kwargs):
        name = kwargs['name']
        # Removing backend from share dictionary
        # This needs to be put back when share is
        # saved to the ETCD store
        backend = kwargs.pop('backend')
        return self._execute_request_for_backend(
            backend, 'create_share', name, **kwargs)

    def remove_object(self, obj):
        share_name = obj['name']
        return self._execute_request('remove_share', share_name, obj)

    def mount_object(self, obj, mount_id):
        share_name = obj['name']
        return self._execute_request('mount_share', share_name,
                                     obj, mount_id)

    def unmount_object(self, obj, mount_id):
        share_name = obj['name']
        return self._execute_request('unmount_share', share_name,
                                     obj, mount_id)

    # def list_objects(self):
    #     return self._manager.list_shares()

    def get_object_details(self, obj):
        share_name = obj['name']
        return self._execute_request('get_share_details', share_name, obj)

    def list_objects(self):
        db_shares = self._etcd_client.get_all_shares()

        if not db_shares:
            response = json.dumps({u"Err": ''})
            return response

        share_list = []
        for share_info in db_shares:
            path_info = share_info.get('share_path_info')
            if path_info is not None and 'mount_dir' in path_info:
                mountdir = path_info['mount_dir']
            else:
                mountdir = ''
            share = {'Name': share_info['name'],
                     'Mountpoint': mountdir}
            share_list.append(share)
        response = json.dumps({u"Err": '', u"Volumes": share_list})
        return response

    def get_path(self, obj):
        share_name = obj['name']
        mount_dir = '/opt/hpe/data/hpedocker-%s' % share_name
        response = json.dumps({u"Err": '', u"Mountpoint": mount_dir})
        return response

