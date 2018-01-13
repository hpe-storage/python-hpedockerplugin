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

"""
An HTTP API implementing the Docker Volumes Plugin API.

See https://github.com/docker/docker/tree/master/docs/extend for details.
"""
from os_brick.initiator import connector
from oslo_utils import netutils
import uuid
from i18n import _, _LE, _LI, _LW
import exception
import six

import json

from twisted.python.filepath import FilePath

import fileutil

from klein import Klein
from hpe import volume
from hpe import utils
from oslo_utils import importutils
import etcdutil as util

from oslo_log import log as logging

# import time


LOG = logging.getLogger(__name__)


class VolumePlugin(object):
    """
    An implementation of the Docker Volumes Plugin API.

    """
    app = Klein()

    def __init__(self, reactor, hpepluginconfig):
        """
        :param IReactorTime reactor: Reactor time interface implementation.
        :param Ihpepluginconfig : hpedefaultconfig configuration
        """
        LOG.info(_LI('Initialize Volume Plugin'))

        self._reactor = reactor
        self._hpepluginconfig = hpepluginconfig
        hpeplugin_driver = hpepluginconfig.hpedockerplugin_driver

        protocol = 'ISCSI'

        if 'HPE3PARFCDriver' in hpeplugin_driver:
            protocol = 'FIBRE_CHANNEL'

        self.hpeplugin_driver = \
            importutils.import_object(hpeplugin_driver, self._hpepluginconfig)

        if self.hpeplugin_driver is None:
            msg = (_('hpeplugin_driver import driver failed'))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

        try:
            self.hpeplugin_driver.do_setup()
            self.hpeplugin_driver.check_for_setup_error()
        except Exception as ex:
            msg = (_('hpeplugin_driver do_setup failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

        self._voltracker = {}
        self._path_info = []
        self._my_ip = netutils.get_my_ipv4()

        self._etcd = self._get_etcd_util()

        # TODO: make device_scan_attempts configurable
        # see nova/virt/libvirt/volume/iscsi.py

        # Override the settings of use_multipath, enforce_multipath
        # This will be a workaround until Issue #50 is fixed.
        msg = (_('Overriding the value of multipath flags to True'))
        LOG.info(msg)
        self.use_multipath = True
        self.enforce_multipath = True

        self.connector = self._get_connector(protocol)

    def _get_connector(self, protocol):
        root_helper = 'sudo'
        return connector.InitiatorConnector.factory(
            protocol, root_helper, use_multipath=self.use_multipath,
            device_scan_attempts=5, transport='default')

    def _get_etcd_util(self):
        return util.EtcdUtil(
            self._hpepluginconfig.host_etcd_ip_address,
            self._hpepluginconfig.host_etcd_port_number,
            self._hpepluginconfig.host_etcd_client_cert,
            self._hpepluginconfig.host_etcd_client_key)

    def disconnect_volume_callback(self, connector_info):
        LOG.info(_LI('In disconnect_volume_callback: connector info is %s'),
                 json.dumps(connector_info))

    def disconnect_volume_error_callback(self, connector_info):
        LOG.info(_LI('In disconnect_volume_error_callback: '
                     'connector info is %s'), json.dumps(connector_info))

    @app.route("/Plugin.Activate", methods=["POST"])
    def plugin_activate(self, ignore_body=True):
        """
        Return which Docker plugin APIs this object supports.
        """
        LOG.info(_LI('In Plugin Activate'))
        return json.dumps({u"Implements": [u"VolumeDriver"]})

    @app.route("/VolumeDriver.Remove", methods=["POST"])
    def volumedriver_remove(self, name):
        """
        Remove a Docker volume.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        obj_to_remove = contents['Name']
        tokens = obj_to_remove.split('/')
        token_cnt = len(tokens)
        LOG.debug("volumedriver_remove - obj_to_remove: %s" %
                  obj_to_remove)
        if token_cnt > 2:
            msg = (_LE("invalid volume or snapshot name %s"
                       % obj_to_remove))
            LOG.error(msg)
            response = json.dumps({u"Err": msg})
            return response

        if token_cnt == 2:
            volname = tokens[0]
            snapname = tokens[1]
            # We don't want to insert remove-snapshot code within
            # remove-volume code for two reasons:
            # 1. We want to avoid regression in existing remove-volume
            # 2. In the future, if docker engine provides snapshot
            #    support, this code should have minimum impact
            return self.volumedriver_remove_snapshot(volname, snapname)
        else:
            volname = tokens[0]

        # Only 1 node in a multinode cluster can try to remove the volume.
        # Grab lock for volume name. If lock is inuse, just return with no
        # error.
        # Expand lock code inline as function based lock causes
        # unexpected behavior
        try:
            self._etcd.try_lock_volname(volname)
        except Exception:
            LOG.debug('volume: %(name)s is locked',
                      {'name': volname})
            response = json.dumps({u"Err": ''})
            return response

        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            # Just log an error, but don't fail the docker rm command
            msg = (_LE('Volume remove name not found %s'), volname)
            LOG.error(msg)
            # Expand lock code inline as function based lock causes
            # unexpected behavior
            try:
                self._etcd.try_unlock_volname(volname)
            except Exception as ex:
                LOG.debug('volume: %(name)s Unlock Volume Failed',
                          {'name': volname})
                response = json.dumps({u"Err": six.text_type(ex)})
                return response
            return json.dumps({u"Err": ''})

        try:
            if vol['snapshots']:
                msg = (_LE('Err: Volume %s has one or more child '
                           'snapshots - volume cannot be deleted!'
                           % volname))
                LOG.error(msg)
                response = json.dumps({u"Err": msg})
                try:
                    self._etcd.try_unlock_volname(volname)
                except Exception as ex:
                    LOG.error('volume: %(name)s Unlock volume failed',
                              {'name':volname})
                    response = json.dumps({u"Err": six.text_type(ex)})
                return response
            else:
                self.hpeplugin_driver.delete_volume(vol)
                LOG.info(_LI('volume: %(name)s,' 'was successfully deleted'),
                         {'name': volname})
        except Exception as ex:
            msg = (_LE('Err: Failed to remove volume %s, error is %s'),
                   volname, six.text_type(ex))
            LOG.error(msg)
            # Expand lock code inline as function based lock causes
            # unexpected behavior
            try:
                self._etcd.try_unlock_volname(volname)
            except Exception as ex:
                LOG.debug('volume: %(name)s Unlock Volume Failed',
                          {'name': volname})
                response = json.dumps({u"Err": six.text_type(ex)})
                return response
            return json.dumps({u"Err": six.text_type(ex)})

        try:
            self._etcd.delete_vol(vol)
        except KeyError:
            msg = (_LW('Warning: Failed to delete volume key: %s from '
                       'etcd due to KeyError'), volname)
            LOG.warning(msg)
            pass

        # Expand lock code inline as function based lock causes
        # unexpected behavior
        try:
            self._etcd.try_unlock_volname(volname)
        except Exception as ex:
            LOG.debug('volume: %(name)s Unlock Volume Failed',
                      {'name': volname})
            response = json.dumps({u"Err": six.text_type(ex)})
            return response
        return json.dumps({u"Err": ''})

    def _get_snapshot_by_name(self, snapshots, snapname):
        idx = 0
        for s in snapshots:
            if s['name'] == snapname:
                return s, idx
            idx = idx + 1
        return None, None

    def volumedriver_remove_snapshot(self, volname, snapname):
        lock_acquired = False
        try:
            LOG.info("volumedriver_remove_snapshot - locking volume %s"
                     % volname)
            self._etcd.try_lock_volname(volname)
            lock_acquired = True

            LOG.info("volumedriver_remove_snapshot - getting volume %s"
                     % volname)

            vol = self._etcd.get_vol_byname(volname)
            if vol is None:
                # Just log an error, but don't fail the docker rm command
                msg = (_LE('snapshot remove - parent volume name not found '
                           '%s'), volname)
                LOG.error(msg)
                return json.dumps({u"Err": msg})

            if snapname:
                snapshots = vol['snapshots']
                LOG.info("Getting snapshot by name: %s" % snapname)
                snapshot, idx = self._get_snapshot_by_name(snapshots,
                                                           snapname)

                if snapshot:
                    LOG.info("Found snapshot by name: %s" % snapname)
                    # Does the snapshot have child snapshot(s)?
                    for ss in snapshots:
                        LOG.info("Checking if snapshot has children: %s"
                                 % snapname)
                        if ss['parent_id'] == snapshot['id']:
                            msg = (_LE('snapshot %s/%s has one or more child '
                                       'snapshots - it cannot be deleted!'
                                       % (volname, snapname)))
                            LOG.error(msg)
                            # raise exception.HPEPluginRemoveException(
                            # reason=msg)
                            response = json.dumps({u"Err": msg})
                            return response
                    try:
                        LOG.info("Deleting snapshot at backend: %s" % snapname)
                        self.hpeplugin_driver.delete_volume(snapshot,
                                                            is_snapshot=True)
                    except Exception as err:
                        msg = (_LE('Failed to remove snapshot error is: %s'),
                               six.text_type(err))
                        LOG.error(msg)
                        response = json.dumps({u"Err": six.text_type(err)})
                        try:
                            self._etcd.try_unlock_volname(volname)
                            lock_acquired = False
                        except Exception as ex:
                            LOG.error('volume: %(name)s Unlock Volume Failed',
                                      {'name': volname})
                            response = json.dumps({u"Err": six.text_type(ex)})
                        return response

                    LOG.info("Deleting snapshot in ETCD - %s" % snapname)
                    # Remove snapshot entry from list and save it back to
                    # ETCD DB
                    del snapshots[idx]
                    try:
                        LOG.info("Updating volume in ETCD after snapshot "
                                 "removal - vol-name: %s" % volname)
                        # For now just track volume to uuid mapping internally
                        # TODO: Save volume name and uuid mapping in etcd as
                        # well. This will make get_vol_byname more efficient
                        self._etcd.update_vol(vol['id'],
                                              'snapshots',
                                              snapshots)
                        LOG.info('snapshot: %(name)s was successfully '
                                 'removed', {'name': snapname})
                        response = json.dumps({u"Err": ''})
                        return response
                    except Exception as ex:
                        msg = (_('remove snapshot from etcd failed, error is:'
                                 ' %s'), six.text_type(ex))
                        LOG.error(msg)
                        response = json.dumps({u"Err": six.text_type(ex)})
                        return response
                else:
                    msg = (_LE('snapshot %s does not exist!' % snapname))
                    LOG.error(msg)
                    # raise exception.HPEPluginRemoveException(reason=msg)
                    response = json.dumps({u"Err": msg})
                    return response

        except Exception:
                LOG.error('volume: %(name)s is locked',
                          {'name': volname})
                response = json.dumps({u"Err": ''})
                return response
        finally:
            # Expand lock code inline as function based lock causes
            # unexpected behavior
            try:
                if lock_acquired:
                    self._etcd.try_unlock_volname(volname)
            except Exception as ex:

                LOG.error('volume: %(name)s Unlock Volume Failed',
                          {'name': volname})
                response = json.dumps({u"Err": six.text_type(ex)})
                return response

    @app.route("/VolumeDriver.Unmount", methods=["POST"])
    def volumedriver_unmount(self, name):
        """
        The Docker container is no longer using the given volume,
        so unmount it.
        NOTE: Since Docker will automatically call Unmount if the Mount
        fails, make sure we properly handle partially completed Mounts.

        :param unicode name: The name of the volume.
        :return: Result indicating success.
        """
        LOG.info(_LI('In volumedriver_unmount'))
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            volid = vol['id']
        else:
            msg = (_LE('Volume unmount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginUMountException(reason=msg)

        vol_mount = volume.DEFAULT_MOUNT_VOLUME
        if ('Opts' in contents and contents['Opts'] and
                'mount-volume' in contents['Opts']):
            vol_mount = str(contents['Opts']['mount-volume'])

        path_info = self._etcd.get_vol_path_info(volname)
        if path_info:
            path_name = path_info['path']
            connection_info = path_info['connection_info']
            mount_dir = path_info['mount_dir']
        else:
            msg = (_LE('Volume unmount path info not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginUMountException(reason=msg)

        # Get connector info from OS Brick
        # TODO: retrieve use_multipath and enforce_multipath from config file
        root_helper = 'sudo'

        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, multipath=self.use_multipath,
            enforce_multipath=self.enforce_multipath)

        # Determine if we need to unmount a previously mounted volume
        if vol_mount is volume.DEFAULT_MOUNT_VOLUME:
            # unmount directory
            fileutil.umount_dir(mount_dir)
            # remove directory
            fileutil.remove_dir(mount_dir)

        # Changed asynchronous disconnect_volume to sync call
        # since it causes a race condition between unmount and
        # mount operation on the same volume. This scenario is
        # more noticed in case of repeated mount & unmount
        # operations on the same volume. Refer Issue #64
        if connection_info:
            LOG.info(_LI('sync call os brick to disconnect volume'))
            self.connector.disconnect_volume(connection_info['data'], None)
            LOG.info(_LI('end of sync call to disconnect volume'))

        try:
            # Call driver to terminate the connection
            self.hpeplugin_driver.terminate_connection(vol, connector_info)
            LOG.info(_LI('connection_info: %(connection_info)s, '
                         'was successfully terminated'),
                     {'connection_info': json.dumps(connection_info)})
        except Exception as ex:
            msg = (_LE('connection info termination failed %s'),
                   six.text_type(ex))
            LOG.error(msg)
            # Not much we can do here, so just continue on with unmount
            # We need to ensure we update etcd path_info so the stale
            # path does not stay around
            # raise exception.HPEPluginUMountException(reason=msg)

        # TODO: Create path_info list as we can mount the volume to multiple
        # hosts at the same time.
        self._etcd.update_vol(volid, 'path_info', None)

        LOG.info(_LI('path for volume: %(name)s, was successfully removed: '
                     '%(path_name)s'), {'name': volname,
                                        'path_name': path_name})

        response = json.dumps({u"Err": ''})
        return response

    @app.route("/VolumeDriver.Create", methods=["POST"])
    def volumedriver_create(self, name, opts=None):
        """
        Create a volume with the given name.

        :param unicode name: The name of the volume.
        :param dict opts: Options passed from Docker for the volume
            at creation. ``None`` if not supplied in the request body.
            Currently ignored. ``Opts`` is a parameter introduced in the
            v2 plugins API introduced in Docker 1.9, it is not supplied
            in earlier Docker versions.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        if 'Name' not in contents:
            msg = (_('create volume failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)
        volname = contents['Name']
        vol_size = volume.DEFAULT_SIZE
        vol_prov = volume.DEFAULT_PROV
        vol_flash = volume.DEFAULT_FLASH_CACHE
        vol_qos = volume.DEFAULT_QOS
        compression_val = volume.DEFAULT_COMPRESSION_VAL
        valid_compression_opts = ['true', 'false']

        # Verify valid Opts arguments.
        valid_volume_create_opts = ['mount-volume', 'compression',
                                    'size', 'provisioning', 'flash-cache',
                                    'cloneOf', 'snapshotOf', 'expirationHours',
                                    'retentionHours', 'promote', 'qos-name']

        if ('Opts' in contents and contents['Opts']):
            for key in contents['Opts']:
                if key not in valid_volume_create_opts:
                    msg = (_('create volume failed, error is: '
                             '%(key)s is not a valid option. Valid options '
                             'are: %(valid)s') %
                           {'key': key,
                            'valid': valid_volume_create_opts, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

            # Populating the values
            if ('size' in contents['Opts']):
                vol_size = int(contents['Opts']['size'])

            if ('provisioning' in contents['Opts']):
                vol_prov = str(contents['Opts']['provisioning'])

            if ('compression' in contents['Opts']):
                compression_val = str(contents['Opts']['compression'])

            if ('flash-cache' in contents['Opts']):
                vol_flash = str(contents['Opts']['flash-cache'])

            if ('qos-name' in contents['Opts']):
                vol_qos = str(contents['Opts']['qos-name'])

            # check for valid promoteSnap option and return the result
            if ('promote' in contents['Opts'] and len(contents['Opts']) == 1):
                return self.revert_to_snapshot(name, opts)
            elif ('promote' in contents['Opts']):
                msg = (_('while reverting volume to snapshot status only '
                         'valid option is promote=<vol_name>'))
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

            # mutually exclusive options check
            mutually_exclusive_list = ['snapshotOf', 'cloneOf', 'qos-name',
                                       'promote']
            input_list = contents['Opts'].keys()
            if (len(list(set(input_list) &
                         set(mutually_exclusive_list))) >= 2):
                msg = (_('%(exclusive)s cannot be specified at the same '
                         'time') % {'exclusive': mutually_exclusive_list, })
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

            if ('snapshotOf' in contents['Opts']):
                return self.volumedriver_create_snapshot(name, opts)
            elif ('cloneOf' in contents['Opts']):
                return self.volumedriver_clone_volume(name, opts)

        if compression_val is not None:
            if compression_val.lower() not in valid_compression_opts:
                msg = (_('create volume failed, error is:'
                         'passed compression parameterdo not have a valid '
                         'value. Valid vaues are: %(valid)s') %
                       {'valid': valid_compression_opts, })
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(msg)})

        LOG.debug('In volumedriver_create')

        # Grab lock for volume name. If lock is inuse, just return with no
        # error
        # Expand lock code inline as function based lock causes
        # unexpected behavior
        try:
            self._etcd.try_lock_volname(volname)
        except Exception:
            LOG.debug('volume: %(name)s is locked',
                      {'name': volname})
            response = json.dumps({u"Err": ''})
            return response

        # NOTE: Since Docker passes user supplied names and not a unique
        # uuid, we can't allow duplicate volume names to exist.
        # TODO: Should confirm with Docker on how why they allow the
        # 'docker volume create" command to create duplicate volume names.
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            # Release lock and return
            # Expand lock code inline as function based lock causes
            # unexpected behavior
            try:
                self._etcd.try_unlock_volname(volname)
            except Exception as ex:
                LOG.debug('volume: %(name)s Unlock Volume Failed',
                          {'name': volname})
                response = json.dumps({u"Err": six.text_type(ex)})
                return response
            return json.dumps({u"Err": ''})

        vol = volume.createvol(volname, vol_size, vol_prov,
                               vol_flash, compression_val, vol_qos)

        try:
            self.hpeplugin_driver.create_volume(vol)
        except Exception as ex:
            msg = (_('create volume failed, error is: %s'), six.text_type(ex))
            LOG.error(msg)
            # Release lock and return
            # NOTE: if for some reason unlock fails, we'll lose this
            # create exception.
            # Expand lock code inline as function based lock causes
            # unexpected behavior
            try:
                self._etcd.try_unlock_volname(volname)
            except Exception as ex:
                LOG.error('volume: %(name)s Unlock Volume Failed',
                          {'name': volname})
                response = json.dumps({u"Err": six.text_type(ex)})
                return response
            return json.dumps({u"Err": six.text_type(ex)})

        response = json.dumps({u"Err": ''})
        try:
            # For now just track volume to uuid mapping internally
            # TODO: Save volume name and uuid mapping in etcd as well
            # This will make get_vol_byname more efficient
            self._etcd.save_vol(vol)
            LOG.debug('volume: %(name)s was successfully saved to etcd',
                      {'name': volname})
        except Exception as ex:
            msg = (_('save volume to etcd failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            response = json.dumps({u"Err": six.text_type(ex)})

        # Expand lock code inline as function based lock causes
        # unexpected behavior
        try:
            self._etcd.try_unlock_volname(volname)
        except Exception as ex:
            LOG.error('volume: %(name)s Unlock Volume Failed',
                      {'name': volname})
            response = json.dumps({u"Err": six.text_type(ex)})
            return response
        return response

    def volumedriver_clone_volume(self, name, opts=None):
        # Repeating the validation here in anticipation that when
        # actual REST call for clone is added, this
        # function will have minimal impact
        contents = json.loads(name.content.getvalue())
        if 'Name' not in contents:
            msg = (_('clone volume failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

        src_vol_name = str(contents['Opts']['cloneOf'])
        clone_name = contents['Name']

        src_lock_acquired = False
        clone_lock_acquired = False
        try:
            self._etcd.try_lock_volname(src_vol_name)
            src_lock_acquired = True

            self._etcd.try_lock_volname(clone_name)
            clone_lock_acquired = True

            # Check if volume is present in database
            src_vol = self._etcd.get_vol_byname(src_vol_name)
            if src_vol is None:
                msg = 'source volume: %s does not exist' % src_vol_name
                LOG.debug(msg)
                response = json.dumps({u"Err": msg})
                return response

            if ('Opts' in contents and contents['Opts'] and
                    'size' in contents['Opts']):
                size = int(contents['Opts']['size'])
            else:
                size = src_vol['size']

            if size < src_vol['size']:
                msg = 'clone volume size %s is less than source ' \
                      'volume size %s' % (size, src_vol['size'])
                LOG.debug(msg)
                response = json.dumps({u"Err": msg})
                return response

            # Create clone volume specification
            clone_vol = volume.createvol(clone_name, size,
                                         src_vol['provisioning'],
                                         src_vol['flash_cache'],
                                         src_vol['compression'],
                                         src_vol['qos_name'], isclone=True)
            try:
                self.hpeplugin_driver.create_cloned_volume(clone_vol, src_vol)

                response = json.dumps({u"Err": ''})
                # For now just track volume to uuid mapping internally
                # TODO: Save volume name and uuid mapping in etcd as well
                # This will make get_vol_byname more efficient
                self._etcd.save_vol(clone_vol)
                return response
            except exception.HPEPluginEtcdException as ex:
                # TODO: 3PAR clean up issue over here - clone got created
                # in the backend but since it could not be saved in etcd db
                # we are throwing an error saying operation failed.
                # TODO: This needs to be fixed
                response = json.dumps({u"Err": ex.message})
                return response

            except Exception as ex:
                msg = (_('clone volume failed, error is: %s'),
                       six.text_type(ex))
                LOG.error(msg)
                response = json.dumps({u"Err": six.text_type(ex)})
                return response
        except exception.HPEPluginEtcdException as ex:
            # Imran: Returning good response even when exception is caught???
            response = json.dumps({u"Err": ''})
            return response
        except Exception as ex:
            msg = (_('unknown exception caught while cloning volume '
                     '%(name)s - reason: %(reason)s',
                     {'name': clone_name, 'reason': ex.message}))
            LOG.error(msg)
            response = json.dumps({u"Err": ''})
            return response

        finally:
            # Release lock and return
            # NOTE: if for some reason unlock fails, we'll lose this
            # create exception.
            # Expand lock code inline as function based lock causes
            # unexpected behavior
            if src_lock_acquired:
                try:
                    self._etcd.try_unlock_volname(src_vol_name)
                except Exception as ex:
                    LOG.error('volume: %(name)s Unlock Volume Failed',
                              {'name': src_vol_name})
                    # response = json.dumps({u"Err": six.text_type(ex)})
                    # return response
            if clone_lock_acquired:
                try:
                    self._etcd.try_unlock_volname(clone_name)
                except Exception as ex:
                    LOG.error('volume: %(name)s Unlock Volume Failed',
                              {'name': clone_name})
                    # response = json.dumps({u"Err": six.text_type(ex)})
                    # return response

    def volumedriver_create_snapshot(self, name, opts=None):
        # Repeating the validation here in anticipation that when
        # actual REST call for snapshot creation is added, this
        # function will have minimal impact
        contents = json.loads(name.content.getvalue())

        LOG.info("creating snapshot:\n%s" % json.dumps(contents, indent=2))

        if 'Name' not in contents:
            msg = (_('create snapshot failed, error is: Name is required.'))
            LOG.error(msg)
            raise exception.HPEPluginCreateException(reason=msg)

        src_vol_name = str(contents['Opts']['snapshotOf'])
        snapshot_name = contents['Name']

        # Verify valid Opts arguments.
        valid_volume_create_opts = ['snapshotOf', 'expirationHours',
                                    'retentionHours']
        if 'Opts' in contents and contents['Opts']:
            for key in contents['Opts']:
                if key not in valid_volume_create_opts:
                    msg = (_('create snapshot failed, error is: '
                             '%(key)s is not a valid option. Valid options '
                             'are: %(valid)s') %
                           {'key': key,
                            'valid': valid_volume_create_opts, })
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

        expiration_hrs = None
        if 'Opts' in contents and contents['Opts'] and \
                'expirationHours' in contents['Opts']:
            expiration_hrs = int(contents['Opts']['expirationHours'])

        retention_hrs = None
        if 'Opts' in contents and contents['Opts'] and \
                'retentionHours' in contents['Opts']:
            retention_hrs = int(contents['Opts']['retentionHours'])

        lock_acquired = False
        try:
            self._etcd.try_lock_volname(src_vol_name)

            lock_acquired = True

            # Check if volume is present in database
            vol = self._etcd.get_vol_byname(src_vol_name)
            if vol is None:
                msg = 'source volume: %s does not exist' % src_vol_name
                LOG.debug(msg)
                response = json.dumps({u"Err": msg})
                return response

            snapshot_id = str(uuid.uuid4())
            snapshot = {'id': snapshot_id,
                        'display_name': snapshot_name,
                        'volume_id': vol['id'],
                        'volume_name': src_vol_name,
                        'expirationHours': expiration_hrs,
                        'retentionHours': retention_hrs,
                        'display_description': 'snapshot of volume %s'
                                               % src_vol_name}
            try:
                self.hpeplugin_driver.create_snapshot(snapshot)

                response = json.dumps({u"Err": ''})
                db_snapshot = {'name': snapshot_name,
                               'id': snapshot_id,
                               'parent_id': vol['id'],
                               'expiration_hours': expiration_hrs,
                               'retention_hours': retention_hrs}
                vol['snapshots'].append(db_snapshot)
                try:
                    # For now just track volume to uuid mapping internally
                    # TODO: Save volume name and uuid mapping in etcd as well
                    # This will make get_vol_byname more efficient
                    self._etcd.save_vol(vol)
                    LOG.debug('snapshot: %(name)s was successfully saved '
                              'to etcd', {'name': snapshot_name})
                except Exception as ex:
                    # TODO: 3PAR clean up issue over here - snapshot got
                    # created in the backend but since it could not be saved
                    # in ETCD db we are throwing an error saying operation
                    # failed.
                    msg = (_('save volume to etcd failed, error is: %s'),
                           six.text_type(ex))
                    LOG.error(msg)
                    response = json.dumps({u"Err": six.text_type(ex)})
                return response

            except Exception as ex:
                msg = (_('create snapshot failed, error is: %s'),
                       six.text_type(ex))
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(ex)})

        except Exception:
            LOG.error('volume: %(name)s is locked',
                      {'name': src_vol_name})
            response = json.dumps({u"Err": ''})
            return response
        finally:
            # Release lock and return
            # NOTE: if for some reason unlock fails, we'll lose this
            # create exception.
            # Expand lock code inline as function based lock causes
            # unexpected behavior
            if lock_acquired:
                try:
                    self._etcd.try_unlock_volname(src_vol_name)
                except Exception as ex:
                    LOG.error('volume: %(name)s Unlock Volume Failed',
                              {'name': src_vol_name})
                    # response = json.dumps({u"Err": six.text_type(ex)})
                    # return response

    @app.route("/VolumeDriver.Mount", methods=["POST"])
    def volumedriver_mount(self, name):
        """
        Mount the volume
        Mount the volume

        NOTE: If for any reason the mount request fails, Docker
        will automatically call uMount. So, just make sure uMount
        can handle partially completed Mount requests.

        :param unicode name: The name of the volume.

        :return: Result that includes the mountpoint.
        """
        LOG.debug('In volumedriver_mount')

        # TODO: use persistent storage to lookup volume for deletion
        contents = {}
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            volid = vol['id']
        else:
            msg = (_LE('Volume mount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        vol_mount = volume.DEFAULT_MOUNT_VOLUME
        if ('Opts' in contents and contents['Opts'] and
                'mount-volume' in contents['Opts']):
            vol_mount = str(contents['Opts']['mount-volume'])

        # Get connector info from OS Brick
        # TODO: retrieve use_multipath and enforce_multipath from config file
        root_helper = 'sudo'

        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, multipath=self.use_multipath,
            enforce_multipath=self.enforce_multipath)

        try:
            # Call driver to initialize the connection
            self.hpeplugin_driver.create_export(vol, connector_info)
            connection_info = \
                self.hpeplugin_driver.initialize_connection(
                    vol, connector_info)
            LOG.debug('connection_info: %(connection_info)s, '
                      'was successfully retrieved',
                      {'connection_info': json.dumps(connection_info)})
        except Exception as ex:
            msg = (_('connection info retrieval failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        # Call OS Brick to connect volume
        try:
            device_info = self.connector.\
                connect_volume(connection_info['data'])
        except Exception as ex:
            msg = (_('OS Brick connect volume failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        # Make sure the path exists
        path = FilePath(device_info['path']).realpath()
        if path.exists is False:
            msg = (_('path: %s,  does not exist'), path)
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        LOG.debug('path for volume: %(name)s, was successfully created: '
                  '%(device)s realpath is: %(realpath)s',
                  {'name': volname, 'device': device_info['path'],
                   'realpath': path.path})

        # Create filesystem on the new device
        if fileutil.has_filesystem(path.path) is False:
            fileutil.create_filesystem(path.path)
            LOG.debug('filesystem successfully created on : %(path)s',
                      {'path': path.path})

        # Determine if we need to mount the volume
        if vol_mount == volume.DEFAULT_MOUNT_VOLUME:
            # mkdir for mounting the filesystem
            mount_dir = fileutil.mkdir_for_mounting(device_info['path'])
            LOG.debug('Directory: %(mount_dir)s, '
                      'successfully created to mount: '
                      '%(mount)s',
                      {'mount_dir': mount_dir, 'mount': device_info['path']})

            # mount the directory
            fileutil.mount_dir(path.path, mount_dir)
            LOG.debug('Device: %(path) successfully mounted on %(mount)s',
                      {'path': path.path, 'mount': mount_dir})

            # TODO: find out how to invoke mkfs so that it creates the
            # filesystem without the lost+found directory
            # KLUDGE!!!!!
            lostfound = mount_dir + '/lost+found'
            lfdir = FilePath(lostfound)
            if lfdir.exists and fileutil.remove_dir(lostfound):
                LOG.debug('Successfully removed : '
                          '%(lost)s from mount: %(mount)s',
                          {'lost': lostfound, 'mount': mount_dir})
        else:
            mount_dir = ''

        path_info = {}
        path_info['name'] = volname
        path_info['path'] = path.path
        path_info['device_info'] = device_info
        path_info['connection_info'] = connection_info
        path_info['mount_dir'] = mount_dir

        self._etcd.update_vol(volid, 'path_info', json.dumps(path_info))

        response = json.dumps({u"Err": '', u"Name": volname,
                               u"Mountpoint": mount_dir,
                               u"Devicename": path.path})
        return response

    @app.route("/VolumeDriver.Path", methods=["POST"])
    def volumedriver_path(self, name):
        """
        Return the path of a locally mounted volume if possible.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        volinfo = self._etcd.get_vol_byname(volname)
        if volinfo is None:
            msg = (_LE('Volume Path: Volume name not found %s'), volname)
            LOG.warning(msg)
            response = json.dumps({u"Err": "No Mount Point",
                                   u"Mountpoint": ""})
            return response

        path_name = ''
        path_info = self._etcd.get_vol_path_info(volname)

        if path_info is not None:
            path_name = path_info['mount_dir']

        response = json.dumps({u"Err": '', u"Mountpoint": path_name})
        return response

    def _get_snapshots_to_be_deleted(self, db_snapshots, bkend_snapshots):
        ss_list = []
        for db_ss in db_snapshots:
            found = False
            bkend_ss_name = utils.get_3par_snap_name(db_ss['id'])

            for bkend_ss in bkend_snapshots:
                if bkend_ss_name == bkend_ss:
                    found = True
                    break
            if not found:
                ss_list.append(db_ss)
        return ss_list

    def _sync_snapshots_from_array(self, vol_id, db_snapshots):
        bkend_snapshots = \
            self.hpeplugin_driver.get_snapshots_by_vol(vol_id)
        ss_list_remove = self._get_snapshots_to_be_deleted(db_snapshots,
                                                           bkend_snapshots)
        if ss_list_remove:
            for ss in ss_list_remove:
                db_snapshots.remove(ss)
            self._etcd.update_vol(vol_id, 'snapshots',
                                  db_snapshots)

    def get_required_qos_field(self, qos_detail):
        qos_filter = {}

        msg = (_LI('get_required_qos_field: %(qos_detail)s'), {'qos_detail':qos_detail})
        LOG.info(msg)

        qos_filter['enabled'] = qos_detail.get('enabled')

        if qos_detail.get('bwMaxLimitKB'):
            qos_filter['maxBWS'] = str(qos_detail.get('bwMaxLimitKB')/1024) + " MB/sec"

        if qos_detail.get('bwMinGoalKB'):
            qos_filter['minBWS'] = str(qos_detail.get('bwMinGoalKB')/1024) + " MB/sec"

        if qos_detail.get('ioMaxLimit'):
            qos_filter['maxIOPS'] = str(qos_detail.get('ioMaxLimit')) + " IOs/sec"

        if qos_detail.get('ioMinGoal'):
            qos_filter['minIOPS'] = str(qos_detail.get('ioMinGoal')) + " IOs/sec"

        if qos_detail.get('latencyGoal'):
            qos_filter['Latency'] = str(qos_detail.get('latencyGoal')) + "sec"

        if qos_detail.get('priority'):
            qos_filter['priority'] = volume.QOS_PRIORITY[qos_detail.get('priority')]

        return qos_filter

    def get_required_vol_field(self, vol_detail, isclone=False):
        vol_filter = {}

        msg = (_LI('get_required_vol_field: %(vol_detail)s'), {'vol_detail':vol_detail})
        LOG.info(msg)

        if isclone:
            vol_filter['compressionState'] = volume.VOL_COMPRESSION_STATE[vol_detail.get('compressionState')]
            vol_filter['copyType'] = volume.VOL_COPY_TYPE[vol_detail.get('copyType')]
            vol_filter['deduplicationState'] = volume.VOL_DEDUPLICATION_STATE[vol_detail.get('deduplicationState')]

        vol_filter['provisioning'] = volume.VOL_PROV_TYPE[vol_detail.get('provisioningType')]
        vol_filter['size'] = str(vol_detail.get('sizeMiB')) + " MiB"

        return vol_filter

    @app.route("/VolumeDriver.Get", methods=["POST"])
    def volumedriver_get(self, name):
        """
        Return volume information.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        err = ''
        mountdir = ''
        devicename = ''
        contents = json.loads(name.content.getvalue())
        volname = contents['Name']
        tokens = volname.split('/')
        token_cnt = len(tokens)

        if token_cnt > 2:
            msg = (_LE("invalid volume or snapshot name %s"
                       % volname))
            LOG.error(msg)
            response = json.dumps({u"Err": msg})
            return response

        volname = tokens[0]
        snapname = None
        if token_cnt == 2:
            snapname = tokens[1]

        volinfo = self._etcd.get_vol_byname(volname)

        if volinfo is None:
            msg = (_LE('Volume Get: Volume name not found %s'), volname)
            LOG.warning(msg)
            response = json.dumps({u"Err": ""})
            return response

        path_info = self._etcd.get_vol_path_info(volname)
        if path_info is not None:
            mountdir = path_info['mount_dir']
            devicename = path_info['path']

        # use volinfo as volname could be partial match
        volume = {'Name': contents['Name'],
                  'Mountpoint': mountdir,
                  'Devicename': devicename,
                  'Size': volinfo['size'],
                  'Status': {}}

        if volinfo['snapshots']:
            self._sync_snapshots_from_array(volinfo['id'],
                                            volinfo['snapshots'])
        # Is this request for snapshot inspect?
        if snapname:
            # Any snapshots left after synchronization with array?
            if volinfo['snapshots']:
                snapshot, idx = \
                    self._get_snapshot_by_name(volinfo['snapshots'],
                                               snapname)
                settings = {"Settings": {
                    'expirationHours': snapshot['expiration_hours'],
                    'retentionHours': snapshot['retention_hours']}}
                volume['Status'].update(settings)
            else:
                msg = (_LE('Snapshot Get: Snapshot name not found %s'),
                       contents['Name'])
                LOG.warning(msg)
                # Should error be returned here or success?
                response = json.dumps({u"Err": ""})
                return response

        else:
            snapshots = volinfo.get('snapshots', None)
            if snapshots:
                ss_list_to_show = []
                for s in snapshots:
                    snapshot = {'Name': s['name'],
                                'ParentName': volname}
                    ss_list_to_show.append(snapshot)
                volume['Status'].update({'Snapshots': ss_list_to_show})

        qos_name = volinfo.get('qos_name')
        if qos_name is not None:
            qos_detail = self.hpeplugin_driver.get_qos_detail(qos_name)
            qos_filter = self.get_required_qos_field(qos_detail)
            volume['Status'].update({'qos_detail': qos_filter})

        isclone = volinfo.get('isclone')
        vol_detail = self.hpeplugin_driver.get_volume_detail(volinfo['id'])
        vol_filter = self.get_required_vol_field(vol_detail, isclone=isclone)
        volume['Status'].update({'volume_detail': vol_filter})

        response = json.dumps({u"Err": err, u"Volume": volume})
        LOG.debug("Get volume/snapshot: \n%s" % str(response))
        return response

    @app.route("/VolumeDriver.List", methods=["POST"])
    def volumedriver_list(self, body):
        """
        Return a list of all volumes.

        :param unicode name: The name of the volume.

        :return: Result indicating success.
        """
        volumes = self._etcd.get_all_vols()

        if volumes is None:
            response = json.dumps({u"Err": ''})
            return response

        volumelist = []
        for volinfo in volumes.children:
            if volinfo.key != util.VOLUMEROOT:
                path_info = self._etcd.get_path_info_from_vol(volinfo.value)
                if path_info is not None and 'mount_dir' in path_info:
                    mountdir = path_info['mount_dir']
                    devicename = path_info['path']
                else:
                    mountdir = ''
                    devicename = ''
                info = json.loads(volinfo.value)
                volume = {'Name': info['display_name'],
                          'Devicename': devicename,
                          'size': info['size'],
                          'Mountpoint': mountdir,
                          'Status': {}}
                volumelist.append(volume)

        response = json.dumps({u"Err": '', u"Volumes": volumelist})
        return response

    def revert_to_snapshot(self, name, opts=None):
        contents = json.loads(name.content.getvalue())
        if 'Name' not in contents:
            msg = (_('revert snapshot failed, error is : Name is required'))
            LOG.errpr(msg)
            raise exception.HPEPluginCreateException(reason=msg)
        snapname = contents['Name']
        volumename = str(contents['Opts']['promote'])
        lock_aquired = False
        try:
            self._etcd.try_lock_volname(volumename)
            lock_aquired = True

            volume = self._etcd.get_vol_byname(volumename)
            if volume is None:
                msg = (_LE('Volume: %s does not exist' % volumename))
                LOG.info(msg)
                response = json.dumps({u"Err": msg})
                return response

            snapshots = volume['snapshots']
            LOG.info("Getting snapshot by name: %s" % snapname)
            snapshot, idx = self._get_snapshot_by_name(snapshots, snapname)
            if snapshot:
                try:
                    LOG.info("Found snapshot by name %s" % snapname)
                    self.hpeplugin_driver.revert_snap_to_vol(volume, snapshot)
                    response = json.dumps({u"Err": ''})
                    return response
                except Exception as ex:
                    msg = (_('revert snapshot failed, error is: %s'),
                           six.text_type(ex))
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(ex)})
            else:
                msg = (_LE('snapshot: %s does not exist!' % snapname))
                LOG.info(msg)
                response = json.dumps({u"Err": msg})
                return response
        except Exception:
            LOG.info('volume: %(name)s is locked',
                     {'name': volumename})
            response = json.dumps({u"Err": ''})
            return response
        finally:
            if lock_aquired:
                try:
                    self._etcd.try_unlock_volname(volumename)
                except Exception:
                    LOG.error('volume: %(name)s unlock volume Failed',
                              {'name': volumename})
