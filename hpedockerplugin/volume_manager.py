import json
import six
import uuid

import etcdutil as util
from oslo_log import log as logging

from hpe import volume
from hpe import utils
from i18n import _, _LE, _LI, _LW
import synchronization

LOG = logging.getLogger(__name__)


class VolumeManager(object):
    def __init__(self, driver, etcd):
        self.hpeplugin_driver = driver
        self._etcd = etcd

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
            bkend_snap_name = self.hpeplugin_driver.create_snapshot(snapshot)
            undo_steps.append(
                {'undo_func': self.hpeplugin_driver.delete_volume,
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
                self.hpeplugin_driver.delete_volume(vol)
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
                    self.hpeplugin_driver.delete_volume(snapshot,
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
                    qos_detail = self.hpeplugin_driver.get_qos_detail(qos_name)
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
        path_name = ''
        path_info = self._etcd.get_vol_path_info(volname)

        if path_info is not None:
            path_name = path_info['mount_dir']

        response = json.dumps({u"Err": '', u"Mountpoint": path_name})
        return response

    def _create_volume(self, vol_specs, undo_steps):
        bkend_vol_name = self.hpeplugin_driver.create_volume(vol_specs)
        undo_steps.append(
            {'undo_func': self.hpeplugin_driver.delete_volume,
             'params': {'volume': vol_specs},
             'msg': 'Cleaning up backend volume: %s...' % bkend_vol_name})
        return bkend_vol_name

    def __clone_volume__(self, src_vol, clone_vol, undo_steps):
        bkend_vol_name = self.hpeplugin_driver.create_cloned_volume(
            clone_vol, src_vol)
        undo_steps.append(
            {'undo_func': self.hpeplugin_driver.delete_volume,
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
        bkend_vol_name = self.hpeplugin_driver.add_volume_to_volume_set(
            vol, vvs_name)
        undo_steps.append(
            {'undo_func': self.hpeplugin_driver.remove_volume_from_volume_set,
             'params': {'vol_name': bkend_vol_name,
                        'vvs_name': vvs_name},
             'msg': 'Removing VV %s from VVS %s...'
                    % (bkend_vol_name, vvs_name)})

    def _create_vvs(self, id, undo_steps):
        vvs_name = self.hpeplugin_driver.create_vvs(id)
        undo_steps.append(
            {'undo_func': self.hpeplugin_driver.delete_vvset,
             'params': {'id': id},
             'msg': 'Cleaning up VVS: %s...' % vvs_name})
        return vvs_name

    def _set_flash_cache_for_volume(self, vvs_name, flash_cache):
        self.hpeplugin_driver.set_flash_cache_policy_on_vvs(
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
            self.hpeplugin_driver.get_snapshots_by_vol(vol_id)
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

        return qos_filter
