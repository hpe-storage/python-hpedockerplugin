import six
from oslo_log import log as logging

from hpedockerplugin.cmd import cmd
from hpedockerplugin import exception

LOG = logging.getLogger(__name__)


class CreateVfsCmd(cmd.Cmd):
    def __init__(self, file_mgr, cpg_name, fpg_name, vfs_name, ip, netmask):
        self._file_mgr = file_mgr
        self._share_etcd = file_mgr.get_etcd()
        self._fp_etcd = file_mgr.get_file_etcd()
        self._mediator = file_mgr.get_mediator()
        self._backend = file_mgr.get_backend()
        self._cpg_name = cpg_name
        self._fpg_name = fpg_name
        self._vfs_name = vfs_name
        self._ip = ip
        self._netmask = netmask

    def execute(self):
        try:
            LOG.info("Creating VFS %s on the backend" % self._vfs_name)
            result = self._mediator.create_vfs(self._vfs_name,
                                               self._ip, self._netmask,
                                               fpg=self._fpg_name)

            self._update_fpg_metadata(self._ip, self._netmask)
            LOG.info("create_vfs result: %s" % result)

        except exception.ShareBackendException as ex:
            msg = "Create VFS failed. Reason: %s" % six.text_type(ex)
            LOG.error(msg)
            # TODO: Add code to undo VFS creation at the backend
            # self._mediator.remove_vfs(self._fpg_name, self._vfs_name)
            raise exception.VfsCreationFailed(reason=msg)

    def unexecute(self):
        # No need to implement this as FPG delete should delete this too
        pass

    def _update_fpg_metadata(self, ip, netmask):
        with self._fp_etcd.get_fpg_lock(self._backend, self._cpg_name,
                                        self._fpg_name):
            fpg_info = self._fp_etcd.get_fpg_metadata(self._backend,
                                                      self._cpg_name,
                                                      self._fpg_name)
            fpg_info['vfs'] = self._vfs_name
            ip_subnet_map = fpg_info.get('ips')
            if ip_subnet_map:
                ips = ip_subnet_map.get(netmask)
                if ips:
                    ips.append(ip)
                else:
                    ip_subnet_map[netmask] = [ip]
            else:
                fpg_info['ips'] = {netmask: [ip]}
            self._fp_etcd.save_fpg_metadata(self._backend, self._cpg_name,
                                            self._fpg_name, fpg_info)
