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

SHAREROOT = '/shares'
FILEPERSONAROOT = '/file-persona'

SHARE_LOCKROOT = "/share-lock"
FILE_BACKEND_LOCKROOT = "/fp-backend-lock"
FILE_CPG_LOCKROOT = "/fp-cpg-lock"
FILE_FPG_LOCKROOT = "/fp-fpg-lock"


class HpeEtcdClient(object):

    def __init__(self, host, port, client_cert, client_key):
        self.host = host
        self.port = port

        LOG.info('HpeEtcdClient datatype of host is %s ' % type(self.host))
        host_tuple = ()
        if isinstance(self.host, str):
            if ',' in self.host:
                host_list = [h.strip() for h in host.split(',')]

                for i in host_list:
                    temp_tuple = (i.split(':')[0], int(i.split(':')[1]))
                    host_tuple = host_tuple + (temp_tuple,)

                host_tuple = tuple(host_tuple)

        LOG.info('HpeEtcdClient host_tuple is %s, host is %s ' %
                 (host_tuple, self.host))

        if client_cert is not None and client_key is not None:
            if len(host_tuple) > 0:
                LOG.info('HpeEtcdClient host tuple is not None')
                self.client = etcd.Client(host=host_tuple, port=port,
                                          protocol='https',
                                          cert=(client_cert, client_key),
                                          allow_reconnect=True)
            else:
                LOG.info('HpeEtcdClient host %s ' % host)
                self.client = etcd.Client(host=host, port=port,
                                          protocol='https',
                                          cert=(client_cert, client_key))
        else:
            LOG.info('HpeEtcdClient no certs')
            if len(host_tuple) > 0:
                LOG.info('Use http protocol')
                self.client = etcd.Client(host=host_tuple, port=port,
                                          protocol='http',
                                          allow_reconnect=True)
            else:
                self.client = etcd.Client(host, port)

    def make_root(self, root):
        try:
            self.client.read(root)
        except etcd.EtcdKeyNotFound:
            self.client.write(root, None, dir=True)
        except Exception as ex:
            msg = (_('Could not init HpeEtcdClient: %s'), six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMakeEtcdRootException(reason=msg)
        return

    def save_object(self, etcd_key, obj):
        val = json.dumps(obj)
        try:
            self.client.write(etcd_key, val)
        except Exception as ex:
            msg = 'Failed to save object to ETCD: %s'\
                  % six.text_type(ex)
            LOG.error(msg)
            raise exception.HPEPluginSaveFailed(obj=obj)
        else:
            LOG.info('Write key: %s to ETCD, value is: %s', etcd_key, val)

    def update_object(self, etcd_key, key_to_update, val):
        result = self.client.read(etcd_key)
        val = json.loads(result.value)
        val[key_to_update] = val
        val = json.dumps(val)
        result.value = val
        self.client.update(result)
        LOG.info(_LI('Update key: %s to ETCD, value is: %s'), etcd_key, val)

    def delete_object(self, etcd_key):
        try:
            self.client.delete(etcd_key)
            LOG.info(_LI('Deleted key: %s from ETCD'), etcd_key)
        except etcd.EtcdKeyNotFound:
            msg = "Key to delete not found ETCD: [key=%s]" % etcd_key
            LOG.info(msg)
            raise exception.EtcdMetadataNotFound(msg=msg)
        except Exception as ex:
            msg = "Unknown error encountered: %s" % six.text_type(ex)
            LOG.info(msg)
            raise exception.HPEPluginEtcdException(reason=msg)

    def get_object(self, etcd_key):
        try:
            result = self.client.read(etcd_key)
            return json.loads(result.value)
        except etcd.EtcdKeyNotFound:
            msg = "Key not found ETCD: [key=%s]" % etcd_key
            LOG.info(msg)
            raise exception.EtcdMetadataNotFound(msg)
        except Exception as ex:
            msg = 'Failed to read key %s: Msg: %s' %\
                  (etcd_key, six.text_type(ex))
            LOG.error(msg)
            raise exception.EtcdUnknownException(reason=msg)

    def get_objects(self, root):
        ret_list = []
        objects = self.client.read(root, recursive=True)
        for obj in objects.children:
            if obj.key != root:
                ret_obj = json.loads(obj.value)
                ret_list.append(ret_obj)
        return ret_list

    def get_value(self, key):
        result = self.client.read(key)
        return result.value


# Manages File Persona metadata under /file-persona key
class HpeFilePersonaEtcdClient(object):
    def __init__(self, host, port, client_cert, client_key):
        self._client = HpeEtcdClient(host, port,
                                     client_cert, client_key)
        self._client.make_root(FILEPERSONAROOT)
        self._root = FILEPERSONAROOT

    def create_cpg_entry(self, backend, cpg):
        etcd_key = '/'.join([self._root, backend, cpg])
        try:
            self._client.read(etcd_key)
        except etcd.EtcdKeyNotFound:
            self._client.write(etcd_key, None, dir=True)
            return True
        except Exception as ex:
            msg = (_('Could not init HpeEtcdClient: %s'), six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMakeEtcdRootException(reason=msg)
        return False

    def delete_cpg_entry(self, backend, cpg):
        etcd_key = '/'.join([self._root, backend, cpg])
        self._client.delete_object(etcd_key)

    def save_fpg_metadata(self, backend, cpg, fpg, fp_metadata):
        etcd_key = '/'.join([self._root, backend, cpg, fpg])
        self._client.save_object(etcd_key, fp_metadata)

    def update_fpg_metadata(self, backend, cpg, fpg, key, val):
        etcd_key = '/'.join([self._root, backend, cpg, fpg])
        self._client.update_object(etcd_key, key, val)

    def delete_fpg_metadata(self, backend, cpg, fpg):
        etcd_key = '/'.join([self._root, backend, cpg, fpg])
        self._client.delete_object(etcd_key)

    def get_fpg_metadata(self, backend, cpg, fpg):
        etcd_key = '/'.join([self._root, backend, cpg, fpg])
        return self._client.get_object(etcd_key)

    def get_all_fpg_metadata(self, backend, cpg):
        etcd_key = '%s/%s/%s' % (self._root, backend, cpg)
        return self._client.get_objects(etcd_key)

    def save_backend_metadata(self, backend, metadata):
        etcd_key = '%s/%s.metadata' % (self._root, backend)
        self._client.save_object(etcd_key, metadata)

    def update_backend_metadata(self, backend, key, val):
        etcd_key = '%s/%s.metadata' % (self._root, backend)
        self._client.update_object(etcd_key, key, val)

    def delete_backend_metadata(self, backend):
        etcd_key = '%s/%s.metadata' % (self._root, backend)
        self._client.delete_object(etcd_key)

    def get_backend_metadata(self, backend):
        etcd_key = '%s/%s.metadata' % (self._root, backend)
        return self._client.get_object(etcd_key)

    def get_lock(self, lock_type, name=None):
        lockroot_map = {
            'FP_BACKEND': FILE_BACKEND_LOCKROOT,
            'FP_FPG': FILE_FPG_LOCKROOT
        }
        lock_root = lockroot_map.get(lock_type)
        if lock_root:
            return EtcdLock(lock_root + '/', self._client.client, name)
        raise exception.EtcdInvalidLockType(type=lock_type)

    def get_file_backend_lock(self, backend):
        return EtcdLock(FILE_BACKEND_LOCKROOT + '/', self._client.client,
                        name=backend)

    def get_cpg_lock(self, backend, cpg):
        lock_key = '/'.join([backend, cpg])
        return EtcdLock(FILE_CPG_LOCKROOT + '/', self._client.client,
                        name=lock_key)

    def get_fpg_lock(self, backend, cpg, fpg):
        lock_key = '/'.join([backend, cpg, fpg])
        return EtcdLock(FILE_FPG_LOCKROOT + '/', self._client.client,
                        name=lock_key)


class HpeShareEtcdClient(object):

    def __init__(self, host, port, client_cert, client_key):
        self._client = HpeEtcdClient(host, port,
                                     client_cert, client_key)
        self._client.make_root(SHAREROOT)
        self._root = SHAREROOT + '/'

        self._client.make_root(BACKENDROOT)
        self.backendroot = BACKENDROOT + '/'

    def save_share(self, share):
        etcd_key = self._root + share['name']
        self._client.save_object(etcd_key, share)

    def update_share(self, name, key, val):
        etcd_key = self._root + name
        self._client.update_object(etcd_key, key, val)

    def delete_share(self, share_name):
        etcd_key = self._root + share_name
        self._client.delete_object(etcd_key)

    def get_share(self, name):
        etcd_key = self._root + name
        return self._client.get_object(etcd_key)

    def get_all_shares(self):
        return self._client.get_objects(SHAREROOT)

    def get_lock(self, lock_type, name=None):
        return EtcdLock(SHARE_LOCKROOT + '/', self._client.client, name=name)

    def get_backend_key(self, backend):
        passphrase = self.backendroot + backend
        return self._client.get_value(passphrase)


# TODO: Eventually this will take over and EtcdUtil will be phased out
class HpeVolumeEtcdClient(object):

    def __init__(self, host, port, client_cert, client_key):
        self._client = HpeEtcdClient(host, port,
                                     client_cert, client_key)
        self._client.make_root(VOLUMEROOT)
        self._root = VOLUMEROOT + '/'

        self._client.make_root(BACKENDROOT)
        self.backendroot = BACKENDROOT + '/'

    def save_vol(self, vol):
        etcd_key = self._root + vol['id']
        self._client.save_object(etcd_key, vol)

    def update_vol(self, volid, key, val):
        etcd_key = self._root + volid
        self._client.update_object(etcd_key, key, val)

    def delete_vol(self, vol):
        etcd_key = self._root + vol['id']
        self._client.delete_object(etcd_key)

    def get_vol_byname(self, volname):
        volumes = self._client.get_objects(self._root)
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
        etcd_key = self._root + volid
        return self._client.get_object(etcd_key)

    def get_all_vols(self):
        return self._client.get_objects(VOLUMEROOT)

    def get_vol_path_info(self, volname):
        vol = self.get_vol_byname(volname)
        if vol:
            if 'path_info' in vol and vol['path_info'] is not None:
                path_info = json.loads(vol['path_info'])
                return path_info
            if 'mount_path_dict' in vol:
                return vol['mount_path_dict']
        return None

    def get_path_info_from_vol(self, vol):
        if vol:
            if 'path_info' in vol and vol['path_info'] is not None:
                return json.loads(vol['path_info'])
            if 'share_path_info' in vol:
                return vol['share_path_info']
        return None

    def get_lock(self, lock_type):
        # By default this is volume lock-root
        lockroot_map = {'VOL': LOCKROOT,
                        'RCG': RCG_LOCKROOT}
        lock_root = lockroot_map.get(lock_type)
        if lock_root:
            return EtcdLock(lock_root + '/', self._client.client)
        raise exception.EtcdInvalidLockType(type=lock_type)

    def get_backend_key(self, backend):
        passphrase = self.backendroot + backend
        return self._client.get_value(passphrase)


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
    # To use this class with "with" clause, passing
    # name is MUST
    def __init__(self, lock_root, client, name=None):
        self._lock_root = lock_root
        self._client = client
        self._name = name

    def __enter__(self):
        if self._name:
            self.try_lock_name(self._name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._name:
            self.try_unlock_name(self._name)

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
