from oslo_log import log as logging

from hpedockerplugin import exception
from hpedockerplugin import request_context as req_ctxt
import hpedockerplugin.synchronization as synchronization

LOG = logging.getLogger(__name__)


class RequestRouter(object):
    def __init__(self, **kwargs):
        self._orchestrators = {'volume': kwargs.get('vol_orchestrator'),
                               'file': kwargs.get('file_orchestrator')}
        # TODO: Workaround just to help unit-test framework to work
        # To be fixed later
        if self._orchestrators['volume']:
            self._etcd = self._orchestrators['volume']._etcd_client
        elif self._orchestrators['file']:
            self._etcd = self._orchestrators['file']._etcd_client

        all_configs = kwargs.get('all_configs')
        self._ctxt_builder_factory = \
            req_ctxt.RequestContextBuilderFactory(all_configs)

    def route_create_request(self, name, contents, orchestrator):
        LOG.info("route_create_request: Entering...")
        req_ctxt_builder = \
            self._ctxt_builder_factory.get_request_context_builder()
        if orchestrator:
            req_ctxt = req_ctxt_builder.build_request_context(
                contents, orchestrator.get_default_backend_name())
            operation = req_ctxt['operation']
            kwargs = req_ctxt['kwargs']
            resp = getattr(orchestrator, operation)(**kwargs)
            LOG.info("route_create_request: Return value: %s" % resp)
            return resp
        else:
            msg = "'%s' driver is not configured. Please refer to" \
                  "the document to learn about configuring the driver."
            LOG.error(msg)
            raise exception.InvalidInput(msg)

    @synchronization.synchronized_fp_share('{name}')
    def route_remove_request(self, name):
        orch = self._orchestrators['file']
        if orch:
            meta_data = orch.get_meta_data_by_name(name)
            if meta_data:
                return orch.remove_object(meta_data)
        # for persona, orch in self._orchestrators.items():
        #     if orch:
        #         meta_data = orch.get_meta_data_by_name(name)
        #         if meta_data:
        #             return orch.remove_object(meta_data)
        raise exception.EtcdMetadataNotFound(
            "Remove failed: '%s' doesn't exist" % name)

    @synchronization.synchronized_fp_share('{name}')
    def route_mount_request(self, name, mount_id):
        orch = self._orchestrators['file']
        if orch:
            meta_data = orch.get_meta_data_by_name(name)
            if meta_data:
                return orch.mount_object(meta_data, mount_id)
        # for persona, orch in self._orchestrators.items():
        #     if orch:
        #         meta_data = orch.get_meta_data_by_name(name)
        #         if meta_data:
        #             return orch.mount_object(meta_data, mount_id)
        raise exception.EtcdMetadataNotFound(
            "Mount failed: '%s' doesn't exist" % name)

    @synchronization.synchronized_fp_share('{name}')
    def route_unmount_request(self, name, mount_id):
        orch = self._orchestrators['file']
        if orch:
            meta_data = orch.get_meta_data_by_name(name)
            if meta_data:
                return orch.unmount_object(meta_data, mount_id)
        # for persona, orch in self._orchestrators.items():
        #     if orch:
        #         meta_data = orch.get_meta_data_by_name(name)
        #         if meta_data:
        #             return orch.unmount_object(meta_data, mount_id)
        raise exception.EtcdMetadataNotFound(
            "Unmount failed: '%s' doesn't exist" % name)

    # # Since volumes and shares are created under the same ETCD key
    # # any orchestrator can return all the volume and share names
    # def list_objects(self):
    #     for persona, orch in self._orchestrators.items():
    #         if orch:
    #             return orch.list_objects()
    #     # TODO: Check if we need to return empty response here?

    def get_object_details(self, name):
        orch = self._orchestrators['file']
        if orch:
            meta_data = orch.get_meta_data_by_name(name)
            if meta_data:
                return orch.get_object_details(meta_data)
        # for persona, orch in self._orchestrators.items():
        #     if orch:
        #         meta_data = orch.get_meta_data_by_name(name)
        #         if meta_data:
        #             return orch.get_object_details(meta_data)
        LOG.warning("Share '%s' not found" % name)
        raise exception.EtcdMetadataNotFound(
            "ERROR: Meta-data details for '%s' don't exist" % name)

    def route_get_path_request(self, name):
        orch = self._orchestrators['file']
        if orch:
            meta_data = orch.get_meta_data_by_name(name)
            if meta_data:
                return orch.get_path(meta_data)
        # for persona, orch in self._orchestrators.items():
        #     if orch:
        #         meta_data = orch.get_meta_data_by_name(name)
        #         if meta_data:
        #             return orch.get_path(name)
        raise exception.EtcdMetadataNotFound(
            "'%s' doesn't exist" % name)

    def list_objects(self):
        orch = self._orchestrators['file']
        if orch:
            return orch.list_objects()
        return []
