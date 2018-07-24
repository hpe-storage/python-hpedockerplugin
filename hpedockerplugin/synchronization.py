import inspect
import json

from oslo_log import log as logging

import hpedockerplugin.exception as exception

LOG = logging.getLogger(__name__)

class Stack:
    def __init__(self):
        self.items = []

    def isEmpty(self):
        return self.items == []

    def push(self, item):
        self.items.append(item)

    def pop(self):
        return self.items.pop()

    def peek(self):
        return self.items[len(self.items)-1]

    def size(self):
        return len(self.items)

def synchronized(*lock_name):
    def _synchronized(f):
        def _wrapped(*a, **k):
            call_args = inspect.getcallargs(f, *a, **k)
            call_args['f_name'] = f.__name__

            self = call_args['self']
            stack = Stack()
            lck_name = ''
            decorator_args =  str(lock_name).format(**call_args)
            LOG.info(" Decorator args: %s " % decorator_args)
            tmp_str = decorator_args.lstrip('(').rstrip(')')
            tmp_str = tmp_str.replace("'","")
            args = list(tmp_str.split(","))

            try:
                for k in args:
                    if k == '':
                      continue
                    lck_name = k
                    self._etcd.try_lock_volname(lck_name)
                    stack.push(lck_name)
                    LOG.info('Lock acquired: [caller=%s, lock-name=%s]'
                             % (f.__name__, lck_name))
                return f(*a)
            except exception.HPEPluginLockFailed:
                LOG.exception('Lock acquire failed: [caller=%(caller)s, '
                              'lock-name=%(name)s]',
                              {'caller': f.__name__,
                               'name': lck_name})
                response = json.dumps({u"Err": ''})
                return response
            finally:
                while stack.isEmpty() == False:
                    try:
                        lck_name = stack.pop()
                        self._etcd.try_unlock_volname(lck_name)
                        LOG.info('Lock released: [caller=%s, lock-name=%s]' %
                                 (f.__name__, lck_name))
                    except exception.HPEPluginUnlockFailed:
                        LOG.exception('Lock release failed: [caller=%(caller)s'
                                      ', lock-name=%(name)s]',
                                      {'caller': f.__name__,
                                       'name': lck_name})
        return _wrapped
    return _synchronized
