import abc

from hpedockerplugin import exception


class Cmd(object):
    @abc.abstractmethod
    def execute(self, args):
        pass

    def unexecute(self, args):
        pass
