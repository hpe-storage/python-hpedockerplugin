import abc

from hpedockerplugin import exception


class Cmd(object):
    def __init__(self):
        self._next_cmd = None

    def set_next_cmd(self, next_cmd):
        self._next_cmd = next_cmd

    def execute(self, args):
        try:
            ret_val = self._execute(args)
            if self._next_cmd:
                self._next_cmd.execute(ret_val)
        except exception.PluginException:
            self._unexecute(args)

    @abc.abstractmethod
    def _execute(self, args):
        pass

    def _unexecute(self, args):
        pass
