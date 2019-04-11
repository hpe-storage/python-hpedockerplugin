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
from hpedockerplugin.hpe import hpe3par_opts as plugin_opts
from oslo_log import log as logging
import logging as log
from oslo_config import cfg
from logging.handlers import RotatingFileHandler

host_opts = [
    cfg.StrOpt('hpedockerplugin_driver',
               default='hpe.hpe_lefthand_iscsi.HPELeftHandISCSIDriver',
               help='HPE Docker Plugin Driver to use for volume creation'),
    cfg.StrOpt('mount_prefix',
               default=None,
               help='Mount prefix for volume mount'),
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
    cfg.BoolOpt('strict_ssh_host_key_policy',
                default=False,
                help='Option to enable strict host key checking.  When '
                     'set to "True" the plugin will only connect to systems '
                     'with a host key present in the configured '
                     '"ssh_hosts_key_file".  When set to "False" the host key '
                     'will be saved upon first connection and used for '
                     'subsequent connections.  Default=False'),
    cfg.StrOpt('ssh_hosts_key_file',
               default='/root/.ssh/ssh_known_hosts',
               help='File containing SSH host keys for the systems with which '
                    'the plugin needs to communicate'),
]

CONF = cfg.CONF
logging.register_options(CONF)
CONF.register_opts(host_opts)


def setup_logging(name, level):

    logging.setup(CONF, name)
    LOG = logging.getLogger(None)

    # Add option to do Log Rotation
    handler = RotatingFileHandler('/etc/hpedockerplugin/3pardcv.log',
                                  maxBytes=10000000, backupCount=100)
    formatter = log.Formatter('%(asctime)-12s [%(levelname)s] '
                               '%(name)s [%(thread)d] '
                               '%(threadName)s %(message)s')

    handler.setFormatter(formatter)
    LOG.logger.addHandler(handler)

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


def get_host_config(configfile):
    CONF(configfile, project='hpedockerplugin', version='1.0.0')
    return conf.Configuration(host_opts)


def get_all_backend_configs(configfile):
    backend_configs = {}
    CONF(configfile, project='hpedockerplugin', version='1.0.0')
    for backend_name in CONF.list_all_sections():
        config = conf.Configuration(host_opts,
                                    config_group=backend_name)
        config.append_config_values(plugin_opts.hpe3par_opts)
        config.append_config_values(plugin_opts.san_opts)
        config.append_config_values(plugin_opts.volume_opts)
        backend_configs[backend_name] = config

    return backend_configs
