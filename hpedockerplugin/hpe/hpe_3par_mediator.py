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
import six

from oslo_log import log
from oslo_service import loopingcall
from oslo_utils import importutils

from hpedockerplugin import exception
from hpedockerplugin.i18n import _

hpe3parclient = importutils.try_import("hpe3parclient")
if hpe3parclient:
    from hpe3parclient import file_client
    from hpe3parclient import exceptions as hpeexceptions

LOG = log.getLogger(__name__)
MIN_CLIENT_VERSION = (4, 0, 0)

BAD_REQUEST = '400'
OTHER_FAILURE_REASON = 29
NON_EXISTENT_CPG = 15
INV_INPUT_ILLEGAL_CHAR = 69
TASK_STATUS_NORMAL = 1

# Overriding these class variable so that minimum supported version is 3.3.1
file_client.HPE3ParFilePersonaClient.HPE3PAR_WS_MIN_BUILD_VERSION = 30301460
file_client.HPE3ParFilePersonaClient.HPE3PAR_WS_MIN_BUILD_VERSION_DESC = \
    '3.3.1 (MU3)'


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

    def get_fpgs(self, filter):
        try:
            self._wsapi_login()
            uri = '/fpgs?query="name EQ %s"' % filter
            resp, body = self._client.http.get(uri)
            return body['members'][0]
        finally:
            self._wsapi_logout()

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

    def get_all_vfs(self):
        try:
            self._wsapi_login()
            uri = '/virtualfileservers'
            resp, body = self._client.http.get(uri)
            return body['members']
        finally:
            self._wsapi_logout()

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
            self._wsapi_login()
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
        finally:
            self._wsapi_logout()

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

    def get_file_stores_for_fpg(self, fpg_name):
        uri = '/filestores?query="fpg EQ %s"' % fpg_name
        try:
            self._wsapi_login()
            resp, body = self._client.http.get(uri)
            return body
        except Exception as ex:
            msg = "mediator:get_file_shares - failed to get file stores " \
                  "for  FPG %s from the backend. Exception: %s" % \
                  (fpg_name, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def shares_present_on_fpg(self, fpg_name):
        fstores = self.get_file_stores_for_fpg(fpg_name)
        for fstore in fstores['members']:
            if fstore['name'] != '.admin':
                return True
        return False

    def get_quotas_for_fpg(self, fpg_name):
        uri = '/filepersonaquotas?query="fpg EQ %s"' % fpg_name
        try:
            self._wsapi_login()
            resp, body = self._client.http.get(uri)
            return body
        except Exception as ex:
            msg = "mediator:get_quota - failed to get quotas for FPG %s" \
                  "from the backend. Exception: %s" % \
                  (fpg_name, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

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
        try:
            self._wsapi_login()
            return self._create_share(share_details)
        finally:
            self._wsapi_logout()

    def delete_share(self, share_id):
        LOG.info("Mediator:delete_share %s: Entering..." % share_id)
        uri = '/fileshares/%s' % share_id
        try:
            self._wsapi_login()
            self._client.http.delete(uri)
        except hpeexceptions.HTTPNotFound:
            LOG.warning("Share %s not found on backend" % share_id)
            pass
        except Exception as ex:
            msg = "Failed to remove share %s at the backend. Reason: %s" \
                  % (share_id, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

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

        task_status = []

        timer = loopingcall.FixedIntervalLoopingCall(
            _wait_for_task, task_id, task_status)
        timer.start(interval=interval).wait()

        if task_status[0]['status'] is not self._client.TASK_DONE:
            msg = "ERROR: Task with id %d has failed with status %s" %\
                  (task_id, task_status)
            LOG.exception(msg)
            raise exception.ShareBackendException(msg=msg)

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

    def create_fpg(self, cpg, fpg_name, size=16):
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

            LOG.info("Create FPG Response: %s" % six.text_type(resp))
            LOG.info("Create FPG Response Body: %s" % six.text_type(body))
            if (resp['status'] == BAD_REQUEST and
                    body['code'] == OTHER_FAILURE_REASON and
                    'already exists' in body['desc']):
                LOG.error(body['desc'])
                raise exception.FpgAlreadyExists(reason=body['desc'])

            task_id = body.get('taskId')
            if task_id:
                self._wait_for_task_completion(task_id, interval=10)
        except hpeexceptions.HTTPBadRequest as ex:
            error_code = ex.get_code()
            LOG.error("Exception: %s" % six.text_type(ex))
            if error_code == NON_EXISTENT_CPG:
                msg = "Failed to create FPG %s on the backend. Reason: " \
                      "CPG %s doesn't exist on array" % (fpg_name, cpg)
                LOG.error(msg)
                raise exception.ShareBackendException(msg=msg)
            elif error_code == OTHER_FAILURE_REASON:
                LOG.error(six.text_type(ex))
                msg = ex.get_description()
                if 'already exists' in msg or \
                        msg.startswith('A createfpg task is already running'):
                    raise exception.FpgAlreadyExists(reason=msg)
            raise exception.ShareBackendException(msg=ex.get_description())
        except exception.ShareBackendException as ex:
            msg = 'Create FPG task failed: cpg=%s,fpg=%s, ex=%s'\
                  % (cpg, fpg_name, six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        except Exception as ex:
            msg = (_('Failed to create FPG %s of size %s using CPG %s: '
                     'Exception: %s') % (fpg_name, size, cpg, ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def create_vfs(self, vfs_name, ip, subnet, cpg=None, fpg=None,
                   size=16):
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
            msg = 'Create VFS task failed: vfs=%s, cpg=%s,fpg=%s' \
                  % (vfs_name, cpg, fpg)
            if resp['status'] != '202':
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
        else:
            self._check_vfs_status(task_id, fpg)
        finally:
            self._wsapi_logout()

    def _check_vfs_status(self, task_id, fpg):
        LOG.info("Checking status of VFS under FPG %s..." % fpg)
        vfs = self.get_vfs(fpg)
        overall_state = vfs['overallState']

        if overall_state != TASK_STATUS_NORMAL:
            LOG.info("Overall state of VFS is not normal")
            task = self._client.getTask(task_id)
            detailed_status = task['detailedStatus']
            lines = detailed_status.split('\n')
            error_line = ''
            for line in lines:
                idx = line.find('Error')
                if idx != -1:
                    error_line += line[idx:] + '\n'
            if error_line:
                raise exception.ShareBackendException(msg=error_line)
            else:
                raise exception.ShareBackendException(msg=detailed_status)

    def set_ACL(self, fMode, fUserId, fUName, fGName):
        # fsMode = "A:fdps:rwaAxdD,A:fFdps:rwaxdnNcCoy,A:fdgps:DtnNcy"
        ACLList = []
        per_type = {"A": 1, "D": 2, "U": 3, "L": 4}
        fsMode_list = fMode.split(",")
        principal_list = ['OWNER@', 'GROUP@', 'EVERYONE@']
        for index, value in enumerate(fsMode_list):
            acl_values = value.split(":")
            acl_type = per_type.get(acl_values[0])
            acl_flags = acl_values[1]
            acl_principal = ""
            if index == 0:
                acl_principal = principal_list[index]
            if index == 1:
                acl_principal = principal_list[index]
            if index == 2:
                acl_principal = principal_list[index]
            acl_permission = acl_values[2]
            acl_object = {}
            acl_object['aclType'] = acl_type
            acl_object['aclFlags'] = acl_flags
            acl_object['aclPrincipal'] = acl_principal
            acl_object['aclPermissions'] = acl_permission
            ACLList.append(acl_object)
        args = {
            'owner': fUName,
            'group': fGName,
            'ACLList': ACLList
        }
        LOG.info("ACL args being passed is %s  ", args)
        try:
            self._wsapi_login()
            uri = '/fileshares/' + fUserId + '/dirperms'

            self._client.http.put(uri, body=args)

            LOG.debug("Share permissions changed successfully")

        except hpeexceptions.HTTPBadRequest as ex:
            msg = (_("File share permission change failed. Exception %s : ")
                   % six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)
        finally:
            self._wsapi_logout()

    def _check_usr_grp_existence(self, fUserOwner, res_cmd):
        fuserowner = str(fUserOwner)
        uname_index = 0
        uid_index = 1
        user_name = None
        first_line = res_cmd[1]
        first_line_list = first_line.split(',')
        for index, value in enumerate(first_line_list):
            if value == 'Username':
                uname_index = index
            if value == 'UID':
                uid_index = index
        res_len = len(res_cmd)
        end_index = res_len - 3
        for line in res_cmd[2:end_index]:
            line_list = line.split(',')
            if fuserowner == line_list[uid_index]:
                user_name = line_list[uname_index]
                return user_name
        if user_name is None:
            return None

    def usr_check(self, fUser, fGroup):
        LOG.info("I am inside usr_check")
        cmd1 = ['showfsuser']
        cmd2 = ['showfsgroup']
        try:
            LOG.info("Now will execute first cmd1")
            cmd1.append('\r')
            res_cmd1 = self._client._run(cmd1)
            f_user_name = self._check_usr_grp_existence(fUser, res_cmd1)
            cmd2.append('\r')
            res_cmd2 = self._client._run(cmd2)
            f_group_name = self._check_usr_grp_existence(fGroup, res_cmd2)
            return f_user_name, f_group_name
        except hpeexceptions.SSHException as ex:
            msg = (_('Failed to get the corresponding user and group name '
                     'reason is %s:') % six.text_type(ex))
            LOG.error(msg)
            raise exception.ShareBackendException(msg=msg)

    def add_client_ip_for_share(self, share_id, client_ip):
        uri = '/fileshares/%s' % share_id
        body = {
            'nfsClientlistOperation': 1,
            'nfsClientlist': [client_ip]
        }
        try:
            self._wsapi_login()
            self._client.http.put(uri, body=body)
        except hpeexceptions.HTTPBadRequest as ex:
            msg = (_("It is first mount request but ip is already"
                     " added to the share. Exception %s : ")
                   % six.text_type(ex))
            LOG.info(msg)
        finally:
            self._wsapi_logout()

    def remove_client_ip_for_share(self, share_id, client_ip):
        uri = '/fileshares/%s' % share_id
        body = {
            'nfsClientlistOperation': 2,
            'nfsClientlist': [client_ip]
        }
        try:
            self._wsapi_login()
            self._client.http.put(uri, body=body)
        finally:
            self._wsapi_logout()
