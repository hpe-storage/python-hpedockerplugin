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
from i18n import _, _LI
import exception

LOG = logging.getLogger(__name__)

VOLUMEROOT = '/volumes'
LOCKROOT = '/volumes-lock'


class EtcdUtil(object):

    def __init__(self, host, port, client_cert, client_key):
        self.host = host
        self.port = port

        LOG.info('ETCDUTIL datatype of host is %s ' % type(self.host))
        host_tuple = ()
        if isinstance(self.host, basestring):
          if ',' in self.host:
            host_list = [ h.strip() for h in host.split(',') ]

            for i in host_list:
              temp_tuple = (  i.split(':')[0] , int(i.split(':')[1]) )
              host_tuple = host_tuple + (temp_tuple,)

            host_tuple  = tuple(host_tuple)

        LOG.info('ETCDUTIL host_tuple is %s, host is %s ' % (host_tuple, self.host))

        self.volumeroot = VOLUMEROOT + '/'
        self.lockroot = LOCKROOT + '/'
        if client_cert is not None and client_key is not None:
            if len(host_tuple) > 0:
               LOG.info('ETCDUTIL host tuple is not None')
               self.client = etcd.Client(host=host_tuple, port=port, protocol='https',
                                      cert=(client_cert, client_key), allow_reconnect=True)
            else:
               LOG.info('ETCDUTIL host %s ' % host)
               self.client = etcd.Client(host=host, port=port, protocol='https',
                                      cert=(client_cert, client_key))
        else:
            LOG.info('ETCDUTIL no certs')
            if len(host_tuple) > 0:
               LOG.info('Use http protocol')
               self.client = etcd.Client(host=host_tuple, port=port,
                              protocol='http', allow_reconnect=True)
            else:
               self.client = etcd.Client(host, port)
        self._make_root()

    def _make_root(self):
        try:
            self.client.read(VOLUMEROOT)
        except etcd.EtcdKeyNotFound:
            self.client.write(VOLUMEROOT, None, dir=True)
        except Exception as ex:
            msg = (_('Could not init EtcUtil: %s'), six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMakeEtcdRootException(reason=msg)
        return

    def save_vol(self, vol):
        volkey = self.volumeroot + vol['id']
        volval = json.dumps(vol)

        self.client.write(volkey, volval)
        LOG.info(_LI('Write key: %s to etc, value is: %s'), volkey, volval)

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

    def _get_vol_byuuid(self, voluuid):
        volkey = self.volumeroot + voluuid
        result = self.client.read(volkey)

        volval = json.loads(result.value)
        LOG.info(_LI('Read key: %s from etcd, result is: %s'), volkey, volval)
        return volval

    def try_lock_volname(self, volname):
        self.client.write(self.lockroot + volname, volname, prevExist=False)

    def try_unlock_volname(self, volname):
        self.client.delete(self.lockroot + volname)

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

    def get_all_vols(self):
        volumes = self.client.read(self.volumeroot, recursive=True)
        return volumes

    def get_vol_path_info(self, volname):
        vol = self.get_vol_byname(volname)
        if vol:
            if 'path_info' in vol and vol['path_info'] is not None:
                path_info = json.loads(vol['path_info'])
                return path_info
        return None

    def get_path_info_from_vol(self, vol):
        if vol:
            info = json.loads(vol)
            if 'path_info' in info and info['path_info'] is not None:
                return json.loads(info['path_info'])
        return None
