import inspect
import json

from oslo_log import log as logging

import hpedockerplugin.exception as exception

LOG = logging.getLogger(__name__)


def __synchronized(lock_type, lock_name, f, *a, **k):
    call_args = inspect.getcallargs(f, *a, **k)
    call_args['f_name'] = f.__name__
    lck_name = lock_name.format(**call_args)
    lock_acquired = False
    self = call_args['self']
    lock = self._etcd.get_lock(lock_type)
    try:
        lock.try_lock_name(lck_name)
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
                lock.try_unlock_name(lck_name)
                LOG.info('Lock released: [caller=%s, lock-name=%s]' %
                         (f.__name__, lck_name))
            except exception.HPEPluginUnlockFailed:
                LOG.exception('Lock release failed: [caller=%(caller)s'
                              ', lock-name=%(name)s]',
                              {'caller': f.__name__,
                               'name': lck_name})


def synchronized_volume(lock_name):
    def _synchronized(f):
        def _wrapped(*a, **k):
            return __synchronized('VOL', lock_name, f, *a, **k)
        return _wrapped
    return _synchronized


def synchronized_rcg(lock_name):
    def _synchronized(f):
        def _wrapped(*a, **k):
            return __synchronized('RCG', lock_name, f, *a, **k)
        return _wrapped
    return _synchronized


def synchronized_fp_share(lock_name):
    def _synchronized(f):
        def _wrapped(*a, **k):
            return __synchronized('FP_SHARE', lock_name, f, *a, **k)
        return _wrapped
    return _synchronized
