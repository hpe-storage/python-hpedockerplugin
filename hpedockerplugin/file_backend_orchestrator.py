import json
from oslo_log import log as logging

from hpedockerplugin.backend_orchestrator import Orchestrator
import hpedockerplugin.etcdutil as util
import hpedockerplugin.file_manager as fmgr

LOG = logging.getLogger(__name__)


class FileBackendOrchestrator(Orchestrator):

    fp_etcd_client = None

    def __init__(self, host_config, backend_configs, def_backend_name):
        super(FileBackendOrchestrator, self).__init__(
            host_config, backend_configs, def_backend_name)

    @staticmethod
    def _initialize_orchestrator(host_config):
        FileBackendOrchestrator.fp_etcd_client = \
            util.HpeFilePersonaEtcdClient(
                host_config.host_etcd_ip_address,
                host_config.host_etcd_port_number,
                host_config.host_etcd_client_cert,
                host_config.host_etcd_client_key)

    # Implementation of abstract function from base class
    def get_manager(self, host_config, config, etcd_client,
                    node_id, backend_name):
        LOG.info("Getting file manager...")
        return fmgr.FileManager(host_config, config, etcd_client,
                                FileBackendOrchestrator.fp_etcd_client,
                                node_id, backend_name)

    # Implementation of abstract function from base class
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

    def share_exists(self, name):
        try:
            self._etcd_client.get_share(name)
        except Exception:
            return False
        else:
            return True

    def create_share(self, **kwargs):
        name = kwargs['name']
        # Removing backend from share dictionary
        # This needs to be put back when share is
        # saved to the ETCD store
        backend = kwargs.get('backend')
        return self._execute_request_for_backend(
            backend, 'create_share', name, **kwargs)

    def create_share_help(self, **kwargs):
        LOG.info("Working on share help content generation...")
        create_help_path = "./config/create_share_help.txt"
        create_help_file = open(create_help_path, "r")
        create_help_content = create_help_file.read()
        create_help_file.close()
        LOG.info(create_help_content)
        return json.dumps({u"Err": create_help_content})

    def get_backends_status(self, **kwargs):
        LOG.info("Getting backend status...")
        line = "=" * 54
        spaces = ' ' * 42
        resp = "\n%s\nNAME%sSTATUS\n%s\n" % (line, spaces, line)

        printable_len = 45
        for k, v in self._manager.items():
            backend_state = v['backend_state']
            padding = (printable_len - len(k)) * ' '
            resp += "%s%s  %s\n" % (k, padding, backend_state)
        return json.dumps({u'Err': resp})

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
        return share_list

    def get_path(self, obj):
        share_name = obj['name']
        mount_dir = '/opt/hpe/data/hpedocker-%s' % share_name
        response = json.dumps({u"Err": '', u"Mountpoint": mount_dir})
        return response
