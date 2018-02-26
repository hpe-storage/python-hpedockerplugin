import json
import os
import six
import time
import uuid

import etcdutil as util
from os_brick.initiator import connector
from oslo_log import log as logging
from oslo_utils import importutils
from oslo_utils import netutils
from twisted.python.filepath import FilePath

import exception
import fileutil
from hpe import volume
from hpe import utils
from i18n import _, _LE, _LI, _LW
import synchronization

LOG = logging.getLogger(__name__)


class VolumeManager(object):
    def __init__(self, hpepluginconfig):
        self._hpepluginconfig = hpepluginconfig
        self._my_ip = netutils.get_my_ipv4()

        # Override the settings of use_multipath3, enforce_multipath
        # This will be a workaround until Issue #50 is fixed.
        msg = (_('Overriding the value of multipath flags to True'))
        LOG.info(msg)
        self._use_multipath = True
        self._enforce_multipath = True

        self._initialize_driver(hpepluginconfig)
        self._connector = self._get_connector(hpepluginconfig)
        self._etcd = self._get_etcd_util(hpepluginconfig)

        # Volume fencing requirement
        self._node_id = self._get_node_id()

    def _initialize_driver(self, hpepluginconfig):
        hpeplugin_driver = hpepluginconfig.hpedockerplugin_driver
        self._hpeplugin_driver = \
            importutils.import_object(hpeplugin_driver, hpepluginconfig)

        if self._hpeplugin_driver is None:
            msg = (_('_hpeplugin_driver import driver failed'))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

        try:
            self._hpeplugin_driver.do_setup()
            self._hpeplugin_driver.check_for_setup_error()
        except Exception as ex:
            msg = (_('_hpeplugin_driver do_setup failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

    def _get_connector(self, hpepluginconfig):
        protocol = 'ISCSI'
        if 'HPE3PARFCDriver' in hpepluginconfig.hpedockerplugin_driver:
            protocol = 'FIBRE_CHANNEL'

        root_helper = 'sudo'
        return connector.InitiatorConnector.factory(
            protocol, root_helper, use_multipath=self._use_multipath,
            device_scan_attempts=5, transport='default')

    @staticmethod
    def _get_node_id():
        # Save node-id if it doesn't exist
        node_id_file_path = '/etc/hpedockerplugin/.node_id'
        if not os.path.isfile(node_id_file_path):
            node_id = str(uuid.uuid4())
            with open(node_id_file_path, 'w') as node_id_file:
                node_id_file.write(node_id)
        else:
            with open(node_id_file_path, 'r') as node_id_file:
                node_id = node_id_file.readline()
        return node_id

    @staticmethod
    def _get_etcd_util(hpepluginconfig):
        return util.EtcdUtil(
            hpepluginconfig.host_etcd_ip_address,
            hpepluginconfig.host_etcd_port_number,
            hpepluginconfig.host_etcd_client_cert,
            hpepluginconfig.host_etcd_client_key)

    @synchronization.synchronized('{volname}')
    def create_volume(self, volname, vol_size, vol_prov,
                      vol_flash, compression_val, vol_qos):
        LOG.debug('In _volumedriver_create')

        # NOTE: Since Docker passes user supplied names and not a unique
        # uuid, we can't allow duplicate volume names to exist
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            return json.dumps({u"Err": ''})

        undo_steps = []
        vol = volume.createvol(volname, vol_size, vol_prov,
                               vol_flash, compression_val, vol_qos)
        try:
            self._create_volume(vol, undo_steps)
            self._apply_volume_specs(vol, undo_steps)

            # For now just track volume to uuid mapping internally
            # TODO: Save volume name and uuid mapping in etcd as well
            # This will make get_vol_byname more efficient
            self._etcd.save_vol(vol)

        except Exception as ex:
            msg = (_('Create volume failed with error: %s'), six.text_type(ex))
            LOG.exception(msg)
            self._rollback(undo_steps)
            return json.dumps({u"Err": six.text_type(ex)})
        else:
            LOG.debug('Volume: %(name)s was successfully saved to etcd',
                      {'name': volname})
            return json.dumps({u"Err": ''})

    @synchronization.synchronized('{src_vol_name}')
    def clone_volume(self, src_vol_name, clone_name,
                     size=None):
        # Check if volume is present in database
        src_vol = self._etcd.get_vol_byname(src_vol_name)
        if src_vol is None:
            msg = 'source volume: %s does not exist' % src_vol_name
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        if not size:
            size = src_vol['size']

        if size < src_vol['size']:
            msg = 'clone volume size %s is less than source ' \
                  'volume size %s' % (size, src_vol['size'])
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response
        return self._clone_volume(clone_name, src_vol, size)

    @synchronization.synchronized('{src_vol_name}')
    def create_snapshot(self, src_vol_name, snapshot_name,
                        expiration_hrs, retention_hrs):
        # Check if volume is present in database
        vol = self._etcd.get_vol_byname(src_vol_name)
        if vol is None:
            msg = 'source volume: %s does not exist' % src_vol_name
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        if vol['snapshots']:
            ss_list = vol['snapshots']
            for ss in ss_list:
                if snapshot_name == ss['name']:
                    msg = (_('Snapshot create failed. Error '
                             'is: %(snap_name)s is already created. '
                             'Please enter a new snapshot name.') %
                           {'snap_name': snapshot_name})
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(msg)})

        undo_steps = []
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
            bkend_snap_name = self._hpeplugin_driver.create_snapshot(snapshot)
            undo_steps.append(
                {'undo_func': self._hpeplugin_driver.delete_volume,
                 'params': {'volume': snapshot,
                            'is_snapshot': True},
                 'msg': 'Cleaning up backend snapshot: %s...'
                        % bkend_snap_name})
        except Exception as ex:
            msg = (_('create snapshot failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            return json.dumps({u"Err": six.text_type(ex)})

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
            # TODO: Snapshot needs clean up
            msg = (_('save volume to etcd failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            self._rollback(undo_steps)
            response = json.dumps({u"Err": six.text_type(ex)})
        return response

    @synchronization.synchronized('{volname}')
    def remove_volume(self, volname):
        # Only 1 node in a multinode cluster can try to remove the volume.
        # Grab lock for volume name. If lock is inuse, just return with no
        # error.
        # Expand lock code inline as function based lock causes
        # unexpected behavior
        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            # Just log an error, but don't fail the docker rm command
            msg = (_LE('Volume remove name not found %s'), volname)
            LOG.error(msg)
            return json.dumps({u"Err": ''})

        try:
            if vol['snapshots']:
                msg = (_LE('Err: Volume %s has one or more child '
                           'snapshots - volume cannot be deleted!'
                           % volname))
                LOG.error(msg)
                response = json.dumps({u"Err": msg})
                return response
            else:
                self._hpeplugin_driver.delete_volume(vol)
                LOG.info(_LI('volume: %(name)s,' 'was successfully deleted'),
                         {'name': volname})
        except Exception as ex:
            msg = (_LE('Err: Failed to remove volume %s, error is %s'),
                   volname, six.text_type(ex))
            LOG.error(msg)
            return json.dumps({u"Err": six.text_type(ex)})

        try:
            self._etcd.delete_vol(vol)
        except KeyError:
            msg = (_LW('Warning: Failed to delete volume key: %s from '
                       'etcd due to KeyError'), volname)
            LOG.warning(msg)
            pass
        return json.dumps({u"Err": ''})

    @synchronization.synchronized('{volname}')
    def remove_snapshot(self, volname, snapname):
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
                        response = json.dumps({u"Err": msg})
                        return response
                try:
                    LOG.info("Deleting snapshot at backend: %s" % snapname)
                    self._hpeplugin_driver.delete_volume(snapshot,
                                                         is_snapshot=True)
                except Exception as err:
                    msg = (_LE('Failed to remove snapshot error is: %s'),
                           six.text_type(err))
                    LOG.error(msg)
                    response = json.dumps({u"Err": six.text_type(err)})
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
                response = json.dumps({u"Err": msg})
                return response

    @synchronization.synchronized('{clone_name}')
    def _clone_volume(self, clone_name, src_vol, size):
        # Create clone volume specification
        undo_steps = []
        clone_vol = volume.createvol(clone_name, size,
                                     src_vol['provisioning'],
                                     src_vol['flash_cache'],
                                     src_vol['compression'],
                                     src_vol['qos_name'])
        try:
            self.__clone_volume__(src_vol, clone_vol, undo_steps)
            self._apply_volume_specs(clone_vol, undo_steps)

            # For now just track volume to uuid mapping internally
            # TODO: Save volume name and uuid mapping in etcd as well
            # This will make get_vol_byname more efficient
            self._etcd.save_vol(clone_vol)

        except Exception as ex:
            msg = (_('Clone volume failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            self._rollback(undo_steps)
            return json.dumps({u"Err": six.text_type(ex)})
        else:
            return json.dumps({u"Err": ''})

    @synchronization.synchronized('{volumename}')
    def revert_to_snapshot(self, volumename, snapname):
        volume = self._etcd.get_vol_byname(volumename)
        if volume is None:
            msg = (_LE('Volume: %s does not exist' % volumename))
            LOG.info(msg)
            response = json.dumps({u"Err": msg})
            return response

        snapshots = volume['snapshots']
        LOG.info("Getting snapshot by name: %s" % snapname)
        snapshot, idx = self._get_snapshot_by_name(snapshots,
                                                   snapname)
        if snapshot:
            try:
                LOG.info("Found snapshot by name %s" % snapname)
                self._hpeplugin_driver.revert_snap_to_vol(volume, snapshot)
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

    def get_volume_snap_details(self, volname, snapname, qualified_name):

        volinfo = self._etcd.get_vol_byname(volname)
        if volinfo is None:
            msg = (_LE('Volume Get: Volume name not found %s'), volname)
            LOG.warning(msg)
            response = json.dumps({u"Err": ""})
            return response

        err = ''
        mountdir = ''
        devicename = ''

        path_info = self._etcd.get_vol_path_info(volname)
        if path_info is not None:
            mountdir = path_info['mount_dir']
            devicename = path_info['path']

        # use volinfo as volname could be partial match
        volume = {'Name': qualified_name,
                  'Mountpoint': mountdir,
                  'Devicename': devicename,
                  'Status': {}}

        if volinfo['snapshots']:
            self._sync_snapshots_from_array(volinfo['id'],
                                            volinfo['snapshots'])
        # Is this request for snapshot inspect?
        if snapname:
            # Any snapshots left after synchronization with array?
            if volinfo['snapshots']:
                snapshot, idx = \
                    self._get_snapshot_by_name(
                        volinfo['snapshots'],
                        snapname)
                settings = {"Settings": {
                    'expirationHours': snapshot['expiration_hours'],
                    'retentionHours': snapshot['retention_hours']}}
                volume['Status'].update(settings)
            else:
                msg = (_LE('Snapshot Get: Snapshot name not found %s'),
                       qualified_name)
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
                try:
                    qos_detail = self._hpeplugin_driver.get_qos_detail(
                        qos_name)
                    qos_filter = self._get_required_qos_field(qos_detail)
                    volume['Status'].update({'qos_detail': qos_filter})
                except Exception as ex:
                    msg = (_('unable to get/filter qos from 3par, error is:'
                             ' %s'), six.text_type(ex))
                    LOG.error(msg)
                    return json.dumps({u"Err": six.text_type(ex)})

            vol_detail = {}
            vol_detail['size'] = volinfo.get('size')
            vol_detail['flash_cache'] = volinfo.get('flash_cache')
            vol_detail['compression'] = volinfo.get('compression')
            vol_detail['provisioning'] = volinfo.get('provisioning')
            volume['Status'].update({'volume_detail': vol_detail})

        response = json.dumps({u"Err": err, u"Volume": volume})
        LOG.debug("Get volume/snapshot: \n%s" % str(response))
        return response

    def list_volumes(self):
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

    def get_path(self, volname):
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

    @staticmethod
    def _is_vol_not_mounted(vol):
        return 'node_mount_info' not in vol

    @staticmethod
    def _is_first_mount(node_mount_info):
        return (len(node_mount_info) == 0)

    def _is_vol_mounted_on_this_node(self, node_mount_info):
        return self._node_id in node_mount_info

    def _update_mount_id_list(self, vol, mount_id):
        LOG.debug("NODE_MOUNT_INFO - NOT first mount ID - APPENDING "
                  "%s" % mount_id)
        node_mount_info = vol['node_mount_info']
        node_mount_info[self._node_id].append(mount_id)
        LOG.debug("NODE_MOUNT_INFO - NOT first mount ID - UPDATING "
                  "ETCD %s" % mount_id)
        self._etcd.update_vol(vol['id'],
                              'node_mount_info',
                              node_mount_info)

    def _get_success_response(self, vol):
        path_info = self._etcd.get_vol_path_info(vol['display_name'])
        path = FilePath(path_info['device_info']['path']).realpath()
        response = json.dumps({"Err": '', "Name": vol['display_name'],
                               "Mountpoint": path_info['mount_dir'],
                               "Devicename": path.path})
        return response

    def _wait_for_graceful_vol_unmount(self, volname):
        unmounted = False
        for checks in range(0, self._hpepluginconfig.mount_conflict_delay):
            time.sleep(1)
            LOG.debug("Checking if volume %s got unmounted #%s..."
                      % (volname, checks))
            vol = self._etcd.get_vol_byname(volname)

            # Check if unmount that was in progress has cleared the
            # node entry from ETCD database
            if 'node_mount_info' not in vol:
                LOG.debug("Volume %s got unmounted after %s "
                          "checks!!!" % (volname, checks))
                unmounted = True
                break

            LOG.debug("Volume %s still unmounting #%s..."
                      % (volname, checks))
        return unmounted

    def _force_remove_vlun(self, vol):
        # Force remove VLUNs for volume from the array
        bkend_vol_name = utils.get_3par_vol_name(vol['id'])
        self._hpeplugin_driver.force_remove_volume_vlun(
            bkend_vol_name)

    def _replace_node_mount_info(self, node_mount_info, mount_id):
        # Remove previous node info from volume meta-data
        old_node_id = node_mount_info.keys()[0]
        node_mount_info.pop(old_node_id)

        # Add new node information to volume meta-data
        node_mount_info[self._node_id] = [mount_id]

    def mount_volume(self, volname, vol_mount, mount_id):
        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            msg = (_LE('Volume mount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        volid = vol['id']

        # Volume fencing check
        #

        # Initialize node-mount-info if volume is being mounted
        # for the first time
        if self._is_vol_not_mounted(vol):
            LOG.debug("Initializing NODE_MOUNT_INFOadding first mount ID %s"
                      % mount_id)
            node_mount_info = {self._node_id: [mount_id]}
            vol['node_mount_info'] = node_mount_info
        else:
            # Volume is in mounted state
            node_mount_info = vol['node_mount_info']

            # If mounted on this node itself then just append mount-id
            if self._is_vol_mounted_on_this_node(node_mount_info):
                self._update_mount_id_list(vol, mount_id)
                return self._get_success_response(vol)
            else:
                # Volume mounted on different node
                # Forced VLUN cleanup from array to happen only in case
                # mount_conflict_delay is defined in hpe.conf
                if self._hpepluginconfig.mount_conflict_delay > 0:
                    LOG.debug("NODE_MOUNT_INFO - NOT first mount ID - "
                              "DIFFERENT NODE %s" % mount_id)

                    unmounted = self._wait_for_graceful_vol_unmount(volname)

                    if not unmounted:
                        self._force_remove_vlun(vol)

                    self._replace_node_mount_info(node_mount_info, mount_id)
                else:
                    msg = "Volume %s is already mounted on some other node"\
                          % volname
                    LOG.info(msg)
                    raise exception.HPEPluginMountException(reason=msg)

        LOG.debug("NODE_MOUNT_INFO - UPDATING ETCD for mount ID "
                  "%s" % mount_id)
        self._etcd.update_vol(volid,
                              'node_mount_info',
                              node_mount_info)
        root_helper = 'sudo'
        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, multipath=self._use_multipath,
            enforce_multipath=self._enforce_multipath)

        try:
            # Call driver to initialize the connection
            self._hpeplugin_driver.create_export(vol, connector_info)
            connection_info = \
                self._hpeplugin_driver.initialize_connection(
                    vol, connector_info)
            LOG.debug('connection_info: %(connection_info)s, '
                      'was successfully retrieved',
                      {'connection_info': json.dumps(connection_info)})
        except Exception as ex:
            msg = (_('connection info retrieval failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            # Imran: Can we raise exception rather than returning response?
            raise exception.HPEPluginMountException(reason=msg)

        # Call OS Brick to connect volume
        try:
            device_info = self._connector.\
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

    def unmount_volume(self, volname, vol_mount, mount_id):
        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            msg = (_LE('Volume unmount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginUMountException(reason=msg)

        volid = vol['id']

        ######
        # Start of volume fencing changes
        LOG.debug('WILLIAM %s ' % (vol))
        if 'node_mount_info' in vol:
            node_mount_info = vol['node_mount_info']
            if self._node_id in node_mount_info:
                # vol['node_mount_info'].pop(node_id)
                # LOG.debug('WILLIAM %s %s %s' % (vol['node_mount_info'],
                # node_id,type(json.load(vol['node_mount_info']))))
                LOG.debug("WILLIAM node_id in vol mount info")

                mount_id_list = node_mount_info[self._node_id]

                LOG.debug(" mount_id_list %s ", mount_id_list)

                try:
                    mount_id_list.remove(mount_id)
                except ValueError as ex:
                    pass

                # Update the mount_id list in etcd
                self._etcd.update_vol(volid, 'node_mount_info',
                                      node_mount_info)

                if len(mount_id_list) > 0:
                    # Don't proceed with unmount
                    LOG.info("WILLIAM.. no unmount done")
                    return json.dumps({u"Err": ''})
                else:
                    # delete the node_id key from node_mount_info
                    LOG.info("WILLIAM : deleting node_mount_info %s ",
                             vol['node_mount_info'])
                    vol.pop('node_mount_info')
                    LOG.info("WILLIAM vol %s ", vol)
                    self._etcd.save_vol(vol)

        # TODO: Requirement #5 will bring the flow here but the below flow
        # may result into exception. Need to ensure it doesn't happen
        path_info = self._etcd.get_vol_path_info(volname)
        # path_info = vol.get('path_info', None)
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
            root_helper, self._my_ip, multipath=self._use_multipath,
            enforce_multipath=self._enforce_multipath)

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
            self._connector.disconnect_volume(connection_info['data'], None)
            LOG.info(_LI('end of sync call to disconnect volume'))

        try:
            # Call driver to terminate the connection
            self._hpeplugin_driver.terminate_connection(vol, connector_info)
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

    def _create_volume(self, vol_specs, undo_steps):
        bkend_vol_name = self._hpeplugin_driver.create_volume(vol_specs)
        undo_steps.append(
            {'undo_func': self._hpeplugin_driver.delete_volume,
             'params': {'volume': vol_specs},
             'msg': 'Cleaning up backend volume: %s...' % bkend_vol_name})
        return bkend_vol_name

    def __clone_volume__(self, src_vol, clone_vol, undo_steps):
        bkend_vol_name = self._hpeplugin_driver.create_cloned_volume(
            clone_vol, src_vol)
        undo_steps.append(
            {'undo_func': self._hpeplugin_driver.delete_volume,
             'params': {'volume': clone_vol},
             'msg': 'Cleaning up backend volume: %s...' % bkend_vol_name})
        return bkend_vol_name

    def _apply_volume_specs(self, vol, undo_steps):
        vvs_name = vol.get('qos_name')

        if vol['flash_cache']:
            # If not a pre-created VVS, create one
            if not vvs_name:
                vvs_name = self._create_vvs(vol['id'], undo_steps)

            self._set_flash_cache_for_volume(vvs_name,
                                             vol['flash_cache'])

        # This can be either an existing VVSet with desired QoS
        # or a new VVSet that got created for flash-cache use case
        # Just add the volume to it
        if vvs_name:
            self._add_volume_to_vvset(vvs_name, vol, undo_steps)

    def _add_volume_to_vvset(self, vvs_name, vol, undo_steps):
        bkend_vol_name = self._hpeplugin_driver.add_volume_to_volume_set(
            vol, vvs_name)
        undo_steps.append(
            {'undo_func': self._hpeplugin_driver.remove_volume_from_volume_set,
             'params': {'vol_name': bkend_vol_name,
                        'vvs_name': vvs_name},
             'msg': 'Removing VV %s from VVS %s...'
                    % (bkend_vol_name, vvs_name)})

    def _create_vvs(self, id, undo_steps):
        vvs_name = self._hpeplugin_driver.create_vvs(id)
        undo_steps.append(
            {'undo_func': self._hpeplugin_driver.delete_vvset,
             'params': {'id': id},
             'msg': 'Cleaning up VVS: %s...' % vvs_name})
        return vvs_name

    def _set_flash_cache_for_volume(self, vvs_name, flash_cache):
        self._hpeplugin_driver.set_flash_cache_policy_on_vvs(
            flash_cache,
            vvs_name)

    @staticmethod
    def _rollback(rollback_list):
        for undo_action in reversed(rollback_list):
            LOG.info(undo_action['msg'])
            try:
                undo_action['undo_func'](**undo_action['params'])
            except Exception as ex:
                # TODO: Implement retry logic
                pass

    @staticmethod
    def _get_snapshot_by_name(snapshots, snapname):
        idx = 0
        for s in snapshots:
            if s['name'] == snapname:
                return s, idx
            idx = idx + 1
        return None, None

    @staticmethod
    def _get_snapshots_to_be_deleted(db_snapshots, bkend_snapshots):
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
            self._hpeplugin_driver.get_snapshots_by_vol(vol_id)
        ss_list_remove = self._get_snapshots_to_be_deleted(db_snapshots,
                                                           bkend_snapshots)
        if ss_list_remove:
            for ss in ss_list_remove:
                db_snapshots.remove(ss)
            self._etcd.update_vol(vol_id, 'snapshots',
                                  db_snapshots)

    @staticmethod
    def _get_required_qos_field(qos_detail):
        qos_filter = {}

        msg = (_LI('get_required_qos_field: %(qos_detail)s'),
               {'qos_detail': qos_detail})
        LOG.info(msg)

        qos_filter['enabled'] = qos_detail.get('enabled')

        bwMaxLimitKB = qos_detail.get('bwMaxLimitKB')
        if bwMaxLimitKB:
            qos_filter['maxBWS'] = str(bwMaxLimitKB / 1024) + " MB/sec"

        bwMinGoalKB = qos_detail.get('bwMinGoalKB')
        if bwMinGoalKB:
            qos_filter['minBWS'] = str(bwMinGoalKB / 1024) + " MB/sec"

        ioMaxLimit = qos_detail.get('ioMaxLimit')
        if ioMaxLimit:
            qos_filter['maxIOPS'] = str(ioMaxLimit) + " IOs/sec"

        ioMinGoal = qos_detail.get('ioMinGoal')
        if ioMinGoal:
            qos_filter['minIOPS'] = str(ioMinGoal) + " IOs/sec"

        latencyGoal = qos_detail.get('latencyGoal')
        if latencyGoal:
            qos_filter['Latency'] = str(latencyGoal) + " sec"

        priority = qos_detail.get('priority')
        if priority:
            qos_filter['priority'] = volume.QOS_PRIORITY[priority]

        qos_filter['vvset_name'] = qos_detail['name']

        return qos_filter
