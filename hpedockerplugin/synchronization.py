import inspect
import json

from oslo_log import log as logging

import exception

LOG = logging.getLogger(__name__)


def synchronized(lock_name):
    def _synchronized(f):
        def _wrapped(*a, **k):
            call_args = inspect.getcallargs(f, *a, **k)
            call_args['f_name'] = f.__name__
            lck_name = lock_name.format(**call_args)
            lock_acquired = False
            plugin = a[0]
            try:
                plugin._etcd.try_lock_volname(lck_name)
                lock_acquired = True
                LOG.info('Lock acquired: [caller=%s, lock-name=%s]'
                         % (f.__name__, lck_name))
                return f(*a, **k)
            except exception.HPEPluginLockFailed:
                LOG.exception('Lock acquire failed: [caller=%(caller)s, '
                              'lock-name=%(name)s]',
                              {'caller': f.__name__,
                               'name': lck_name})
                response = json.dumps({u"Err": ''})
                return response
            finally:
                if lock_acquired:
                    try:
                        plugin._etcd.try_unlock_volname(lck_name)
                        LOG.info('Lock released: [caller=%s, lock-name=%s]' %
                                 (f.__name__, lck_name))
                    except exception.HPEPluginUnlockFailed:
                        LOG.exception('Lock release failed: [caller=%(caller)s'
                                      ', lock-name=%(name)s]',
                                      {'caller': f.__name__,
                                       'name': lck_name})
        return _wrapped
    return _synchronized
