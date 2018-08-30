from oslo_log import log as logging

LOG = logging.getLogger(__name__)


class ArrayConnectionParams(object):
    def __init__(self, d=None):
        if d and isinstance(d, dict):
            for k, v in d.items():
                object.__setattr__(self, k, v)

    def __getattr__(self, key):
        LOG.info("ACP Key: %s" % key)
        try:
            object.__getattribute__(self, key)
        except AttributeError:
            return None
