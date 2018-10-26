# (c) Copyright [2016] Hewlett Packard Enterprise Development LP
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import etcd
import json
from oslo_log import log as logging
import six
from hpedockerplugin.i18n import _, _LI
import hpedockerplugin.exception as exception

LOG = logging.getLogger(__name__)

VOLUMEROOT = '/volumes'
RCROOT = '/remote-copy'
RC_KEY_FMT_STR = "%s/%s#%s"
BACKENDROOT = '/backend'
LOCKROOT = '/volumes-lock'
RCG_LOCKROOT = '/rcg-lock'


class EtcdUtil(object):

    def __init__(self, host, port, client_cert, client_key):
        self.host = host
        self.port = port

        LOG.info('ETCDUTIL datatype of host is %s ' % type(self.host))
        host_tuple = ()
        if isinstance(self.host, str):
            if ',' in self.host:
                host_list = [h.strip() for h in host.split(',')]

                for i in host_list:
                    temp_tuple = (i.split(':')[0], int(i.split(':')[1]))
                    host_tuple = host_tuple + (temp_tuple,)

                host_tuple = tuple(host_tuple)

        LOG.info('ETCDUTIL host_tuple is %s, host is %s ' % (host_tuple,
                                                             self.host))

        self.volumeroot = VOLUMEROOT + '/'
        self.backendroot = BACKENDROOT + '/'
        if client_cert is not None and client_key is not None:
            if len(host_tuple) > 0:
                LOG.info('ETCDUTIL host tuple is not None')
                self.client = etcd.Client(host=host_tuple, port=port,
                                          protocol='https',
                                          cert=(client_cert, client_key),
                                          allow_reconnect=True)
            else:
                LOG.info('ETCDUTIL host %s ' % host)
                self.client = etcd.Client(host=host, port=port,
                                          protocol='https',
                                          cert=(client_cert, client_key))
        else:
            LOG.info('ETCDUTIL no certs')
            if len(host_tuple) > 0:
                LOG.info('Use http protocol')
                self.client = etcd.Client(host=host_tuple, port=port,
                                          protocol='http',
                                          allow_reconnect=True)
            else:
                self.client = etcd.Client(host, port)
        self._make_root()

    def _make_root(self):
        try:
            self.client.read(VOLUMEROOT)
        except etcd.EtcdKeyNotFound:
            self.client.write(VOLUMEROOT, None, dir=True)
        try:
            self.client.read(BACKENDROOT)
        except etcd.EtcdKeyNotFound:
            self.client.write(BACKENDROOT, None, dir=True)
        except Exception as ex:
            msg = (_('Could not init EtcUtil: %s'), six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMakeEtcdRootException(reason=msg)
        return

    def save_vol(self, vol):
        volkey = self.volumeroot + vol['id']
        volval = json.dumps(vol)
        try:
            self.client.write(volkey, volval)
        except Exception as ex:
            msg = 'Failed to save volume to ETCD: %s'\
                  % six.text_type(ex)
            LOG.error(msg)
            raise exception.HPEPluginSaveFailed(obj=vol['display_name'])
        else:
            LOG.info('Write key: %s to etc, value is: %s', volkey, volval)

    def update_vol(self, volid, key, val):
        volkey = self.volumeroot + volid
        result = self.client.read(volkey)
        volval = json.loads(result.value)
        volval[key] = val
        volval = json.dumps(volval)
        result.value = volval
        self.client.update(result)

        LOG.info(_LI('Update key: %s to etcd, value is: %s'), volkey, volval)

    def delete_vol(self, vol):
        volkey = self.volumeroot + vol['id']

        self.client.delete(volkey)
        LOG.info(_LI('Deleted key: %s from etcd'), volkey)

    def get_lock(self, lock_type):
        # By default this is volume lock-root
        lock_root = LOCKROOT
        if lock_type == 'RCG':
            lock_root = RCG_LOCKROOT
        return EtcdLock(lock_root + '/', self.client)

    def get_vol_byname(self, volname):
        volumes = self.client.read(self.volumeroot, recursive=True)
        LOG.info(_LI('Get volbyname: volname is %s'), volname)

        for child in volumes.children:
            if child.key != VOLUMEROOT:
                volmember = json.loads(child.value)
                vol = volmember['display_name']
                if vol.startswith(volname, 0, len(volname)):
                    if volmember['display_name'] == volname:
                        return volmember
                elif volmember['name'] == volname:
                    return volmember
        return None

    def get_vol_by_id(self, volid):
        volkey = self.volumeroot + volid
        result = self.client.read(volkey)
        return json.loads(result.value)

    def get_all_vols(self):
        ret_vol_list = []
        volumes = self.client.read(self.volumeroot, recursive=True)
        for volinfo in volumes.children:
            if volinfo.key != VOLUMEROOT:
                vol = json.loads(volinfo.value)
                ret_vol_list.append(vol)
        return ret_vol_list

    def get_vol_path_info(self, volname):
        vol = self.get_vol_byname(volname)
        if vol:
            if 'path_info' in vol and vol['path_info'] is not None:
                path_info = json.loads(vol['path_info'])
                return path_info
        return None

    def get_path_info_from_vol(self, vol):
        if vol:
            if 'path_info' in vol and vol['path_info'] is not None:
                return json.loads(vol['path_info'])
        return None

    def get_backend_key(self, backend):
        passphrase = self.backendroot + backend
        result = self.client.read(passphrase)
        return result.value


class EtcdLock(object):
    def __init__(self, lock_root, client):
        self._lock_root = lock_root
        self._client = client

    def try_lock_name(self, name):
        try:
            LOG.debug("Try locking name %s", name)
            self._client.write(self._lock_root + name, name,
                               prevExist=False)
            LOG.debug("Name is locked : %s", name)
        except Exception as ex:
            msg = 'Name: %(name)s is already locked' % {'name': name}
            LOG.exception(msg)
            LOG.exception(ex)
            raise exception.HPEPluginLockFailed(obj=name)

    def try_unlock_name(self, name):
        try:
            LOG.debug("Try unlocking name %s", name)
            self._client.delete(self._lock_root + name)
            LOG.debug("Name is unlocked : %s", name)
        except Exception as ex:
            msg = 'Name: %(name)s unlock failed' % {'name': name}
            LOG.exception(msg)
            LOG.exception(ex)
            raise exception.HPEPluginUnlockFailed(obj=name)
