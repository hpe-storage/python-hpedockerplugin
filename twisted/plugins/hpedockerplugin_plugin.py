from zope.interface import implementer

from twisted.python import usage
from twisted.plugin import IPlugin
from twisted.application.service import IServiceMaker
from twisted.application import internet

from hpedockerplugin.hpe_plugin_service import HpeFactory


class Options(usage.Options):
    optParameters = [["cfg", "c", "/home/vagrant/python-hpedockerplugin/config"
                                  "/hpe.conf", "The configuration file."]]


@implementer(IServiceMaker)
@implementer(IPlugin)
class MyServiceMaker(object):
    # implements(IServiceMaker, IPlugin)
    tapname = "hpe_plugin_service"
    description = "Run to start up the HPE Docker Volume Plugin"
    options = Options

    def makeService(self, options):
        """
        Construct a TCPServer from a factory defined in myproject.
        """
        return HpeFactory(options["cfg"]).start_service()


# Now construct an object which *provides* the relevant interfaces
# The name of this variable is irrelevant, as long as there is *some*
# name bound to a provider of IPlugin and IServiceMakera
serviceMaker = MyServiceMaker()
