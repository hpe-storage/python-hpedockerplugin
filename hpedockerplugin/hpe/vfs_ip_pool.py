from oslo_config import types
from oslo_log import log
import six

from hpedockerplugin import exception

LOG = log.getLogger(__name__)


class VfsIpPool(types.String, types.IPAddress):
    """VfsIpPool type.
    Used to represent VFS IP Pool for a single backend
    Converts configuration value to an IP subnet dictionary
    VfsIpPool value format::
        IP_address_1:SubnetA,IP_address_2-IP_address10:SubnetB,...
    IP address is of type types.IPAddress
    Optionally doing range checking.
    If value is whitespace or empty string will raise error
    :param type_name: Type name to be used in the sample config file.
    """

    def __init__(self, type_name='VfsIpPool'):
        types.String.__init__(self, type_name=type_name)
        types.IPAddress.__init__(self, type_name=type_name)

    def _validate_ip(self, ip):
        ip = types.String.__call__(self, ip.strip())
        # Validate if the IP address is good
        try:
            types.IPAddress.__call__(self, ip)
        except ValueError as val_err:
            msg = "ERROR: Invalid IP address specified: %s" % ip
            LOG.error(msg)
            raise exception.InvalidInput(msg)

    def __call__(self, value):

        if value is None or value.strip(' ') is '':
            message = ("ERROR: Invalid configuration. "
                       "'hpe3par_server_ip_pool' must be set in the format "
                       "'IP1:Subnet1,IP2:Subnet2...,IP3-IP5:Subnet3'. Check "
                       "help for usage")
            LOG.error(message)
            raise exception.InvalidInput(err=message)

        values = value.split(",")

        # ip-subnet-dict = {subnet: set([ip-list])}
        ip_subnet_dict = {}
        for value in values:
            if '-' in value:
                ips, subnet = self._get_ips_for_range(value)
            else:
                ip, subnet = value.split(':')
                self._validate_ip(ip)
                self._validate_ip(subnet)
                ips = [ip]

            ip_set = ip_subnet_dict.get(subnet)
            if ip_set:
                ip_set.update(ips)
            else:
                # Keeping it as set to avoid duplicates
                ip_subnet_dict[subnet] = set(ips)
        return ip_subnet_dict

    def __repr__(self):
        return 'VfsIpPool'

    def _formatter(self, value):
        return six.text_type(value)
