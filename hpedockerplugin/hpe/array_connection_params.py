class ArrayConnectionParams(dict):
    def __init__(self, d=None):
        if d:
            super(ArrayConnectionParams, self).__init__(d)
        else:
            super(ArrayConnectionParams, self).__init__()

    def __getattr__(self, key):
        return self.get(key)
