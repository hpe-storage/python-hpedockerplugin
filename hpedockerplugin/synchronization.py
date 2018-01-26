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
                LOG.info("Lock acquired: [lock-name=%s]" % lck_name)
                return f(*a, **k)
            except exception.HPEPluginLockFailed:
                LOG.exception('Failed to acquire lock: [lock-name=%(name)s]',
                             {'name': lck_name})
                response = json.dumps({u"Err": ''})
                return response
            finally:
                if lock_acquired:
                    try:
                        plugin._etcd.try_unlock_volname(lck_name)
                        LOG.info("Released lock: [lock-name=%s]" % lck_name)
                    except exception.HPEPluginUnlockFailed:
                        LOG.exception('Release lock failed: '
                                      '[lock-name=%(name)s]',
                                      {'name': lck_name})
        return _wrapped
    return _synchronized
