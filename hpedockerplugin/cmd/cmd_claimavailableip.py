import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception

LOG = logging.getLogger(__name__)


class ClaimAvailableIPCmd(cmd.Cmd):
    def __init__(self, backend, config, fp_etcd, mediator):
        self._backend = backend
        self._fp_etcd = fp_etcd
        self._config = config
        self._locked_ip = None
        self._mediator = mediator

    def execute(self):
        try:
            return self._get_available_ip()
        except (exception.IPAddressPoolExhausted,
                exception.EtcdMetadataNotFound) as ex:
            msg = "Claim available IP failed. Reason: %s" % six.text_type(ex)
            raise exception.VfsCreationFailed(reason=msg)

    def unexecute(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            backend_metadata = self._fp_etcd.get_backend_metadata(
                self._backend)
            ips_in_use = backend_metadata['ips_in_use']
            if self._locked_ip in ips_in_use:
                ips_in_use.remove(self._locked_ip)

            ips_locked_for_use = backend_metadata['ips_locked_for_use']
            if self._locked_ip in ips_locked_for_use:
                ips_locked_for_use.remove(self._locked_ip)

            self._fp_etcd.save_backend_metadata(self._backend,
                                                backend_metadata)

    def _get_available_ip(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            try:
                backend_metadata = self._fp_etcd.get_backend_metadata(
                    self._backend
                )
            except exception.EtcdMetadataNotFound:
                backend_metadata = {
                    'ips_in_use': [],
                    'ips_locked_for_use': [],
                }
                LOG.info("Backend metadata entry for backend %s not found."
                         "Creating %s..." %
                         (self._backend, six.text_type(backend_metadata)))
                self._fp_etcd.save_backend_metadata(self._backend,
                                                    backend_metadata)

            # ips_in_use = backend_metadata['ips_in_use']
            all_in_use_backend_ips = self._get_all_in_use_ip_from_backend()
            ips_locked_for_use = backend_metadata['ips_locked_for_use']
            total_ips_in_use = set(all_in_use_backend_ips + ips_locked_for_use)
            ip_netmask_pool = self._config.hpe3par_server_ip_pool[0]
            for netmask, ips in ip_netmask_pool.items():
                available_ips = ips - total_ips_in_use
                if available_ips:
                    # Return first element from the set
                    available_ip = next(iter(available_ips))
                    # Lock the available IP till VFS is created
                    ips_locked_for_use.append(available_ip)
                    # Save the updated meta-data
                    self._fp_etcd.save_backend_metadata(self._backend,
                                                        backend_metadata)
                    self._locked_ip = available_ip
                    return available_ip, netmask
            raise exception.IPAddressPoolExhausted()

    def _get_all_in_use_ip_from_backend(self):
        ips = []
        all_vfs = self._mediator.get_all_vfs()
        for vfs in all_vfs:
            all_ip_info = vfs['IPInfo']
            for ip_info in all_ip_info:
                ips.append(ip_info['IPAddr'])
        return ips

    def mark_ip_in_use(self):
        with self._fp_etcd.get_file_backend_lock(self._backend):
            if self._locked_ip:
                try:
                    backend_metadata = self._fp_etcd.get_backend_metadata(
                        self._backend)
                    ips_in_use = backend_metadata['ips_in_use']
                    ips_locked_for_use = \
                        backend_metadata['ips_locked_for_use']
                    # Move IP from locked-ip-list to in-use-list
                    ips_locked_for_use.remove(self._locked_ip)
                    ips_in_use.append(self._locked_ip)
                    self._fp_etcd.save_backend_metadata(self._backend,
                                                        backend_metadata)
                except (exception.EtcdMetadataNotFound, Exception) as ex:
                    msg = "mark_ip_in_use failed: Metadata for backend " \
                          "%s not found: Exception: %s" % (self._backend,
                                                           six.text_type(ex))
                    LOG.error(msg)
                    raise exception.VfsCreationFailed(reason=msg)
