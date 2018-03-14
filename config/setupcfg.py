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

from hpedockerplugin import configuration as conf
from oslo_log import log as logging
from oslo_config import cfg

host_opts = [
    cfg.StrOpt('hpedockerplugin_driver',
               default='hpe.hpe_lefthand_iscsi.HPELeftHandISCSIDriver',
               help='HPE Docker Plugin Driver to use for volume creation'),
    cfg.StrOpt('host_etcd_ip_address',
               default='0.0.0.0',
               help='Host IP Address to use for etcd communication'),
    cfg.PortOpt('host_etcd_port_number',
                default=2379,
                help='Host Port Number to use for etcd communication'),
    cfg.StrOpt('host_etcd_ca_cert',
                default=None,
                help='CA certificate location'),
    cfg.StrOpt('host_etcd_client_cert',
                default=None,
                help='Client certificate location'),
    cfg.StrOpt('host_etcd_client_key',
                default=None,
                help='Client certificate key location'),
    cfg.StrOpt('logging',
               default='WARNING',
               help='Debug level for hpe docker volume plugin'),
    cfg.BoolOpt('use_multipath',
               default=False,
               help='Toggle use of multipath for volume attachments.'),
    cfg.BoolOpt('enforce_multipath',
               default=False,
               help='Toggle enforcing of multipath for volume attachments.'),
]

CONF = cfg.CONF
logging.register_options(CONF)

CONF.register_opts(host_opts)


def setup_logging(name, level):

    logging.setup(CONF, name)
    LOG = logging.getLogger(None)

    if level == 'INFO':
        LOG.logger.setLevel(logging.INFO)
    if level == 'DEBUG':
        LOG.logger.setLevel(logging.DEBUG)
    if level == 'WARNING':
        LOG.logger.setLevel(logging.WARNING)
    if level == 'ERROR':
        LOG.logger.setLevel(logging.ERROR)


def getdefaultconfig(configfile):
    CONF(configfile, project='hpedockerplugin', version='1.0.0')
    configuration = conf.Configuration(host_opts, config_group='DEFAULT')

    return configuration
