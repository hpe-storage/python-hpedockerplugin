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
from config.setupcfg import getdefaultconfig, setup_logging
from hpe_storage_api import VolumePlugin

from os import umask
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

from oslo_log import log as logging

LOG = logging.getLogger(__name__)

PLUGIN_PATH = FilePath("/run/docker/plugins/hpe/hpe.sock")
CONFIG_FILE = '../config/hpe.conf'

CONFIG = ['--config-file', CONFIG_FILE]


class HPEDockerPluginService(object):

    def __init__(self):
        self._reactor = reactor

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

        # Setup the default, hpe3parconfig, and hpelefthandconfig
        # configuration objects.
        try:
            hpedefaultconfig = getdefaultconfig(CONFIG)
        except Exception as ex:
            msg = (_('hpe3pardocker setupservice failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginStartPluginException(reason=msg)

        # Set Logging level
        logging_level = hpedefaultconfig.logging
        setup_logging('hpe_storage_api', logging_level)

        self._create_listening_directory(PLUGIN_PATH.parent())
        endpoint = serverFromString(self._reactor, "unix:{}:mode=600".
                                    format(PLUGIN_PATH.path))
        servicename = StreamServerEndpointService(endpoint, Site(
            VolumePlugin(self._reactor, hpedefaultconfig).app.resource()))
        return servicename

hpedockerplugin = HPEDockerPluginService()

# this will hold the services that combine to form the poetry server
top_service = service.MultiService()

hpepluginservice = hpedockerplugin.setupservice()
hpepluginservice.setServiceParent(top_service)

# this variable has to be named 'application'
application = service.Application("hpedockerplugin")

# this hooks the collection we made to the application
top_service.setServiceParent(application)

LOG.info(_LI('HPE Docker Volume Plugin Successfully Started'))
