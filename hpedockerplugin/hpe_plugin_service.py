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
Command to start up the Docker plugin.
"""
import socket

from config import setupcfg
from hpe_storage_api import VolumePlugin

from os import umask, remove
from stat import S_IRUSR, S_IWUSR, S_IXUSR

from twisted.internet import reactor
from twisted.internet.endpoints import serverFromString
from twisted.application.internet import StreamServerEndpointService
from twisted.application import service
from twisted.web.server import Site
from twisted.python.filepath import FilePath
from twisted.internet.address import UNIXAddress
from i18n import _, _LI

import exception
import six
# import argparse
# import pdb

from oslo_log import log as logging

LOG = logging.getLogger(__name__)

PLUGIN_PATH = FilePath("/run/docker/plugins/hpe.sock")
CONFIG_FILE = '/etc/hpedockerplugin/hpe.conf'

CONFIG = ['--config-file', CONFIG_FILE]


class HPEDockerPluginService(object):

    def __init__(self, cfg):
        self._reactor = reactor
        self._config_file = cfg

        if not self._sock_in_use():
            self._cleanup()

        # Set a cleanup function when reactor stops
        reactor.addSystemEventTrigger("before", "shutdown", self._cleanup)

    @staticmethod
    def _sock_in_use():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(PLUGIN_PATH.path)
        except socket.error:
            LOG.info("hpe.sock not in use")
            return False
        else:
            LOG.info("hpe.sock in use")
            sock.close()
            return True

    def _cleanup(self):
        LOG.info(_LI('_cleanup invoked: HPE Docker Volume Plugin Shutdown'))
        try:
            remove(PLUGIN_PATH.path)
        except OSError:
            pass
        try:
            remove(PLUGIN_PATH.path + ".lock")
        except OSError:
            pass
        LOG.info("Cleanup done!")

    """
    Start the Docker plugin.
    """
    def _create_listening_directory(self, directory_path):
        """
        Create the parent directory for the Unix socket if it doesn't exist.

        :param FilePath directory_path: The directory to create.
        """
        original_umask = umask(0)
        try:
            if not directory_path.exists():
                directory_path.makedirs()
            directory_path.chmod(S_IRUSR | S_IWUSR | S_IXUSR)
        finally:
            umask(original_umask)

    def setupservice(self):
        # TODO: Remove this line when Python Klein pull request #103 is
        # released
        # NOTE: Docker 1.9 will fail without this line. Docker 1.10 will
        # fail as it no longer includes the Host as part of the http header.
        # Therefore, we need to remove this line altogether.
        # 4/6/16 Removing this line as it's causing problems for testers on
        # Docker 1.10. If you're running 1.9, you can apply the Klein fix
        # here https://github.com/twisted/klein.git to fix.
        UNIXAddress.port = 0
        UNIXAddress.host = b"127.0.0.1"

        # Turnoff use of parameterized hpe.conf and use bind mounted
        # configuration file
        # CONFIG = ['--config-file', self._config_file]
        CONFIG = ['--config-file', CONFIG_FILE]

        # Setup the default, hpe3parconfig, and hpelefthandconfig
        # configuration objects.
        try:
            host_config = setupcfg.get_host_config(CONFIG)
            backend_configs = setupcfg.get_all_backend_configs(CONFIG)
        except Exception as ex:
            msg = (_('hpe3pardocker setupservice failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginStartPluginException(reason=msg)

        file_driver = 'hpedockerplugin.hpe.hpe_3par_file.HPE3PARFileDriver'
        fc_driver = 'hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver'
        iscsi_driver = 'hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver'
        # backend_configs -> {'backend1': config1, 'backend2': config2, ...}
        # all_configs -> {'block': backend_configs1, 'file': backend_configs2}
        file_configs = {}
        block_configs = {}
        all_configs = {}
        for backend_name, config in backend_configs.items():
            configured_driver = config.hpedockerplugin_driver.strip()
            if configured_driver == file_driver:
                file_configs[backend_name] = config
            elif configured_driver == fc_driver or \
                    configured_driver == iscsi_driver:
                block_configs[backend_name] = config
            else:
                msg = "Bad driver name specified in hpe.conf: %s" %\
                      configured_driver
                raise exception.HPEPluginStartPluginException(reason=msg)

        if file_configs:
            all_configs['file'] = (host_config, file_configs)
        if block_configs:
            all_configs['block'] = (host_config, block_configs)

        # Set Logging level
        logging_level = backend_configs['DEFAULT'].logging
        setupcfg.setup_logging('hpe_storage_api', logging_level)

        self._create_listening_directory(PLUGIN_PATH.parent())
        endpoint = serverFromString(self._reactor, "unix:{}:mode=600".
                                    format(PLUGIN_PATH.path))
        servicename = StreamServerEndpointService(endpoint, Site(
            VolumePlugin(self._reactor, all_configs).app.resource()))
        return servicename


class HpeFactory(object):

    def __init__(self, cfg):
        self._cfg = cfg

    def start_service(self):
        hpedockerplugin = HPEDockerPluginService(self._cfg)

        # this will hold the services that combine to form the poetry server
        top_service = service.MultiService()

        hpepluginservice = hpedockerplugin.setupservice()
        hpepluginservice.setServiceParent(top_service)

        # this variable has to be named 'application'
        # application = service.Application("hpedockerplugin")

        # this hooks the collection we made to the application
        # hpeplugin_service = top_service.setServiceParent(application)

        return top_service
