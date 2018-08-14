class ArrayConnectionParams(object):
    def __init__(self, d=None):
        if d and isinstance(d, dict):
            for k, v in d.iteritems():
                object.__setattr__(self, k, v)

    def __getattr__(self, key):
        try:
            object.__getattribute__(self, key)
        except AttributeError:
            return None
