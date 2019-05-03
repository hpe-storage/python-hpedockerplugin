# Copyright 2015 Hewlett Packard Enterprise Development LP
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""HPE 3PAR Mediator for OpenStack Manila.
This 'mediator' de-couples the 3PAR focused client from the OpenStack focused
driver.
"""
import sh
import six

from oslo_log import log
from oslo_service import loopingcall
from oslo_utils import importutils
from oslo_utils import units

from hpedockerplugin import exception
from hpedockerplugin.i18n import _
from hpedockerplugin import fileutil

hpe3parclient = importutils.try_import("hpe3parclient")
if hpe3parclient:
    from hpe3parclient import file_client

LOG = log.getLogger(__name__)
MIN_CLIENT_VERSION = (4, 0, 0)
DENY = '-'
ALLOW = '+'
FULL = 1
THIN = 2
DEDUPE = 6
ENABLED = 1
DISABLED = 2
CACHE = 'cache'
CONTINUOUS_AVAIL = 'continuous_avail'
ACCESS_BASED_ENUM = 'access_based_enum'
SMB_EXTRA_SPECS_MAP = {
    CACHE: CACHE,
    CONTINUOUS_AVAIL: 'ca',
    ACCESS_BASED_ENUM: 'abe',
}
IP_ALREADY_EXISTS = 'IP address %s already exists'
USER_ALREADY_EXISTS = '"allow" permission already exists for "%s"'
DOES_NOT_EXIST = 'does not exist, cannot'
LOCAL_IP = '127.0.0.1'
LOCAL_IP_RO = '127.0.0.2'
SUPER_SHARE = 'DOCKER_SUPER_SHARE'
TMP_RO_SNAP_EXPORT = "Temp RO snapshot export as source for creating RW share."


class HPE3ParMediator(object):
    """3PAR client-facing code for the 3PAR driver.
    Version history:
        1.0.0 - Begin Liberty development (post-Kilo)
        1.0.1 - Report thin/dedup/hp_flash_cache capabilities
        1.0.2 - Add share server/share network support
        1.0.3 - Use hp3par prefix for share types and capabilities
        2.0.0 - Rebranded HP to HPE
        2.0.1 - Add access_level (e.g. read-only support)
        2.0.2 - Add extend/shrink
        2.0.3 - Fix SMB read-only access (added in 2.0.1)
        2.0.4 - Remove file tree on delete when using nested shares #1538800
        2.0.5 - Reduce the fsquota by share size
                when a share is deleted #1582931
        2.0.6 - Read-write share from snapshot (using driver mount and copy)
        2.0.7 - Add update_access support
        2.0.8 - Multi pools support per backend
        2.0.9 - Fix get_vfs() to correctly validate conf IP addresses at
                boot up #1621016
    """

    VERSION = "2.0.9"

    def __init__(self, host_config, config):
        self._host_config = host_config
        self._config = config
        self._client = None
        self.client_version = None

    @staticmethod
    def no_client():
        return hpe3parclient is None

    def do_setup(self, timeout=30):

        if self.no_client():
            msg = _('You must install hpe3parclient before using the 3PAR '
                    'driver. Run "pip install --upgrade python-3parclient" '
                    'to upgrade the hpe3parclient.')
            LOG.error(msg)
            raise exception.HPE3ParInvalidClient(message=msg)

        self.client_version = hpe3parclient.version_tuple
        if self.client_version < MIN_CLIENT_VERSION:
            msg = (_('Invalid hpe3parclient version found (%(found)s). '
                     'Version %(minimum)s or greater required. Run "pip'
                     ' install --upgrade python-3parclient" to upgrade'
                     ' the hpe3parclient.') %
                   {'found': '.'.join(map(six.text_type, self.client_version)),
                    'minimum': '.'.join(map(six.text_type,
                                            MIN_CLIENT_VERSION))})
            LOG.error(msg)
            raise exception.HPE3ParInvalidClient(message=msg)

        try:
            self._client = file_client.HPE3ParFilePersonaClient(
                self._config.hpe3par_api_url)
        except Exception as e:
            msg = (_('Failed to connect to HPE 3PAR File Persona Client: %s') %
                   six.text_type(e))
            LOG.exception(msg)
            raise exception.ShareBackendException(message=msg)

        try:
            ssh_kwargs = {}
            if self._config.san_ssh_port:
                ssh_kwargs['port'] = self._config.san_ssh_port
            if self._config.ssh_conn_timeout:
                ssh_kwargs['conn_timeout'] = self._config.ssh_conn_timeout
            if self._config.san_private_key:
                ssh_kwargs['privatekey'] = \
                    self._config.san_private_key

            self._client.setSSHOptions(
                self._config.san_ip,
                self._config.san_login,
                self._config.san_password,
                **ssh_kwargs
            )

        except Exception as e:
            msg = (_('Failed to set SSH options for HPE 3PAR File Persona '
                     'Client: %s') % six.text_type(e))
            LOG.exception(msg)
            raise exception.ShareBackendException(message=msg)

        LOG.info("HPE3ParMediator %(version)s, "
                 "hpe3parclient %(client_version)s",
                 {"version": self.VERSION,
                  "client_version": hpe3parclient.get_version_string()})

        try:
            wsapi_version = self._client.getWsApiVersion()['build']
            LOG.info("3PAR WSAPI %s", wsapi_version)
        except Exception as e:
            msg = (_('Failed to get 3PAR WSAPI version: %s') %
                   six.text_type(e))
            LOG.exception(msg)
            raise exception.ShareBackendException(message=msg)

        if self._config.hpe3par_debug:
            self._client.debug_rest(True)  # Includes SSH debug (setSSH above)

    def _wsapi_login(self):
        try:
            self._client.login(self._config.hpe3par_username,
                               self._config.hpe3par_password)
        except Exception as e:
            msg = (_("Failed to Login to 3PAR (%(url)s) as %(user)s "
                     "because: %(err)s") %
                   {'url': self._config.hpe3par_api_url,
                    'user': self._config.hpe3par_username,
                    'err': six.text_type(e)})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

    def _wsapi_logout(self):
        try:
            self._client.http.unauthenticate()
        except Exception as e:
            msg = ("Failed to Logout from 3PAR (%(url)s) because %(err)s")
            LOG.warning(msg, {'url': self._config.hpe3par_api_url,
                              'err': six.text_type(e)})
            # don't raise exception on logout()

    @staticmethod
    def build_export_locations(protocol, ips, path):

        if not ips:
            message = _('Failed to build export location due to missing IP.')
            raise exception.InvalidInput(reason=message)

        if not path:
            message = _('Failed to build export location due to missing path.')
            raise exception.InvalidInput(reason=message)

        share_proto = HPE3ParMediator.ensure_supported_protocol(protocol)
        if share_proto == 'nfs':
            return ['%s:%s' % (ip, path) for ip in ips]
        else:
            return [r'\\%s\%s' % (ip, path) for ip in ips]

    def get_provisioned_gb(self, fpg):
        total_mb = 0
        try:
            result = self._client.getfsquota(fpg=fpg)
        except Exception as e:
            result = {'message': six.text_type(e)}

        error_msg = result.get('message')
        if error_msg:
            message = (_('Error while getting fsquotas for FPG '
                         '%(fpg)s: %(msg)s') %
                       {'fpg': fpg, 'msg': error_msg})
            LOG.error(message)
            raise exception.ShareBackendException(msg=message)

        for fsquota in result['members']:
            total_mb += float(fsquota['hardBlock'])
        return total_mb / units.Ki

    def get_fpg(self, fpg_name):
        try:
            self._wsapi_login()
            uri = '/fpgs?query="name EQ %s"' % fpg_name
            resp, body = self._client.http.get(uri)
            if not body['members']:
                LOG.info("FPG %s not found" % fpg_name)
                raise exception.FpgNotFound(fpg=fpg_name)
            return body['members'][0]
        finally:
            self._wsapi_logout()

    def get_vfs(self, fpg_name):
        try:
            self._wsapi_login()
            uri = '/virtualfileservers?query="fpg EQ %s"' % fpg_name
            resp, body = self._client.http.get(uri)
            if not body['members']:
                msg = "VFS for FPG %s not found" % fpg_name
                LOG.info(msg)
                raise exception.ShareBackendException(msg=msg)
            return body['members'][0]
        finally:
            self._wsapi_logout()

    def get_fpg_status(self, fpg):
        """Get capacity and capabilities for FPG."""

        try:
            result = self._client.getfpg(fpg)
        except Exception as e:
            msg = (_('Failed to get capacity for fpg %(fpg)s: %(e)s') %
                   {'fpg': fpg, 'e': six.text_type(e)})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

        if result['total'] != 1:
            msg = (_('Failed to get capacity for fpg %s.') % fpg)
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

        member = result['members'][0]
        total_capacity_gb = float(member['capacityKiB']) / units.Mi
        free_capacity_gb = float(member['availCapacityKiB']) / units.Mi

        volumes = member['vvs']
        if isinstance(volumes, list):
            volume = volumes[0]  # Use first name from list
        else:
            volume = volumes  # There is just a name

        self._wsapi_login()
        try:
            volume_info = self._client.getVolume(volume)
            volume_set = self._client.getVolumeSet(fpg)
        finally:
            self._wsapi_logout()

        provisioning_type = volume_info['provisioningType']
        if provisioning_type not in (THIN, FULL, DEDUPE):
            msg = (_('Unexpected provisioning type for FPG %(fpg)s: '
                     '%(ptype)s.') % {'fpg': fpg, 'ptype': provisioning_type})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

        dedupe = provisioning_type == DEDUPE
        thin_provisioning = provisioning_type in (THIN, DEDUPE)

        flash_cache_policy = volume_set.get('flashCachePolicy', DISABLED)
        hpe3par_flash_cache = flash_cache_policy == ENABLED

        status = {
            'pool_name': fpg,
            'total_capacity_gb': total_capacity_gb,
            'free_capacity_gb': free_capacity_gb,
            'thin_provisioning': thin_provisioning,
            'dedupe': dedupe,
            'hpe3par_flash_cache': hpe3par_flash_cache,
            'hp3par_flash_cache': hpe3par_flash_cache,
        }

        if thin_provisioning:
            status['provisioned_capacity_gb'] = self.get_provisioned_gb(fpg)

        return status

    @staticmethod
    def ensure_supported_protocol(share_proto):
        protocol = share_proto.lower()
        if protocol == 'cifs':
            protocol = 'smb'
        if protocol not in ['smb', 'nfs']:
            message = (_('Invalid protocol. Expected nfs or smb. Got %s.') %
                       protocol)
            LOG.error(message)
            raise exception.InvalidShareAccess(reason=message)
        return protocol

    @staticmethod
    def other_protocol(share_proto):
        """Given 'nfs' or 'smb' (or equivalent) return the other one."""
        protocol = HPE3ParMediator.ensure_supported_protocol(share_proto)
        return 'nfs' if protocol == 'smb' else 'smb'

    @staticmethod
    def ensure_prefix(uid, protocol=None, readonly=False):
        if uid.startswith('osf-'):
            return uid

        if protocol:
            proto = '-%s' % HPE3ParMediator.ensure_supported_protocol(protocol)
        else:
            proto = ''

        if readonly:
            ro = '-ro'
        else:
            ro = ''

        # Format is osf[-ro]-{nfs|smb}-uid
        return 'osf%s%s-%s' % (proto, ro, uid)

    @staticmethod
    def _get_nfs_options(proto_opts, readonly):
        """Validate the NFS extra_specs and return the options to use."""

        nfs_options = proto_opts
        if nfs_options:
            options = nfs_options.split(',')
        else:
            options = []

        # rw, ro, and (no)root_squash (in)secure options are not allowed in
        # extra_specs because they will be forcibly set below.
        # no_subtree_check and fsid are not allowed per 3PAR support.
        # Other strings will be allowed to be sent to the 3PAR which will do
        # further validation.
        options_not_allowed = ['ro', 'rw',
                               'no_root_squash', 'root_squash',
                               'secure', 'insecure',
                               'no_subtree_check', 'fsid']

        invalid_options = [
            option for option in options if option in options_not_allowed
        ]

        if invalid_options:
            raise exception.InvalidInput(_('Invalid hp3par:nfs_options or '
                                           'hpe3par:nfs_options in '
                                           'extra-specs. The following '
                                           'options are not allowed: %s') %
                                         invalid_options)

        options.append('ro' if readonly else 'rw')
        options.append('no_root_squash')
        # options.append('insecure')
        options.append('secure')

        return ','.join(options)

    def delete_file_store(self, fpg_name, fstore_name):
        try:
            self._wsapi_login()
            query = '/filestores?query="name EQ %s AND fpg EQ %s"' %\
                    (fstore_name, fpg_name)
            body, fstore = self._client.http.get(query)
            if body['status'] == '200' and fstore['total'] == 1:
                fstore_id = fstore['members'][0]['id']
                del_uri = '/filestores/%s' % fstore_id
                self._client.http.delete(del_uri)
        except Exception:
            msg = (_('ERROR: File store deletion failed: [fstore: %s,'
                     'fpg:%s') % (fstore_name, fpg_name))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def delete_fpg(self, fpg_name):
        try:
            self._wsapi_login()
            query = '/fpgs?query="name EQ %s"' % fpg_name
            resp, body = self._client.http.get(query)
            if resp['status'] == '200' and body['total'] == 1:
                fpg_id = body['members'][0]['id']
                del_uri = '/fpgs/%s' % fpg_id
                resp, body = self._client.http.delete(del_uri)
                if resp['status'] == '202':
                    task_id = body['taskId']
                    self._wait_for_task_completion(task_id, 10)
        except Exception:
            msg = (_('ERROR: FPG deletion failed: [fpg: %s,') % fpg_name)
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def update_capacity_quotas(self, fstore, size, fpg, vfs):

        def _sync_update_capacity_quotas(fstore, new_size, fpg, vfs):
            """Update 3PAR quotas and return setfsquota output."""

            hcapacity = new_size
            scapacity = hcapacity
            uri = '/filepersonaquotas/'
            req_body = {
                'name': fstore,
                'type': 3,
                'vfs': vfs,
                'fpg': fpg,
                'softBlockMiB': scapacity,
                'hardBlockMiB': hcapacity
            }
            return self._client.http.post(uri, body=req_body)

        try:
            resp, body = _sync_update_capacity_quotas(
                fstore, size, fpg, vfs)
            if resp['status'] != '201':
                msg = (_('Failed to update capacity quota '
                         '%(size)s on %(fstore)s') %
                       {'size': size,
                        'fstore': fstore})
                LOG.error(msg)
                raise exception.ShareBackendException(msg=msg)

            href = body['links'][0]['href']
            uri, quota_id = href.split('filepersonaquotas/')

            LOG.debug("Quota successfully set: resp=%s, body=%s"
                      % (resp, body))
            return quota_id
        except Exception as e:
            msg = (_('Failed to update capacity quota '
                     '%(size)s on %(fstore)s with exception: %(e)s') %
                   {'size': size,
                    'fstore': fstore,
                    'e': six.text_type(e)})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

    def remove_quota(self, quota_id):
        uri = '/filepersonaquotas/%s' % quota_id
        try:
            self._wsapi_login()
            self._client.http.delete(uri)
        except Exception as ex:
            msg = "mediator:remove_quota - failed to remove quota %s" \
                  "at the backend. Exception: %s" % \
                  (quota_id, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def _parse_protocol_opts(self, proto_opts):
        ret_opts = {}
        opts = proto_opts.split(',')
        for opt in opts:
            key, value = opt.split('=')
            ret_opts[key] = value
        return ret_opts

    def _create_share(self, share_details):
        fpg_name = share_details['fpg']
        vfs_name = share_details['vfs']
        share_name = share_details['name']
        proto_opts = share_details['nfsOptions']
        readonly = share_details['readonly']

        args = {
            'name': share_name,
            'type': 1,
            'vfs': vfs_name,
            'fpg': fpg_name,
            'shareDirectory': None,
            'fstore': None,
            'nfsOptions': self._get_nfs_options(proto_opts, readonly),
            'nfsClientlist': ['127.0.0.1'],
            'comment': 'Docker created share'
        }

        try:
            uri = '/fileshares/'
            resp, body = self._client.http.post(uri, body=args)
            if resp['status'] != '201':
                msg = (_('Failed to create share %(resp)s, %(body)s') %
                       {'resp': resp, 'body': body})
                LOG.exception(msg)
                raise exception.ShareBackendException(msg=msg)

            href = body['links'][0]['href']
            uri, share_id = href.split('fileshares/')
            LOG.debug("Share created successfully: %s" % body)
            return share_id
        except Exception as e:
            msg = (_('Failed to create share %(share_name)s: %(e)s') %
                   {'share_name': share_name, 'e': six.text_type(e)})
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)

    def create_share(self, share_details):
        """Create the share and return its path.
        This method can create a share when called by the driver or when
        called locally from create_share_from_snapshot().  The optional
        parameters allow re-use.
        :param share_id: The share-id with or without osf- prefix.
        :param share_proto: The protocol (to map to smb or nfs)
        :param fpg: The file provisioning group
        :param vfs:  The virtual file system
        :param fstore:  (optional) The file store.  When provided, an existing
        file store is used.  Otherwise one is created.
        :param sharedir: (optional) Share directory.
        :param readonly: (optional) Create share as read-only.
        :param size: (optional) Size limit for file store if creating one.
        :param comment: (optional) Comment to set on the share.
        :param client_ip: (optional) IP address to give access to.
        :return: share path string
        """
        try:
            self._wsapi_login()
            return self._create_share(share_details)
        finally:
            self._wsapi_logout()

    def _delete_share(self, share_name, protocol, fpg, vfs, fstore):
        try:
            self._client.removefshare(
                protocol, vfs, share_name, fpg=fpg, fstore=fstore)

        except Exception as e:
            msg = (_('Failed to remove share %(share_name)s: %(e)s') %
                   {'share_name': share_name, 'e': six.text_type(e)})
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)

    def _delete_ro_share(self, project_id, share_id, protocol,
                         fpg, vfs, fstore):
        share_name_ro = self.ensure_prefix(share_id, readonly=True)
        if not fstore:
            fstore = self._find_fstore(project_id,
                                       share_name_ro,
                                       protocol,
                                       fpg,
                                       vfs,
                                       allow_cross_protocol=True)
        if fstore:
            self._delete_share(share_name_ro, protocol, fpg, vfs, fstore)
        return fstore

    def delete_share(self, share_id):
        LOG.info("Mediator:delete_share %s: Entering..." % share_id)
        uri = '/fileshares/%s' % share_id
        try:
            self._wsapi_login()
            self._client.http.delete(uri)
        except Exception as ex:
            msg = "mediator:delete_share - failed to remove share %s" \
                  "at the backend. Exception: %s" % \
                  (share_id, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def _create_mount_directory(self, mount_location):
        try:
            fileutil.execute('mkdir', mount_location, run_as_root=True)
        except Exception as err:
            message = ("There was an error creating mount directory: "
                       "%s. The nested file tree will not be deleted.",
                       six.text_type(err))
            LOG.warning(message)

    def _mount_share(self, protocol, export_location, mount_dir):
        if protocol == 'nfs':
            sh.mount('-t', 'nfs', export_location, mount_dir)
            # cmd = ('mount', '-t', 'nfs', export_location, mount_dir)
            # fileutil.execute(*cmd)

    def _unmount_share(self, mount_location):
        try:
            sh.umount(mount_location)
            # fileutil.execute('umount', mount_location, run_as_root=True)
        except Exception as err:
            message = ("There was an error unmounting the share at "
                       "%(mount_location)s: %(error)s")
            msg_data = {
                'mount_location': mount_location,
                'error': six.text_type(err),
            }
            LOG.warning(message, msg_data)

    def _delete_share_directory(self, directory):
        try:
            sh.rm('-rf', directory)
            # fileutil.execute('rm', '-rf', directory, run_as_root=True)
        except Exception as err:
            message = ("There was an error removing the share: "
                       "%s. The nested file tree will not be deleted.",
                       six.text_type(err))
            LOG.warning(message)

    def _generate_mount_path(self, fpg, vfs, fstore, share_ip):
        path = (("%(share_ip)s:/%(fpg)s/%(vfs)s/%(fstore)s") %
                {'share_ip': share_ip,
                 'fpg': fpg,
                 'vfs': vfs,
                 'fstore': fstore})
        return path

    @staticmethod
    def _is_share_from_snapshot(fshare):

        path = fshare.get('shareDir')
        if path:
            return '.snapshot' in path.split('/')

        path = fshare.get('sharePath')
        return path and '.snapshot' in path.split('/')

    def create_snapshot(self, orig_project_id, orig_share_id, orig_share_proto,
                        snapshot_id, fpg, vfs):
        """Creates a snapshot of a share."""

        fshare = self._find_fshare(orig_project_id,
                                   orig_share_id,
                                   orig_share_proto,
                                   fpg,
                                   vfs)

        if not fshare:
            msg = (_('Failed to create snapshot for FPG/VFS/fshare '
                     '%(fpg)s/%(vfs)s/%(fshare)s: Failed to find fshare.') %
                   {'fpg': fpg, 'vfs': vfs, 'fshare': orig_share_id})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

        if self._is_share_from_snapshot(fshare):
            msg = (_('Failed to create snapshot for FPG/VFS/fshare '
                     '%(fpg)s/%(vfs)s/%(fshare)s: Share is a read-only '
                     'share of an existing snapshot.') %
                   {'fpg': fpg, 'vfs': vfs, 'fshare': orig_share_id})
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

        fstore = fshare.get('fstoreName')
        snapshot_tag = self.ensure_prefix(snapshot_id)
        try:
            result = self._client.createfsnap(
                vfs, fstore, snapshot_tag, fpg=fpg)

            LOG.debug("createfsnap result=%s", result)

        except Exception as e:
            msg = (_('Failed to create snapshot for FPG/VFS/fstore '
                     '%(fpg)s/%(vfs)s/%(fstore)s: %(e)s') %
                   {'fpg': fpg, 'vfs': vfs, 'fstore': fstore,
                    'e': six.text_type(e)})
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)

    def delete_snapshot(self, orig_project_id, orig_share_id, orig_proto,
                        snapshot_id, fpg, vfs):
        """Deletes a snapshot of a share."""

        snapshot_tag = self.ensure_prefix(snapshot_id)

        snapshot = self._find_fsnap(orig_project_id, orig_share_id, orig_proto,
                                    snapshot_tag, fpg, vfs)

        if not snapshot:
            return

        fstore = snapshot.get('fstoreName')

        for protocol in ('nfs', 'smb'):
            try:
                shares = self._client.getfshare(protocol,
                                                fpg=fpg,
                                                vfs=vfs,
                                                fstore=fstore)
            except Exception as e:
                msg = (_('Unexpected exception while getting share list. '
                         'Cannot delete snapshot without checking for '
                         'dependent shares first: %s') % six.text_type(e))
                LOG.exception(msg)
                raise exception.ShareBackendException(msg=msg)

            for share in shares['members']:
                if protocol == 'nfs':
                    path = share['sharePath'][1:].split('/')
                    dot_snapshot_index = 3
                else:
                    if share['shareDir']:
                        path = share['shareDir'].split('/')
                    else:
                        path = None
                    dot_snapshot_index = 0

                snapshot_index = dot_snapshot_index + 1
                if path and len(path) > snapshot_index:
                    if (path[dot_snapshot_index] == '.snapshot' and
                            path[snapshot_index].endswith(snapshot_tag)):
                        msg = (_('Cannot delete snapshot because it has a '
                                 'dependent share.'))
                        raise exception.Invalid(msg)

        snapname = snapshot['snapName']
        try:
            result = self._client.removefsnap(
                vfs, fstore, snapname=snapname, fpg=fpg)

            LOG.debug("removefsnap result=%s", result)

        except Exception as e:
            msg = (_('Failed to delete snapshot for FPG/VFS/fstore/snapshot '
                     '%(fpg)s/%(vfs)s/%(fstore)s/%(snapname)s: %(e)s') %
                   {
                       'fpg': fpg,
                       'vfs': vfs,
                       'fstore': fstore,
                       'snapname': snapname,
                       'e': six.text_type(e)})
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)

        # Try to reclaim the space
        try:
            self._client.startfsnapclean(fpg, reclaimStrategy='maxspeed')
        except Exception:
            # Remove already happened so only log this.
            LOG.exception('Unexpected exception calling startfsnapclean '
                          'for FPG %(fpg)s.', {'fpg': fpg})

    @staticmethod
    def _validate_access_type(protocol, access_type):

        if access_type not in ('ip', 'user'):
            msg = (_("Invalid access type.  Expected 'ip' or 'user'.  "
                     "Actual '%s'.") % access_type)
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg)

        if protocol == 'nfs' and access_type != 'ip':
            msg = (_("Invalid NFS access type.  HPE 3PAR NFS supports 'ip'. "
                     "Actual '%s'.") % access_type)
            LOG.error(msg)
            raise exception.HPE3ParInvalid(err=msg)

        return protocol

    @staticmethod
    def _validate_access_level(protocol, access_type, access_level, fshare):

        readonly = access_level == 'ro'
        snapshot = HPE3ParMediator._is_share_from_snapshot(fshare)

        if snapshot and not readonly:
            reason = _('3PAR shares from snapshots require read-only access')
            LOG.error(reason)
            raise exception.InvalidShareAccess(reason=reason)

        if protocol == 'smb' and access_type == 'ip' and snapshot != readonly:
            msg = (_("Invalid CIFS access rule. HPE 3PAR optionally supports "
                     "IP access rules for CIFS shares, but they must be "
                     "read-only for shares from snapshots and read-write for "
                     "other shares. Use the required CIFS 'user' access rules "
                     "to refine access."))
            LOG.error(msg)
            raise exception.InvalidShareAccess(reason=msg)

    @staticmethod
    def ignore_benign_access_results(plus_or_minus, access_type, access_to,
                                     result):

        # TODO(markstur): Remove the next line when hpe3parclient is fixed.
        result = [x for x in result if x != '\r']

        if result:
            if plus_or_minus == DENY:
                if DOES_NOT_EXIST in result[0]:
                    return None
            else:
                if access_type == 'user':
                    if USER_ALREADY_EXISTS % access_to in result[0]:
                        return None
                elif IP_ALREADY_EXISTS % access_to in result[0]:
                    return None
        return result

    def _find_fstore(self, project_id, share_id, share_proto, fpg, vfs,
                     allow_cross_protocol=False):

        share = self._find_fshare(project_id,
                                  share_id,
                                  share_proto,
                                  fpg,
                                  vfs,
                                  allow_cross_protocol=allow_cross_protocol)

        return share.get('fstoreName') if share else None

    def _find_fshare(self, project_id, share_id, share_proto, fpg, vfs,
                     allow_cross_protocol=False, readonly=False):

        share = self._find_fshare_with_proto(project_id,
                                             share_id,
                                             share_proto,
                                             fpg,
                                             vfs,
                                             readonly=readonly)

        if not share and allow_cross_protocol:
            other_proto = self.other_protocol(share_proto)
            share = self._find_fshare_with_proto(project_id,
                                                 share_id,
                                                 other_proto,
                                                 fpg,
                                                 vfs,
                                                 readonly=readonly)
        return share

    def _find_fshare_with_proto(self, project_id, share_id, share_proto,
                                fpg, vfs, readonly=False):

        protocol = self.ensure_supported_protocol(share_proto)
        share_name = self.ensure_prefix(share_id, readonly=readonly)

        project_fstore = self.ensure_prefix(project_id, share_proto)
        search_order = [
            {'fpg': fpg, 'vfs': vfs, 'fstore': project_fstore},
            {'fpg': fpg, 'vfs': vfs, 'fstore': share_name},
            {'fpg': fpg},
            {}
        ]

        try:
            for search_params in search_order:
                result = self._client.getfshare(protocol, share_name,
                                                **search_params)
                shares = result.get('members', [])
                if len(shares) == 1:
                    return shares[0]
        except Exception as e:
            msg = (_('Unexpected exception while getting share list: %s') %
                   six.text_type(e))
            raise exception.ShareBackendException(msg=msg)

    def _find_fsnap(self, project_id, share_id, orig_proto, snapshot_tag,
                    fpg, vfs):

        share_name = self.ensure_prefix(share_id)
        osf_project_id = self.ensure_prefix(project_id, orig_proto)
        pattern = '*_%s' % self.ensure_prefix(snapshot_tag)

        search_order = [
            {'pat': True, 'fpg': fpg, 'vfs': vfs, 'fstore': osf_project_id},
            {'pat': True, 'fpg': fpg, 'vfs': vfs, 'fstore': share_name},
            {'pat': True, 'fpg': fpg},
            {'pat': True},
        ]

        try:
            for search_params in search_order:
                result = self._client.getfsnap(pattern, **search_params)
                snapshots = result.get('members', [])
                if len(snapshots) == 1:
                    return snapshots[0]
        except Exception as e:
            msg = (_('Unexpected exception while getting snapshots: %s') %
                   six.text_type(e))
            raise exception.ShareBackendException(msg=msg)

    def _wait_for_task_completion(self, task_id, interval=1):
        """This waits for a 3PAR background task complete or fail.
        This looks for a task to get out of the 'active' state.
        """

        # Wait for the physical copy task to complete
        def _wait_for_task(task_id, task_status):
            status = self._client.getTask(task_id)
            LOG.debug("3PAR Task id %(id)s status = %(status)s",
                      {'id': task_id,
                       'status': status['status']})
            if status['status'] is not self._client.TASK_ACTIVE:
                task_status.append(status)
                raise loopingcall.LoopingCallDone()

        self._wsapi_login()
        task_status = []
        try:
            timer = loopingcall.FixedIntervalLoopingCall(
                _wait_for_task, task_id, task_status)
            timer.start(interval=interval).wait()

            if task_status[0]['status'] is not self._client.TASK_DONE:
                msg = "ERROR: Task with id %d has failed with status %s" %\
                      (task_id, task_status)
                LOG.exception(msg)
                raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def _check_task_id(self, task_id):
        if type(task_id) is list:
            task_id = task_id[0]
        try:
            int(task_id)
        except ValueError:
            # 3PAR returned error instead of task_id
            # Log the error message
            msg = task_id
            LOG.error(msg)
            raise exception.ShareBackendException(msg)
        return task_id

    def create_fpg(self, cpg, fpg_name, size=64):
        try:
            self._wsapi_login()
            uri = '/fpgs/'
            args = {
                'name': fpg_name,
                'cpg': cpg,
                'sizeTiB': size,
                'comment': 'Docker created FPG'
            }
            resp, body = self._client.http.post(uri, body=args)
            task_id = body['taskId']
            self._wait_for_task_completion(task_id, interval=10)
        except exception.ShareBackendException as ex:
            msg = 'Create FPG task failed: cpg=%s,fpg=%s, ex=%s'\
                  % (cpg, fpg_name, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        except Exception:
            msg = (_('Failed to create FPG %s of size %s using CPG %s') %
                   (fpg_name, size, cpg))
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def create_vfs(self, vfs_name, ip, subnet, cpg=None, fpg=None,
                   size=64):
        uri = '/virtualfileservers/'
        ip_info = {
            'IPAddr': ip,
            'netmask': subnet
        }
        args = {
            'name': vfs_name,
            'IPInfo': ip_info,
            'cpg': cpg,
            'fpg': fpg,
            'comment': 'Docker created VFS'
        }
        try:
            self._wsapi_login()
            resp, body = self._client.http.post(uri, body=args)
            if resp['status'] != '202':
                msg = 'Create VFS task failed: vfs=%s, cpg=%s,fpg=%s' \
                      % (vfs_name, cpg, fpg)
                LOG.exception(msg)
                raise exception.ShareBackendException(msg=msg)

            task_id = body['taskId']
            self._wait_for_task_completion(task_id, interval=3)
            LOG.info("Created VFS '%s' successfully" % vfs_name)
        except exception.ShareBackendException as ex:
            msg = 'Create VFS task failed: vfs=%s, cpg=%s,fpg=%s, ex=%s'\
                  % (vfs_name, cpg, fpg, six.text_type(ex))
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)

        except Exception:
            msg = (_('ERROR: VFS creation failed: [vfs: %s, ip:%s, subnet:%s,'
                     'cpg:%s, fpg:%s, size=%s') % (vfs_name, ip, subnet, cpg,
                                                   fpg, size))
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def add_client_ip_for_share(self, share_id, client_ip):
        uri = '/fileshares/%s' % share_id
        body = {
            'nfsClientlistOperation': 1,
            'nfsClientlist': [client_ip]
        }
        self._wsapi_login()
        try:
            self._client.http.put(uri, body=body)
        finally:
            self._wsapi_logout()

    def remove_client_ip_for_share(self, share_id, client_ip):
        uri = '/fileshares/%s' % share_id
        body = {
            'nfsClientlistOperation': 2,
            'nfsClientlist': [client_ip]
        }
        self._wsapi_login()
        try:
            self._client.http.put(uri, body=body)
        finally:
            self._wsapi_logout()
