import json
import string
import os
import six
import time
from sh import chmod
from Crypto.Cipher import AES
import base64


from os_brick.initiator import connector
from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import importutils
from oslo_utils import netutils
from oslo_utils import units
from twisted.python.filepath import FilePath

import hpedockerplugin.exception as exception
import hpedockerplugin.fileutil as fileutil
import math
import re
import hpedockerplugin.hpe.array_connection_params as acp
import datetime
from hpedockerplugin.hpe import volume
from hpedockerplugin.hpe import utils
from hpedockerplugin.i18n import _, _LE, _LI, _LW
import hpedockerplugin.synchronization as synchronization


LOG = logging.getLogger(__name__)
PRIMARY = 1
PRIMARY_REV = 1
SECONDARY = 2

CONF = cfg.CONF


class VolumeManager(object):
    def __init__(self, host_config, hpepluginconfig, etcd_util,
                 node_id,
                 backend_name='DEFAULT'):
        self._host_config = host_config
        self._hpepluginconfig = hpepluginconfig
        self._my_ip = netutils.get_my_ipv4()

        # Override the settings of use_multipath3, enforce_multipath
        # This will be a workaround until Issue #50 is fixed.
        msg = (_('Overriding the value of multipath flags to True'))
        LOG.info(msg)
        self._use_multipath = True
        self._enforce_multipath = True
        self._etcd = etcd_util

        self._initialize_configuration()
        self._decrypt_password(self.src_bkend_config,
                               self.tgt_bkend_config, backend_name)

        # TODO: When multiple backends come into picture, consider
        # lazy initialization of individual driver
        try:
            LOG.info("Initializing 3PAR driver...")
            self._primary_driver = self._initialize_driver(
                host_config, self.src_bkend_config, self.tgt_bkend_config)

            self._hpeplugin_driver = self._primary_driver
            LOG.info("Initialized 3PAR driver!")
        except Exception as ex:
            msg = "Failed to initialize 3PAR driver for array: %s!" \
                  "Exception: %s"\
                  % (self.src_bkend_config.hpe3par_api_url,
                     six.text_type(ex))
            LOG.info(msg)
            raise exception.HPEPluginStartPluginException(
                reason=msg)

        # If replication enabled, then initialize secondary driver
        if self.tgt_bkend_config:
            LOG.info("Replication enabled!")
            try:
                LOG.info("Initializing 3PAR driver for remote array...")
                self._remote_driver = self._initialize_driver(
                    host_config, self.tgt_bkend_config,
                    self.src_bkend_config)
            except Exception as ex:
                msg = "Failed to initialize 3PAR driver for remote array %s!" \
                      "Exception: %s"\
                      % (self.tgt_bkend_config.hpe3par_api_url,
                         six.text_type(ex))
                LOG.info(msg)
                raise exception.HPEPluginStartPluginException(reason=msg)

        self._connector = self._get_connector(hpepluginconfig)

        # Volume fencing requirement
        self._node_id = node_id

    def _initialize_configuration(self):
        self.src_bkend_config = self._get_src_bkend_config()

        self.tgt_bkend_config = None
        if self._hpepluginconfig.replication_device:
            self.tgt_bkend_config = acp.ArrayConnectionParams(
                self._hpepluginconfig.replication_device)
            if self.tgt_bkend_config:

                # Copy all the source configuration to target
                hpeconf = self._hpepluginconfig
                for key in hpeconf.keys():
                    if not self.tgt_bkend_config.is_param_present(key):
                        value = getattr(hpeconf, key)
                        self.tgt_bkend_config.__setattr__(key, value)

                self.tgt_bkend_config.hpe3par_cpg = self._extract_remote_cpgs(
                    self.tgt_bkend_config.cpg_map)
                if not self.tgt_bkend_config.hpe3par_cpg:
                    LOG.exception("Failed to initialize driver - cpg_map not "
                                  "defined for replication device")
                    raise exception.HPEPluginMountException(
                        "Failed to initialize driver - cpg_map not defined for"
                        "replication device")

                self.tgt_bkend_config.hpe3par_snapcpg = \
                    self._extract_remote_cpgs(
                        self.tgt_bkend_config.snap_cpg_map)
                if not self.tgt_bkend_config.hpe3par_snapcpg:
                    self.tgt_bkend_config.hpe3par_snapcpg = \
                        self.tgt_bkend_config.hpe3par_cpg

                if 'iscsi' in self.src_bkend_config.hpedockerplugin_driver:
                    iscsi_ips = self.tgt_bkend_config.hpe3par_iscsi_ips
                    self.tgt_bkend_config.hpe3par_iscsi_ips = iscsi_ips.split(
                        ';')

    def _get_src_bkend_config(self):
        LOG.info("Getting source backend configuration...")
        hpeconf = self._hpepluginconfig
        config = acp.ArrayConnectionParams()
        for key in hpeconf.keys():
            value = getattr(hpeconf, key)
            config.__setattr__(key, value)

        if hpeconf.hpe3par_snapcpg:
            config.hpe3par_snapcpg = hpeconf.hpe3par_snapcpg
        else:
            # config.hpe3par_snapcpg = hpeconf.hpe3par_cpg
            # if 'hpe3par_snapcpg' is NOT given in hpe.conf this should be
            # default to empty list & populate volume's snap_cpg later with
            # value given with '-o cpg'
            config.hpe3par_snapcpg = hpeconf.hpe3par_cpg

        LOG.info("Got source backend configuration!")
        return config

    @staticmethod
    def _extract_remote_cpgs(cpg_map):
        hpe3par_cpgs = []
        cpg_pairs = cpg_map.split(' ')
        for cpg_pair in cpg_pairs:
            cpgs = cpg_pair.split(':')
            hpe3par_cpgs.append(cpgs[1])

        return hpe3par_cpgs

    def _initialize_driver(self, host_config, src_config, tgt_config):
        hpeplugin_driver_class = src_config.hpedockerplugin_driver
        hpeplugin_driver = importutils.import_object(
            hpeplugin_driver_class, host_config, src_config, tgt_config)

        if hpeplugin_driver is None:
            msg = (_('hpeplugin_driver import driver failed'))
            LOG.error(msg)
            raise exception.HPEPluginNotInitializedException(reason=msg)

        try:
            hpeplugin_driver.do_setup(timeout=30)
            hpeplugin_driver.check_for_setup_error()
            return hpeplugin_driver
        except Exception as ex:
            msg = (_('hpeplugin_driver do_setup failed, error is: %s'),
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

    @synchronization.synchronized_volume('{volname}')
    def create_volume(self, volname, vol_size, vol_prov,
                      vol_flash, compression_val, vol_qos,
                      fs_owner, fs_mode,
                      mount_conflict_delay, cpg, snap_cpg,
                      current_backend, rcg_name):
        LOG.info('In _volumedriver_create')

        # NOTE: Since Docker passes user supplied names and not a unique
        # uuid, we can't allow duplicate volume names to exist
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            return json.dumps({u"Err": ''})

        # if qos-name is given, check vvset is associated with qos or not
        if vol_qos is not None:
            try:
                self._hpeplugin_driver.get_qos_detail(vol_qos)
                # if vol_flash is not given in option & with qos
                # if vvset is having flash-cache enabled, then set
                # vol_flash=True
                if vol_flash is None:
                    vvset_detail = self._hpeplugin_driver.get_vvset_detail(
                        vol_qos)
                    if(vvset_detail.get('flashCachePolicy') is not None and
                       vvset_detail.get('flashCachePolicy') == 1):
                        vol_flash = True

            except Exception as ex:
                msg = (_('Create volume failed because vvset is not present or'
                         'is not associated with qos: %s'), six.text_type(ex))
                LOG.exception(msg)
                return json.dumps({u"Err": six.text_type(ex)})

        undo_steps = []
        vol = volume.createvol(volname, vol_size, vol_prov,
                               vol_flash, compression_val, vol_qos,
                               mount_conflict_delay, False, cpg, snap_cpg,
                               False, current_backend)

        bkend_vol_name = ""
        try:
            bkend_vol_name = self._create_volume(vol, undo_steps)
            self._apply_volume_specs(vol, undo_steps)
            if rcg_name:
                # bkend_rcg_name = self._get_3par_rcg_name(rcg_name)
                try:
                    rcg_info = self._find_rcg(rcg_name)
                except exception.HPEDriverRemoteCopyGroupNotFound:
                    rcg_info = self._create_rcg(rcg_name, undo_steps)

                self._add_volume_to_rcg(vol, rcg_name, undo_steps)
                vol['rcg_info'] = rcg_info

            # For now just track volume to uuid mapping internally
            # TODO: Save volume name and uuid mapping in etcd as well
            # This will make get_vol_byname more efficient
            vol['fsOwner'] = fs_owner
            vol['fsMode'] = fs_mode
            vol['3par_vol_name'] = bkend_vol_name

            self._etcd.save_vol(vol)

        except Exception as ex:
            msg = (_('Create volume failed with error: %s'), six.text_type(ex))
            LOG.exception(msg)
            self._rollback(undo_steps)
            return json.dumps({u"Err": six.text_type(ex)})
        else:
            LOG.info('Volume: %(name)s was successfully saved to etcd',
                     {'name': volname})
            return json.dumps({u"Err": ''})

    def map_3par_volume_time_to_docker(self, vol, expiration=True):
        try:

            date_format = "%Y-%m-%d %H:%M:%S"
            if expiration:
                find_flag = "expirationTime8601"
            else:
                find_flag = "retentionTime8601"

            start_groups = re.search('(\d+\-\d+\-\d+)[A-z](\d+:\d+:\d+)',
                                     str(vol["creationTime8601"]))
            startdate = start_groups.group(1) + " " + start_groups.group(2)
            startt = datetime.datetime.strptime(startdate, date_format)

            end_groups = re.search('(\d+\-\d+\-\d+)[A-z](\d+:\d+:\d+)',
                                   str(vol[find_flag]))
            enddate = end_groups.group(1) + " " + end_groups.group(2)
            endd = datetime.datetime.strptime(enddate, date_format)

            diff = endd - startt
            diff_hour = diff.seconds / 3600
            return diff_hour

        except Exception as ex:
            msg = (_(
                'Failed to map expiration hours of 3par volume: %(vol)s error'
                ' is: %(ex)s'), {'vol': vol, 'ex': six.text_type(ex)})
            LOG.error(msg)
            raise exception.HPEPluginMapHourException(reason=msg)

    def map_3par_volume_size_to_docker(self, vol):
        try:
            return int(math.ceil(float(vol['sizeMiB']) / units.Ki))
        except Exception as ex:
            msg = (_('Failed to map size of 3par volume: %(vol)s, error is: '
                     '%(ex)s'), {'vol': vol, 'ex': six.text_type(ex)})
            LOG.error(msg)
            raise exception.HPEPluginMapSizeException(reason=msg)

    def map_3par_volume_prov_to_docker(self, vol):
        try:
            prov = volume.PROVISIONING.get(vol.get('provisioningType'))
            if not prov:
                return volume.DEFAULT_PROV
            return prov
        except Exception as ex:
            msg = (_(
                'Failed to map provisioning of 3par volume: %(vol)s, error'
                ' is: %(ex)s'), {'vol': vol, 'ex': six.text_type(ex)})
            LOG.error(msg)
            raise exception.HPEPluginMapProvisioningException(reason=msg)

    def map_3par_volume_compression_to_docker(self, vol):
        # no need to raise exception here, because compression in docker
        # environment can be either True or False
        if volume.COMPRESSION.get(vol.get('compressionState')):
            return True
        return volume.DEFAULT_COMPRESSION_VAL

    def manage_existing(self, volname, existing_ref, backend='DEFAULT',
                        manage_opts=None):
        LOG.info('Managing a %(vol)s' % {'vol': existing_ref})

        # NOTE: Since Docker passes user supplied names and not a unique
        # uuid, we can't allow duplicate volume names to exist
        vol = self._etcd.get_vol_byname(volname)
        if vol is not None:
            return json.dumps({u"Err": ''})

        is_snap = False

        # Make sure the reference is not in use.
        if existing_ref.startswith('dcv-') or existing_ref.startswith('dcs-'):
            msg = (_('target: %s is already in-use') % existing_ref)
            LOG.error(msg)
            return json.dumps({u"Err": six.text_type(msg)})

        vol = volume.createvol(volname)
        vol['backend'] = backend
        vol['fsOwner'] = None
        vol['fsMode'] = None
        vol['Options'] = manage_opts

        parent_vol = ""
        try:
            # check target volume exists in 3par
            existing_ref_details = \
                self._hpeplugin_driver.get_volume_detail(existing_ref)
        except Exception as ex:
            msg = (_(
                'Volume:%(existing_ref)s does not exists Error: %(ex)s')
                % {'existing_ref': existing_ref, 'ex': six.text_type(ex)})
            LOG.exception(msg)
            return json.dumps({u"Err": six.text_type(msg)})

        if ('rcopyStatus' in existing_ref_details and
                existing_ref_details['rcopyStatus'] != 1):
            msg = 'ERROR: Volume associated with a replication group '\
                  'cannot be imported'
            raise exception.InvalidInput(reason=msg)

        vvset_detail = self._hpeplugin_driver.get_vvset_from_volume(
            existing_ref_details['name'])
        if vvset_detail is not None:
            vvset_name = vvset_detail.get('name')
            LOG.info('vvset_name: %(vvset)s' % {'vvset': vvset_name})

            # check and set the flash-cache if exists
            if(vvset_detail.get('flashCachePolicy') is not None and
               vvset_detail.get('flashCachePolicy') == 1):
                vol['flash_cache'] = True

            try:
                self._hpeplugin_driver.get_qos_detail(vvset_name)
                LOG.info('Volume:%(existing_ref)s is in vvset_name:'
                         '%(vvset_name)s associated with QOS'
                         % {'existing_ref': existing_ref,
                            'vvset_name': vvset_name})
                vol["qos_name"] = vvset_name
            except Exception as ex:
                msg = (_(
                    'volume is in vvset:%(vvset_name)s and not associated with'
                    ' QOS error:%(ex)s') % {
                        'vvset_name': vvset_name,
                        'ex': six.text_type(ex)})
                LOG.error(msg)
                if not vol['flash_cache']:
                    return json.dumps({u"Err": six.text_type(msg)})

        # since we have only 'importVol' option for importing,
        # both volume and snapshot
        # throw error when user tries to manage snapshot,
        # before managing parent
        copyType = existing_ref_details.get('copyType')
        if volume.COPYTYPE.get(copyType) == 'virtual':
            # it's a snapshot, so check whether its parent is managed or not ?
            try:
                # convert parent volume name to its uuid,
                # which is then check in etcd for existence
                vol_id = utils.get_vol_id(existing_ref_details["copyOf"])
                LOG.info('parent volume ID: %(parent_vol_id)s'
                         % {'parent_vol_id': vol_id})
                # check parent uuid is present in etcd, or not ?
                parent_vol = self._etcd.get_vol_by_id(vol_id)
                vol['flash_cache'] = parent_vol['flash_cache']
                # parent vol is present so manage a snapshot now
                is_snap = True
            except Exception as ex:
                msg = (_(
                    'Manage snapshot failed because parent volume: '
                    '%(parent_volume)s is unmanaged.') % {
                        'parent_volume': existing_ref_details["copyOf"]})
                LOG.exception(msg)
                return json.dumps({u"Err": six.text_type(msg)})

        try:
            volume_detail_3par = self._hpeplugin_driver.manage_existing(
                vol, existing_ref_details, is_snap=is_snap)
        except Exception as ex:
            msg = (_('Manage volume failed Error: %s') % six.text_type(ex))
            LOG.exception(msg)
            return json.dumps({u"Err": six.text_type(msg)})

        try:
            # mapping
            vol['size'] = \
                self.map_3par_volume_size_to_docker(volume_detail_3par)
            vol['provisioning'] = \
                self.map_3par_volume_prov_to_docker(volume_detail_3par)
            vol['compression'] = \
                self.map_3par_volume_compression_to_docker(volume_detail_3par)
            vol['cpg'] = volume_detail_3par.get('userCPG')
            vol['snap_cpg'] = volume_detail_3par.get('snapCPG')

            if is_snap:
                if vol['3par_vol_name'].startswith("dcv-"):
                    vol['3par_vol_name'] = \
                        str.replace(vol['3par_vol_name'], "dcv-", "dcs-", 1)
                # managing a snapshot
                if volume_detail_3par.get("expirationTime8601"):
                    expiration_hours = \
                        self.map_3par_volume_time_to_docker(volume_detail_3par)
                else:
                    expiration_hours = None

                if volume_detail_3par.get("retentionTime8601"):
                    retention_hours = self.map_3par_volume_time_to_docker(
                        volume_detail_3par, expiration=False)
                else:
                    retention_hours = None

                db_snapshot = {
                    'name': volname,
                    'id': vol['id'],
                    'parent_name': parent_vol['display_name'],
                    'parent_id': parent_vol['id'],
                    'fsOwner': parent_vol['fsOwner'],
                    'fsMode': parent_vol['fsMode'],
                    'expiration_hours': expiration_hours,
                    'retention_hours': retention_hours}
                if 'snapshots' not in parent_vol:
                    parent_vol['snapshots'] = []
                parent_vol['snapshots'].append(db_snapshot)
                vol['is_snap'] = is_snap
                vol['snap_metadata'] = db_snapshot
                self._etcd.save_vol(parent_vol)

            self._etcd.save_vol(vol)
        except Exception as ex:
            msg = (_('Manage volume failed Error: %s') % six.text_type(ex))
            LOG.exception(msg)
            undo_steps = []
            undo_steps.append(
                {'undo_func': self._hpeplugin_driver.manage_existing,
                 'params': {
                     'volume': volume_detail_3par,
                     'existing_ref': volume_detail_3par.get('name'),
                     'is_snap': is_snap,
                     'target_vol_name': existing_ref_details.get('name'),
                     'comment': existing_ref_details.get('comment')},
                 'msg': 'Cleaning up manage'})
            self._rollback(undo_steps)
            return json.dumps({u"Err": six.text_type(ex)})

        return json.dumps({u"Err": ''})

    @synchronization.synchronized_volume('{src_vol_name}')
    def clone_volume(self, src_vol_name, clone_name,
                     size=None, cpg=None, snap_cpg=None,
                     current_backend='DEFAULT', clone_opts=None):
        # Check if volume is present in database
        LOG.info('hpedockerplugin : clone options 5 %s ' % clone_opts)
        src_vol = self._etcd.get_vol_byname(src_vol_name)
        mnt_conf_delay = volume.DEFAULT_MOUNT_CONFLICT_DELAY
        if src_vol is None:
            msg = 'source volume: %s does not exist' % src_vol_name
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        # TODO(sonivi): remove below conversion to 3par volume name, once we
        # we have code in place to store 3par volume name in etcd vol object
        volume_3par = utils.get_3par_vol_name(src_vol.get('id'))

        # check if volume having any active task, it yes return with error
        # add prefix '*' because offline copy task name have pattern like
        # e.g. dcv-m0o5ZAwPReaZVoymnLTrMA->dcv-N.9ikeA.RiaxPP4LzecaEQ
        # this will check both offline as well as online copy task
        if self._hpeplugin_driver.is_vol_having_active_task(
           "*%s" % volume_3par):
            msg = 'source volume: %s / %s is having some active task ' \
                  'running on array' % (src_vol_name, volume_3par)
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        if not size:
            size = src_vol['size']
        if not cpg:
            cpg = src_vol.get('cpg', self._hpeplugin_driver.get_cpg
                              (src_vol, False, allowSnap=True))
        if not snap_cpg:
            snap_cpg = src_vol.get('snap_cpg', self._hpeplugin_driver.
                                   get_snapcpg(src_vol, False))

        if size < src_vol['size']:
            msg = 'clone volume size %s is less than source ' \
                  'volume size %s' % (size, src_vol['size'])
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        if 'is_snap' in src_vol and src_vol['is_snap']:
            msg = 'cloning a snapshot %s is not allowed ' \
                  % (src_vol_name)
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        if 'snapshots' not in src_vol:
            src_vol['compression'] = None
            src_vol['qos_name'] = None
            src_vol['mount_conflict_delay'] = mnt_conf_delay
            src_vol['snapshots'] = []
            self._etcd.save_vol(src_vol)

        return self._clone_volume(clone_name, src_vol, size, cpg,
                                  snap_cpg, current_backend, clone_opts)

    def _create_snapshot_record(self, snap_vol, snapshot_name, undo_steps):
        self._etcd.save_vol(snap_vol)
        undo_steps.append({'undo_func': self._etcd.delete_vol,
                           'params': {'vol': snap_vol},
                           'msg': "Cleaning up snapshot record for '%s'"
                                  " from ETCD..." % snapshot_name})

    @synchronization.synchronized_volume('{snapshot_name}')
    def create_snapshot(self, src_vol_name, schedName, snapshot_name,
                        snapPrefix, expiration_hrs, exphrs, retention_hrs,
                        rethrs, mount_conflict_delay, has_schedule,
                        schedFrequency, current_backend='DEFAULT'):

        # Check if volume is present in database
        snap = self._etcd.get_vol_byname(snapshot_name)
        if snap:
            msg = 'snapshot %s already exists' % snapshot_name
            LOG.info(msg)
            response = json.dumps({'Err': msg})
            return response

        return self._create_snapshot(src_vol_name, schedName, snapshot_name,
                                     snapPrefix, expiration_hrs, exphrs,
                                     retention_hrs, rethrs,
                                     mount_conflict_delay, has_schedule,
                                     schedFrequency, current_backend)

    @synchronization.synchronized_volume('{src_vol_name}')
    def _create_snapshot(self, src_vol_name, schedName, snapshot_name,
                         snapPrefix, expiration_hrs, exphrs, retention_hrs,
                         rethrs, mount_conflict_delay, has_schedule,
                         schedFrequency, current_backend):

        vol = self._etcd.get_vol_byname(src_vol_name)
        if vol is None:
            msg = 'source volume: %s does not exist' % src_vol_name
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response
        volid = vol['id']
        if 'has_schedule' not in vol:
            vol_sched_flag = volume.DEFAULT_SCHEDULE
            vol['has_schedule'] = vol_sched_flag
            self._etcd.update_vol(volid, 'has_schedule', vol_sched_flag)

        # TODO(sonivi): remove below conversion to 3par volume name, once we
        # we have code in place to store 3par volume name in etcd vol object
        volume_3par = utils.get_3par_vol_name(volid)

        # check if volume having any active task, it yes return with error
        # add prefix '*' because offline copy task name have pattern like
        # e.g. dcv-m0o5ZAwPReaZVoymnLTrMA->dcv-N.9ikeA.RiaxPP4LzecaEQ
        # this will check both offline as well as online copy task
        if self._hpeplugin_driver.is_vol_having_active_task(
           "*%s" % volume_3par):
            msg = 'source volume: %s / %s is having some active task ' \
                  'running on array' % (src_vol_name, volume_3par)
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

        # Check if this is an old volume type. If yes, add is_snap flag to it
        if 'is_snap' not in vol:
            vol_snap_flag = volume.DEFAULT_TO_SNAP_TYPE
            vol['is_snap'] = vol_snap_flag
            self._etcd.update_vol(volid, 'is_snap', vol_snap_flag)
        if 'snapshots' not in vol:
            vol['snapshots'] = []
            vol['compression'] = None
            vol['qos_name'] = None
            vol['mount_conflict_delay'] = mount_conflict_delay
            vol['backend'] = current_backend

        # Check if instead of specifying parent volume, user incorrectly
        # specified snapshot as virtualCopyOf parameter. If yes, return error.
        if 'is_snap' in vol and vol['is_snap']:
            msg = 'source volume: %s is a snapshot, creating hierarchy ' \
                  'of snapshots is not allowed.' % src_vol_name
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response
        snap_cpg = None
        if 'snap_cpg' in vol and vol['snap_cpg']:
            snap_cpg = vol['snap_cpg']
        else:
            snap_cpg = vol.get('snap_cpg', self._hpeplugin_driver.get_snapcpg
                               (vol, False))

        snap_size = vol['size']
        snap_prov = vol['provisioning']
        snap_flash = vol['flash_cache']
        snap_compression = vol['compression']
        snap_qos = volume.DEFAULT_QOS

        is_snap = True

        snap_vol = volume.createvol(snapshot_name, snap_size, snap_prov,
                                    snap_flash, snap_compression, snap_qos,
                                    mount_conflict_delay, is_snap, None,
                                    snap_cpg, has_schedule,
                                    current_backend)

        snapshot_id = snap_vol['id']

        if snap_vol['has_schedule']:
            try:
                src_3par_vol_name = utils.get_3par_vol_name(vol['id'])
                self._hpeplugin_driver.create_snap_schedule(src_3par_vol_name,
                                                            schedName,
                                                            snapPrefix,
                                                            exphrs, rethrs,
                                                            schedFrequency)
            except Exception as ex:
                msg = (_('create snapshot failed, error is: %s')
                       % six.text_type(ex))
                LOG.error(msg)
                return json.dumps({u"Err": six.text_type(ex)})

        # this 'snapshot dict'is for creating snap at 3par
        snapshot = {'id': snapshot_id,
                    'display_name': snapshot_name,
                    'volume_id': vol['id'],
                    'volume_name': src_vol_name,
                    'expirationHours': expiration_hrs,
                    'retentionHours': retention_hrs,
                    'display_description': 'snapshot of volume %s'
                                           % src_vol_name}
        undo_steps = []
        bkend_snap_name = ""
        try:
            bkend_snap_name = self._hpeplugin_driver.create_snapshot(
                snapshot)
            undo_steps.append(
                {'undo_func': self._hpeplugin_driver.delete_volume,
                 'params': {'volume': snapshot,
                            'is_snapshot': True},
                 'msg': 'Cleaning up backend snapshot: %s...'
                        % bkend_snap_name})
        except Exception as ex:
            msg = (_('create snapshot failed, error is: %s')
                   % six.text_type(ex))
            LOG.error(msg)
            return json.dumps({u"Err": six.text_type(ex)})

        # Add back reference to child snapshot in volume metadata

        db_snapshot = {'name': snapshot_name,
                       'id': snapshot_id,
                       'parent_name': src_vol_name,
                       'parent_id': vol['id'],
                       'fsMode': vol.get('fsMode'),
                       'fsOwner': vol.get('fsOwner'),
                       'expiration_hours': expiration_hrs,
                       'retention_hours': retention_hrs}
        if has_schedule:
            snap_schedule = {
                'schedule_name': schedName,
                'snap_name_prefix': snapPrefix,
                'sched_frequency': schedFrequency,
                'sched_snap_exp_hrs': exphrs,
                'sched_snap_ret_hrs': rethrs}
            db_snapshot['snap_schedule'] = snap_schedule

        vol['snapshots'].append(db_snapshot)
        snap_vol['snap_metadata'] = db_snapshot
        snap_vol['backend'] = current_backend
        snap_vol['3par_vol_name'] = bkend_snap_name

        try:
            self._create_snapshot_record(snap_vol,
                                         snapshot_name,
                                         undo_steps)

            # For now just track volume to uuid mapping internally
            # TODO: Save volume name and uuid mapping in etcd as well
            # This will make get_vol_byname more efficient
            self._etcd.save_vol(vol)
            LOG.debug('snapshot: %(name)s was successfully saved '
                      'to etcd', {'name': snapshot_name})
        except Exception as ex:
            msg = (_('save volume to etcd failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            self._rollback(undo_steps)
            response = json.dumps({u"Err": six.text_type(ex)})
        else:
            response = json.dumps({u"Err": ''})
        return response

    @synchronization.synchronized_volume('{volname}')
    def remove_volume(self, volname):
        # Only 1 node in a multinode cluster can try to remove the volume.
        # Grab lock for volume name. If lock is inuse, just return with no
        # error.
        # Expand lock code inline as function based lock causes
        # unexpected behavior
        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            # Just log an error, but don't fail the docker rm command
            msg = 'Volume name to remove not found: %s' % volname
            LOG.error(msg)
            return json.dumps({u"Err": msg})
        parent_name = None
        is_snap = False
        if 'is_snap' in vol and vol['is_snap']:
            is_snap = True
            parent_name = vol['snap_metadata']['parent_name']

        try:
            if 'snapshots' in vol and vol['snapshots']:
                msg = (_LE('Err: Volume %s has one or more child '
                           'snapshots - volume cannot be deleted!'
                           % volname))
                LOG.error(msg)
                response = json.dumps({u"Err": msg})
                return response
            else:
                if 'has_schedule' in vol and vol['has_schedule']:
                    schedule_info = vol['snap_metadata']['snap_schedule']
                    sched_name = schedule_info['schedule_name']
                    self._hpeplugin_driver.force_remove_3par_schedule(
                        sched_name)

                self._hpeplugin_driver.delete_volume(vol, is_snap)
                LOG.info(_LI('volume: %(name)s,' 'was successfully deleted'),
                         {'name': volname})
                if is_snap:
                    self.remove_snapshot(parent_name, volname)
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

    @synchronization.synchronized_volume('{volname}')
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

    @synchronization.synchronized_volume('{clone_name}')
    def _clone_volume(self, clone_name, src_vol, size, cpg,
                      snap_cpg, current_backend, clone_opts):

        # Create clone volume specification
        undo_steps = []
        clone_vol = volume.createvol(clone_name, size,
                                     src_vol['provisioning'],
                                     src_vol['flash_cache'],
                                     src_vol['compression'],
                                     src_vol['qos_name'],
                                     src_vol['mount_conflict_delay'],
                                     False, cpg, snap_cpg, False,
                                     current_backend)
        try:
            bkend_clone_name = self.__clone_volume__(src_vol,
                                                     clone_vol,
                                                     undo_steps)
            self._apply_volume_specs(clone_vol, undo_steps)
            # For now just track volume to uuid mapping internally
            # TODO: Save volume name and uuid mapping in etcd as well
            # This will make get_vol_byname more efficient
            clone_vol['fsOwner'] = src_vol.get('fsOwner')
            clone_vol['fsMode'] = src_vol.get('fsMode')
            clone_vol['3par_vol_name'] = bkend_clone_name
            if clone_opts is not None:
                clone_vol['Options'] = clone_opts

            self._etcd.save_vol(clone_vol)

        except Exception as ex:
            msg = (_('Clone volume failed, error is: %s'),
                   six.text_type(ex))
            LOG.error(msg)
            self._rollback(undo_steps)
            return json.dumps({u"Err": six.text_type(ex)})
        else:
            return json.dumps({u"Err": ''})

    # Commenting out unused function to increase coverage
    # @synchronization.synchronized_volume('{volumename}')
    # def revert_to_snapshot(self, volumename, snapname):
    #     volume = self._etcd.get_vol_byname(volumename)
    #     if volume is None:
    #         msg = (_LE('Volume: %s does not exist' % volumename))
    #         LOG.info(msg)
    #         response = json.dumps({u"Err": msg})
    #         return response
    #
    #     snapshots = volume['snapshots']
    #     LOG.info("Getting snapshot by name: %s" % snapname)
    #     snapshot, idx = self._get_snapshot_by_name(snapshots,
    #                                                snapname)
    #     if snapshot:
    #         try:
    #             LOG.info("Found snapshot by name %s" % snapname)
    #             self._hpeplugin_driver.revert_snap_to_vol(volume, snapshot)
    #             response = json.dumps({u"Err": ''})
    #             return response
    #         except Exception as ex:
    #             msg = (_('revert snapshot failed, error is: %s'),
    #                    six.text_type(ex))
    #             LOG.error(msg)
    #             return json.dumps({u"Err": six.text_type(ex)})
    #     else:
    #         msg = (_LE('snapshot: %s does not exist!' % snapname))
    #         LOG.info(msg)
    #         response = json.dumps({u"Err": msg})
    #         return response

    def _get_snapshot_response(self, snapinfo, snapname):
        err = ''
        mountdir = ''
        devicename = ''
        path_info = self._etcd.get_vol_path_info(snapname)
        LOG.debug('Value of path info in snapshot response is %s', path_info)
        if path_info is not None:
            mountdir = path_info['mount_dir']
            devicename = path_info['path']

        # use volinfo as volname could be partial match
        snapshot = {'Name': snapname,
                    'Mountpoint': mountdir,
                    'Devicename': devicename,
                    'Status': {}}
        metadata = snapinfo['snap_metadata']
        parent_name = metadata['parent_name']
        parent_id = metadata['parent_id']
        expiration_hours = metadata['expiration_hours']
        retention_hours = metadata['retention_hours']

        snap_detail = {}
        snap_detail['size'] = snapinfo.get('size')
        snap_detail['compression'] = snapinfo.get('compression')
        snap_detail['provisioning'] = snapinfo.get('provisioning')
        snap_detail['is_snap'] = snapinfo.get('is_snap')
        snap_detail['parent_volume'] = parent_name
        snap_detail['parent_id'] = parent_id
        snap_detail['fsOwner'] = snapinfo['snap_metadata'].get('fsOwner')
        snap_detail['fsMode'] = snapinfo['snap_metadata'].get('fsMode')
        snap_detail['expiration_hours'] = expiration_hours
        snap_detail['retention_hours'] = retention_hours
        snap_detail['mountConflictDelay'] = snapinfo.get(
            'mount_conflict_delay')
        snap_detail['snap_cpg'] = snapinfo.get('snap_cpg')
        snap_detail['backend'] = snapinfo.get('backend')

        if 'snap_schedule' in metadata:
            snap_detail['snap_schedule'] = metadata['snap_schedule']

        LOG.info('_get_snapshot_response: adding 3par vol info')

        if '3par_vol_name' in snapinfo:
            snap_detail['3par_vol_name'] = snapinfo.get('3par_vol_name')
        else:
            snap_detail['3par_vol_name'] = utils.get_3par_name(snapinfo['id'],
                                                               True)

        snapshot['Status'].update({'snap_detail': snap_detail})

        response = json.dumps({u"Err": err, u"Volume": snapshot})
        LOG.debug("Get volume/snapshot: \n%s" % str(response))
        return response

    def _get_snapshot_etcd_record(self, parent_volname, snapname):
        volumeinfo = self._etcd.get_vol_byname(parent_volname)
        snapshots = volumeinfo.get('snapshots', None)
        if 'snap_cpg' in volumeinfo:
            snapshot_cpg = volumeinfo.get('snap_cpg')
        else:
            snapshot_cpg = self._hpeplugin_driver.get_snapcpg(volumeinfo,
                                                              False)
        if snapshots:
            self._sync_snapshots_from_array(volumeinfo['id'],
                                            volumeinfo['snapshots'],
                                            snapshot_cpg)
            snapinfo = self._etcd.get_vol_byname(snapname)
            LOG.debug('value of snapinfo from etcd read is %s', snapinfo)
            if snapinfo is None:
                msg = (_LE('Snapshot_get: snapname not found after sync %s'),
                       snapname)
                LOG.debug(msg)
                response = json.dumps({u"Err": msg})
                return response
            snapinfo['snap_cpg'] = snapshot_cpg
            self._etcd.update_vol(snapinfo['id'], 'snap_cpg', snapshot_cpg)
            return self._get_snapshot_response(snapinfo, snapname)
        else:
            msg = (_LE('Snapshot_get: snapname not found after sync %s'),
                   snapname)
            LOG.debug(msg)
            response = json.dumps({u"Err": msg})
            return response

    def get_volume_snap_details(self, volname, snapname, qualified_name):

        volinfo = self._etcd.get_vol_byname(volname)
        LOG.info("Value of volinfo is: %s", volinfo)
        if volinfo is None:
            msg = (_LE('Volume Get: Volume name not found %s'), volname)
            LOG.warning(msg)
            response = json.dumps({u"Err": ""})
            return response
        if 'is_snap' in volinfo and volinfo['is_snap']:
            LOG.debug('type of is_snap is %s', type(volinfo['is_snap']))
            snap_metadata = volinfo['snap_metadata']
            parent_volname = snap_metadata['parent_name']
            snapname = snap_metadata['name']
            return self._get_snapshot_etcd_record(parent_volname, snapname)
        if 'snap_cpg' not in volinfo:
            snap_cpg = self._hpeplugin_driver.get_snapcpg(volinfo, False)
            if snap_cpg:
                volinfo['snap_cpg'] = snap_cpg
                self._etcd.update_vol(volinfo['id'], 'snap_cpg', snap_cpg)
        if 'cpg' not in volinfo:
            volinfo['cpg'] = self._hpeplugin_driver.get_cpg(volinfo, False,
                                                            allowSnap=False)
            self._etcd.update_vol(volinfo['id'], 'cpg', volinfo['cpg'])

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
        snapshot_cpg = volinfo.get('snap_cpg', volinfo.get('cpg'))
        if volinfo.get('snapshots') and volinfo.get('snapshots') != '':
            self._sync_snapshots_from_array(volinfo['id'],
                                            volinfo['snapshots'], snapshot_cpg)
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
                    # metadata = s['snap_metadata']
                    if 'snap_schedule' in s:
                        snapshot['snap_schedule'] = s['snap_schedule']
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
                    msg = "ERROR: Failed to retrieve QoS '%s' from 3PAR" \
                          % qos_name
                    volume['Status'].update({'qos_detail': msg})
                    msg += ' %s' % six.text_type(ex)
                    LOG.error(msg)

            vol_detail = {}
            vol_detail['size'] = volinfo.get('size')
            vol_detail['flash_cache'] = volinfo.get('flash_cache')
            vol_detail['compression'] = volinfo.get('compression')
            vol_detail['provisioning'] = volinfo.get('provisioning')
            vol_detail['fsOwner'] = volinfo.get('fsOwner')
            vol_detail['fsMode'] = volinfo.get('fsMode')
            vol_detail['mountConflictDelay'] = volinfo.get(
                'mount_conflict_delay')
            vol_detail['cpg'] = volinfo.get('cpg')
            vol_detail['snap_cpg'] = volinfo.get('snap_cpg')
            vol_detail['backend'] = volinfo.get('backend')
            vol_detail['domain'] = self._hpeplugin_driver.get_domain(
                vol_detail['cpg'])

            LOG.info(' get_volume_snap_details : adding 3par vol info')
            if '3par_vol_name' in volinfo:
                vol_detail['3par_vol_name'] = volinfo['3par_vol_name']
            else:
                vol_detail['3par_vol_name'] = \
                    utils.get_3par_name(volinfo['id'],
                                        False)

            if 'Options' in volinfo:
                vol_detail['Options'] = volinfo['Options']

            if volinfo.get('rcg_info'):
                vol_detail['secondary_cpg'] = \
                    self.tgt_bkend_config.hpe3par_cpg[0]
                vol_detail['secondary_snap_cpg'] = \
                    self.tgt_bkend_config.hpe3par_snapcpg[0]

                # fetch rcg details and display
                rcg_name = volinfo['rcg_info']['local_rcg_name']
                try:
                    rcg_detail = self._hpeplugin_driver.get_rcg(rcg_name)
                    rcg_filter = self._get_required_rcg_field(rcg_detail)
                    volume['Status'].update({'rcg_detail': rcg_filter})
                except Exception as ex:
                    msg = "ERROR: Failed to retrieve RCG '%s' from 3PAR" \
                          % rcg_name
                    volume['Status'].update({'rcg_detail': msg})
                    msg += ' %s' % six.text_type(ex)
                    LOG.error(msg)

            volume['Status'].update({'volume_detail': vol_detail})

        response = json.dumps({u"Err": err, u"Volume": volume})
        LOG.debug("Get volume/snapshot: \n%s" % str(response))
        return response

    def list_volumes(self):
        volumes = self._etcd.get_all_vols()

        if not volumes:
            response = json.dumps({u"Err": ''})
            return response

        volumelist = []
        for volinfo in volumes:
            path_info = self._etcd.get_path_info_from_vol(volinfo)
            if path_info is not None and 'mount_dir' in path_info:
                mountdir = path_info['mount_dir']
                devicename = path_info['path']
            else:
                mountdir = ''
                devicename = ''
            volume = {'Name': volinfo['display_name'],
                      'Devicename': devicename,
                      'size': volinfo['size'],
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
        node_mount_info = vol['node_mount_info']

        # Check if mount_id is unique
        if mount_id in node_mount_info[self._node_id]:
            LOG.info("Received duplicate mount-id: %s. Ignoring"
                     % mount_id)
            return

        LOG.info("Adding new mount-id %s to node_mount_info..."
                 % mount_id)
        node_mount_info[self._node_id].append(mount_id)
        LOG.info("Updating etcd with modified node_mount_info: %s..."
                 % node_mount_info)
        self._etcd.update_vol(vol['id'],
                              'node_mount_info',
                              node_mount_info)
        LOG.info("Updated etcd with modified node_mount_info: %s!"
                 % node_mount_info)

    def _get_success_response(self, vol):
        path_info = json.loads(vol['path_info'])
        path = FilePath(path_info['device_info']['path']).realpath()
        response = json.dumps({"Err": '', "Name": vol['display_name'],
                               "Mountpoint": path_info['mount_dir'],
                               "Devicename": path.path})
        return response

    def _wait_for_graceful_vol_unmount(self, vol):
        unmounted = False
        vol_id = vol['id']
        volname = vol['display_name']
        mount_conflict_delay = vol['mount_conflict_delay']
        for checks in range(0, mount_conflict_delay):
            time.sleep(1)
            LOG.info("Checking if volume %s got unmounted #%s..."
                     % (volname, checks))
            vol = self._etcd.get_vol_by_id(vol_id)

            # Check if unmount that was in progress has cleared the
            # node entry from ETCD database
            if 'node_mount_info' not in vol:
                LOG.info("Volume %s got unmounted after %s "
                         "checks!!!" % (volname, checks))
                unmounted = True
                break

            LOG.info("Volume %s still unmounting #%s..."
                     % (volname, checks))
        return unmounted

    def _force_remove_vlun(self, vol, is_snap):
        bkend_vol_name = utils.get_3par_name(vol['id'], is_snap)
        # Check if replication is configured and volume is
        # populated with the RCG
        if (self.tgt_bkend_config and 'rcg_info' in vol and
                vol['rcg_info'] is not None):
            if self.tgt_bkend_config.quorum_witness_ip:
                LOG.info("Peer Persistence setup: Removing VLUNs "
                         "forcefully from remote backend...")
                self._primary_driver.force_remove_volume_vlun(bkend_vol_name)
                self._remote_driver.force_remove_volume_vlun(bkend_vol_name)
                LOG.info("Peer Persistence setup: VLUNs forcefully "
                         "removed from remote backend!")
            else:
                LOG.info("Active/Passive setup: Getting active driver...")
                try:
                    driver = self._get_target_driver(vol['rcg_info'])
                    if driver:
                        LOG.info("Active/Passive setup: Got active driver!")
                        LOG.info("Active/Passive setup: Removing VLUNs "
                                 "forcefully from remote backend...")
                        driver.force_remove_volume_vlun(bkend_vol_name)
                        LOG.info("Active/Passive setup: VLUNs forcefully "
                                 "removed from remote backend!")
                    else:
                        msg = "Failed to force remove VLUN(s) " \
                              "Could not determine the target array based on" \
                              "state of RCG %s." % \
                              vol['rcg_info']['local_rcg_name']
                        LOG.error(msg)
                        raise exception.HPEDriverForceRemoveVLUNFailed(
                            reason=msg)
                except Exception as ex:
                    msg = "Failed to force remove VLUN(s). " \
                          "Exception: %s" % six.text_type(ex)
                    LOG.error(msg)
                    raise exception.HPEDriverForceRemoveVLUNFailed(
                        reason=six.text_type(ex))
        else:
            LOG.info("Removing VLUNs forcefully from remote backend...")
            self._primary_driver.force_remove_volume_vlun(bkend_vol_name)
            LOG.info("VLUNs forcefully removed from remote backend!")

    @synchronization.synchronized_volume('{volname}')
    def mount_volume(self, volname, vol_mount, mount_id):
        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            msg = (_LE('Volume mount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginMountException(reason=msg)

        undo_steps = []
        volid = vol['id']
        is_snap = False
        if 'is_snap' not in vol:
            vol['is_snap'] = volume.DEFAULT_TO_SNAP_TYPE
            self._etcd.update_vol(volid, 'is_snap', is_snap)
        elif vol['is_snap']:
            is_snap = vol['is_snap']
            vol['fsOwner'] = vol['snap_metadata'].get('fsOwner')
            vol['fsMode'] = vol['snap_metadata'].get('fsMode')

        if 'mount_conflict_delay' not in vol:
            m_conf_delay = volume.DEFAULT_MOUNT_CONFLICT_DELAY
            vol['mount_conflict_delay'] = m_conf_delay
            self._etcd.update_vol(volid, 'mount_conflict_delay',
                                  m_conf_delay)
        # Initialize node-mount-info if volume is being mounted
        # for the first time
        if self._is_vol_not_mounted(vol):
            LOG.info("Initializing node_mount_info... adding first "
                     "mount ID %s" % mount_id)
            node_mount_info = {self._node_id: [mount_id]}
            vol['node_mount_info'] = node_mount_info
        else:
            # Volume is in mounted state - Volume fencing logic begins here
            node_mount_info = vol['node_mount_info']

            # If mounted on this node itself then just append mount-id
            if self._is_vol_mounted_on_this_node(node_mount_info):
                self._update_mount_id_list(vol, mount_id)
                return self._get_success_response(vol)
            else:
                # Volume mounted on different node
                LOG.info("Volume mounted on a different node. Waiting for "
                         "other node to gracefully unmount the volume...")

                unmounted = self._wait_for_graceful_vol_unmount(vol)

                if not unmounted:
                    LOG.info("Volume not gracefully unmounted by other node")
                    LOG.info("%s" % vol)
                    self._force_remove_vlun(vol, is_snap)

                    # Since VLUNs exported to previous node were forcefully
                    # removed, cache the connection information so that it
                    # can be used later when user tries to un-mount volume
                    # from the previous node
                    if 'path_info' in vol:
                        path_info = vol['path_info']
                        old_node_id = list(node_mount_info.keys())[0]
                        old_path_info = vol.get('old_path_info', [])
                        old_path_info.append((old_node_id, path_info))
                        self._etcd.update_vol(volid, 'old_path_info',
                                              old_path_info)

                node_mount_info = {self._node_id: [mount_id]}
                LOG.info("New node_mount_info set: %s" % node_mount_info)

        root_helper = 'sudo'
        connector_info = connector.get_connector_properties(
            root_helper, self._my_ip, multipath=self._use_multipath,
            enforce_multipath=self._enforce_multipath)

        def _mount_volume(driver):
            LOG.info("Entered _mount_volume")
            try:
                # Call driver to initialize the connection
                driver.create_export(vol, connector_info, is_snap)
                connection_info = \
                    driver.initialize_connection(
                        vol, connector_info, is_snap)
                LOG.debug("Initialized Connection Successful!")
                LOG.debug('connection_info: %(connection_info)s, '
                          'was successfully retrieved',
                          {'connection_info': json.dumps(connection_info)})

                undo_steps.append(
                    {'undo_func': driver.terminate_connection,
                     'params': (vol, connector_info, is_snap),
                     'msg': 'Terminating connection to volume: %s...'
                            % volname})
            except Exception as ex:
                msg = (_('Initialize Connection Failed: '
                         'connection info retrieval failed, error is: '),
                       six.text_type(ex))
                LOG.error(msg)
                self._rollback(undo_steps)
                raise exception.HPEPluginMountException(reason=msg)

            # Call OS Brick to connect volume
            try:
                LOG.debug("OS Brick Connector Connecting Volume...")
                device_info = self._connector.connect_volume(
                    connection_info['data'])

                undo_steps.append(
                    {'undo_func': self._connector.disconnect_volume,
                     'params': (connection_info['data'], None),
                     'msg': 'Undoing connection to volume: %s...' % volname})
            except Exception as ex:
                msg = (_('OS Brick connect volume failed, error is: '),
                       six.text_type(ex))
                LOG.error(msg)
                self._rollback(undo_steps)
                raise exception.HPEPluginMountException(reason=msg)
            return device_info, connection_info

        pri_connection_info = None
        sec_connection_info = None
        # Check if replication is configured and volume is
        # populated with the RCG
        if (self.tgt_bkend_config and 'rcg_info' in vol and
                vol['rcg_info'] is not None):
            LOG.info("This is a replication setup")
            # Check if this is Active/Passive based replication
            if self.tgt_bkend_config.quorum_witness_ip:
                LOG.info("Peer Persistence has been configured")
                # This is Peer Persistence setup
                LOG.info("Mounting volume on primary array...")
                device_info, pri_connection_info = _mount_volume(
                    self._primary_driver)
                LOG.info("Volume successfully mounted on primary array!"
                         "pri_connection_info: %s" % pri_connection_info)
                LOG.info("Mounting volume on secondary array...")
                sec_device_info, sec_connection_info = _mount_volume(
                    self._remote_driver)
                LOG.info("Volume successfully mounted on secondary array!"
                         "sec_connection_info: %s" % sec_connection_info)
            else:
                # In case failover/failback has happened at the backend, while
                # mounting the volume, the plugin needs to figure out the
                # target array
                LOG.info("Active/Passive replication has been configured")
                driver = self._get_target_driver(vol['rcg_info'])
                device_info, pri_connection_info = _mount_volume(driver)
                LOG.info("Volume successfully mounted on active array!"
                         "active_connection_info: %s" % pri_connection_info)
        else:
            # hpeplugin_driver will always point to the currently active array
            # Post-failover, it will point to secondary_driver
            LOG.info("Single array setup has been configured")
            device_info, pri_connection_info = _mount_volume(
                self._hpeplugin_driver)
            LOG.info("Volume successfully mounted on the array!"
                     "pri_connection_info: %s" % pri_connection_info)

        # Make sure the path exists
        path = FilePath(device_info['path']).realpath()
        if path.exists is False:
            msg = (_('path: %s,  does not exist'), path)
            LOG.error(msg)
            self._rollback(undo_steps)
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
            if self._host_config.mount_prefix:
                mount_prefix = self._host_config.mount_prefix
            else:
                mount_prefix = None
            mount_dir = fileutil.mkdir_for_mounting(device_info['path'],
                                                    mount_prefix)
            LOG.debug('Directory: %(mount_dir)s, '
                      'successfully created to mount: '
                      '%(mount)s',
                      {'mount_dir': mount_dir, 'mount': device_info['path']})

            undo_steps.append(
                {'undo_func': fileutil.remove_dir,
                 'params': mount_dir,
                 'msg': 'Removing mount directory: %s...' % mount_dir})

            # mount the directory
            fileutil.mount_dir(path.path, mount_dir)
            LOG.debug('Device: %(path)s successfully mounted on %(mount)s',
                      {'path': path.path, 'mount': mount_dir})

            undo_steps.append(
                {'undo_func': fileutil.umount_dir,
                 'params': mount_dir,
                 'msg': 'Unmounting directory: %s...' % mount_dir})

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

        try:
            if 'fsOwner' in vol and vol['fsOwner']:
                fs_owner = vol['fsOwner'].split(":")
                uid = int(fs_owner[0])
                gid = int(fs_owner[1])
                os.chown(mount_dir, uid, gid)

            if 'fsMode' in vol and vol['fsMode']:
                mode = str(vol['fsMode'])
                chmod(mode, mount_dir)

            path_info = {}
            path_info['name'] = volname
            path_info['path'] = path.path
            path_info['device_info'] = device_info
            path_info['connection_info'] = pri_connection_info
            path_info['mount_dir'] = mount_dir
            if sec_connection_info:
                path_info['remote_connection_info'] = sec_connection_info

            LOG.info("Updating node_mount_info in etcd with mount_id %s..."
                     % mount_id)
            self._etcd.update_vol(volid,
                                  'node_mount_info',
                                  node_mount_info)
            LOG.info("node_mount_info updated successfully in etcd with "
                     "mount_id %s" % mount_id)
            self._etcd.update_vol(volid, 'path_info', json.dumps(path_info))

            response = json.dumps({u"Err": '', u"Name": volname,
                                   u"Mountpoint": mount_dir,
                                   u"Devicename": path.path})
        except Exception as ex:
            self._rollback(undo_steps)
            response = json.dumps({"Err": '%s' % six.text_type(ex)})

        return response

    def _get_target_driver(self, rcg_info):
        local_rcg = None
        rcg_name = rcg_info.get('local_rcg_name')
        try:
            LOG.info("Getting local RCG: %s" % rcg_name)
            local_rcg = self._primary_driver.get_rcg(rcg_name)
            local_role_reversed = local_rcg['targets'][0]['roleReversed']
        except Exception as ex:
            msg = "There was an error fetching the remote copy " \
                  "group %s from primary array: %s" % \
                  (rcg_name, six.text_type(ex))
            LOG.error(msg)

        remote_rcg = None
        remote_rcg_name = rcg_info.get('remote_rcg_name')
        try:
            LOG.info("Getting remote RCG: %s" % remote_rcg_name)
            remote_rcg = self._remote_driver.get_rcg(remote_rcg_name)
            remote_role_reversed = remote_rcg['targets'][0]['roleReversed']
        except Exception as ex:
            msg = "There was an error fetching the remote copy " \
                  "group %s from secondary array: %s" % \
                  (remote_rcg_name, six.text_type(ex))
            LOG.error(msg)

        # Both arrays are up - this could just be a group fail-over
        if local_rcg and remote_rcg:
            LOG.info("Got both local and remote RCGs! Checking roles...")
            # State before to fail-over
            if local_rcg['role'] == PRIMARY and not local_role_reversed and \
               remote_rcg['role'] == SECONDARY and not remote_role_reversed:
                LOG.info("Primary array is the active array")
                return self._primary_driver

            # Primary array is either down or RCG under maintenance
            # Allow remote target driver to take over
            if local_rcg['role'] == PRIMARY and not local_role_reversed and \
               remote_rcg['role'] == PRIMARY_REV and remote_role_reversed:
                msg = "Secondary array is the active array"
                LOG.info(msg)
                return self._remote_driver

            # State post recover
            if remote_rcg['role'] == PRIMARY and remote_role_reversed and \
               local_rcg['role'] == SECONDARY and local_role_reversed:
                LOG.info("Secondary array is the active array")
                return self._remote_driver

            msg = (_("Remote copy group %s is being failed over or failed "
                     "back. Unable to determine RCG location") % rcg_name)
            LOG.error(msg)
            raise exception.RcgStateInTransitionException(reason=msg)

        if local_rcg:
            if local_rcg['role'] == PRIMARY and not local_role_reversed:
                LOG.info("Primary array is the active array")
                return self._primary_driver

        if remote_rcg:
            if remote_rcg['role'] == PRIMARY and remote_role_reversed:
                LOG.info("Secondary array is the active array")
                return self._remote_driver

        msg = (_("Failed to get RCG %s. Unable to determine RCG location")
               % rcg_name)
        LOG.error(msg)
        raise exception.HPEDriverRemoteCopyGroupNotFound(name=rcg_name)

    @synchronization.synchronized_volume('{volname}')
    def unmount_volume(self, volname, vol_mount, mount_id):
        vol = self._etcd.get_vol_byname(volname)
        if vol is None:
            msg = (_LE('Volume unmount name not found %s'), volname)
            LOG.error(msg)
            raise exception.HPEPluginUMountException(reason=msg)

        volid = vol['id']
        is_snap = vol['is_snap']

        path_info = None
        node_owns_volume = True

        # Start of volume fencing
        LOG.info('Unmounting volume: %s' % vol)
        if 'node_mount_info' in vol:
            node_mount_info = vol['node_mount_info']

            # Check if this node still owns the volume. If not, then it is
            # not possible to proceed with cleanup as the volume meta-data
            # context was modified by other node and it's not relevant for
            # this node anymore.
            # TODO: To solve the above issue, when a volume is re-mounted
            # forcibly on other node, that other node should save the volume
            # meta-data in a different ETCD root for it to be accessible by
            # this node. Once this node discovers that the volume is owned
            # by some other node, it can go to that different ETCD root to
            # fetch the volume meta-data and do the cleanup.
            if self._node_id not in node_mount_info:
                if 'old_path_info' in vol:
                    LOG.info("Old path info present in volume: %s"
                             % path_info)
                    for pi in vol['old_path_info']:
                        node_id = pi[0]
                        if node_id == self._node_id:
                            LOG.info("Found matching old path info for old "
                                     "node ID: %s" % six.text_type(pi))
                            path_info = pi
                            node_owns_volume = False
                            break

                if path_info:
                    LOG.info("Removing old path info for node %s from ETCD "
                             "volume meta-data..." % self._node_id)
                    vol['old_path_info'].remove(path_info)
                    if len(vol['old_path_info']) == 0:
                        LOG.info("Last old_path_info found. "
                                 "Removing it too...")
                        vol.pop('old_path_info')
                    LOG.info("Updating volume meta-data: %s..." % vol)
                    self._etcd.save_vol(vol)
                    LOG.info("Volume meta-data updated: %s" % vol)

                    path_info = json.loads(path_info[1])
                    LOG.info("Cleaning up devices using old_path_info: %s"
                             % path_info)
                else:
                    LOG.info("Volume '%s' is mounted on another node. "
                             "No old_path_info is present on ETCD. Unable"
                             "to cleanup devices!" % volname)
                    return json.dumps({u"Err": ""})
            else:
                LOG.info("node_id '%s' is present in vol mount info"
                         % self._node_id)

                mount_id_list = node_mount_info[self._node_id]

                LOG.info("Current mount_id_list %s " % mount_id_list)

                try:
                    mount_id_list.remove(mount_id)
                except ValueError as ex:
                    LOG.exception('Ignoring exception: %s' % ex)
                    pass

                LOG.info("Updating node_mount_info '%s' in etcd..."
                         % node_mount_info)
                # Update the mount_id list in etcd
                self._etcd.update_vol(volid, 'node_mount_info',
                                      node_mount_info)

                LOG.info("Updated node_mount_info '%s' in etcd!"
                         % node_mount_info)

                if len(mount_id_list) > 0:
                    # Don't proceed with unmount
                    LOG.info("Volume still in use by %s containers... "
                             "no unmounting done!" % len(mount_id_list))
                    return json.dumps({u"Err": ''})
                else:
                    # delete the node_id key from node_mount_info
                    LOG.info("Removing node_mount_info %s",
                             node_mount_info)
                    vol.pop('node_mount_info')
                    LOG.info("Saving volume to etcd: %s..." % vol)
                    self._etcd.save_vol(vol)
                    LOG.info("Volume saved to etcd: %s!" % vol)

        # TODO: Requirement #5 will bring the flow here but the below flow
        # may result into exception. Need to ensure it doesn't happen
        if not path_info:
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

        remote_connection_info = path_info.get('remote_connection_info')

        # Issue#272 Fix: Don't allow disconnect_volume on secondary array
        # for ISCSI. OS-Brick cleans up all the devices in the above call
        # only for ISCSI. If we allow the below disconnect-volume to
        # execute, OS-Brick throws exception aborting the remaining steps
        # thereby leaving behind VLUN and ETCD entries
        if remote_connection_info and \
                remote_connection_info['driver_volume_type'] != 'iscsi':
            LOG.info('sync call os brick to disconnect remote volume')
            self._connector.disconnect_volume(
                remote_connection_info['data'], None)
            LOG.info('end of sync call to disconnect remote volume')

        def _unmount_volume(driver):
            try:
                # Call driver to terminate the connection
                driver.terminate_connection(vol, connector_info,
                                            is_snap)
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

        _unmount_volume(self._hpeplugin_driver)

        # In case of Peer Persistence, volume is mounted on the secondary
        # array as well. It should be unmounted too
        if self.tgt_bkend_config:
            _unmount_volume(self._remote_driver)

        # TODO: Create path_info list as we can mount the volume to multiple
        # hosts at the same time.
        # If this node owns the volume then update path_info
        if node_owns_volume:
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

        if vvs_name is not None:
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

    def _remove_snap_record(self, snap_name):
        snap_info = self._etcd.get_vol_byname(snap_name)
        self._etcd.delete_vol(snap_info)

    def _set_flash_cache_for_volume(self, vvs_name, flash_cache):
        self._hpeplugin_driver.set_flash_cache_policy_on_vvs(
            flash_cache,
            vvs_name)

    @staticmethod
    def _rollback(rollback_list):
        for undo_action in reversed(rollback_list):
            LOG.info(undo_action['msg'])
            try:
                params = undo_action['params']
                if type(params) is dict:
                    undo_action['undo_func'](**undo_action['params'])
                elif type(params) is tuple:
                    undo_action['undo_func'](*undo_action['params'])
                else:
                    undo_action['undo_func'](undo_action['params'])
            except Exception as ex:
                # TODO: Implement retry logic
                LOG.exception('Ignoring exception: %s' % ex)
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

    def _sync_snapshots_from_array(self, vol_id, db_snapshots, snap_cpg):
        bkend_snapshots = \
            self._hpeplugin_driver.get_snapshots_by_vol(vol_id, snap_cpg)
        ss_list_remove = self._get_snapshots_to_be_deleted(db_snapshots,
                                                           bkend_snapshots)
        if ss_list_remove:
            for ss in ss_list_remove:
                db_snapshots.remove(ss)
                self._remove_snap_record(ss['name'])
            self._etcd.update_vol(vol_id, 'snapshots',
                                  db_snapshots)

    @staticmethod
    def _get_required_rcg_field(rcg_detail):
        rcg_filter = {}

        msg = 'get_required_rcg_field: %s' % rcg_detail
        LOG.info(msg)
        rcg_filter['rcg_name'] = rcg_detail.get('name')
        # TODO(sonivi): handle in case of multiple target
        rcg_filter['policies'] = rcg_detail['targets'][0].get('policies')
        rcg_filter['role'] = volume.RCG_ROLE.get(rcg_detail.get('role'))

        return rcg_filter

    @staticmethod
    def _get_required_qos_field(qos_detail):
        qos_filter = {}

        msg = 'get_required_qos_field: %s' % qos_detail
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

    # TODO: Place holder for now
    def _get_3par_rcg_name(self, rcg_name):
        return rcg_name

    def _find_rcg(self, rcg_name):
        rcg = self._hpeplugin_driver.get_rcg(rcg_name)
        rcg_info = {'local_rcg_name': rcg_name,
                    'remote_rcg_name': rcg['remoteGroupName']}
        return rcg_info

    # TODO: Need RCG lock in different namespace. To be done later
    @synchronization.synchronized_rcg('{rcg_name}')
    def _create_rcg(self, rcg_name, undo_steps):
        rcg_info = self._hpeplugin_driver.create_rcg(
            rcg_name=rcg_name)

        undo_steps.append(
            {'undo_func': self._hpeplugin_driver.delete_rcg,
             'params': {'rcg_name': rcg_name},
             'msg': 'Undo create RCG: Deleting Remote Copy Group %s...'
                    % (rcg_name)})
        return rcg_info

    # TODO: Need RCG lock in different namespace. To be done later
    # @synchronization.synchronized_rcg('{rcg_name}')
    def _add_volume_to_rcg(self, vol, rcg_name, undo_steps):
        bkend_vol_name = utils.get_3par_vol_name(vol['id'])
        self._hpeplugin_driver.add_volume_to_rcg(
            bkend_vol_name=bkend_vol_name,
            rcg_name=rcg_name)
        undo_steps.append(
            {'undo_func': self._hpeplugin_driver.remove_volume_from_rcg,
             'params': {'vol_name': bkend_vol_name,
                        'rcg_name': rcg_name},
             'msg': 'Removing VV %s from Remote Copy Group %s...'
                    % (bkend_vol_name, rcg_name)})

    def _decrypt_password(self, src_bknd, trgt_bknd, backend_name):
        try:
            passphrase = self._etcd.get_backend_key(backend_name)
        except Exception as ex:
            LOG.info('Exception occurred %s ' % ex)
            LOG.info("Using PLAIN TEXT for backend '%s'" % backend_name)
        else:
            passphrase = self.key_check(passphrase)
            src_bknd.hpe3par_password = \
                self._decrypt(src_bknd.hpe3par_password, passphrase)
            src_bknd.san_password =  \
                self._decrypt(src_bknd.san_password, passphrase)
            if trgt_bknd:
                trgt_bknd.hpe3par_password = \
                    self._decrypt(trgt_bknd.hpe3par_password, passphrase)
                trgt_bknd.san_password = \
                    self._decrypt(trgt_bknd.san_password, passphrase)

    def key_check(self, key):
        KEY_LEN = len(key)
        padding_string = string.ascii_letters

        if KEY_LEN < 16:
            KEY = key + padding_string[:16 - KEY_LEN]

        elif KEY_LEN > 16 and KEY_LEN < 24:
            KEY = key + padding_string[:24 - KEY_LEN]

        elif KEY_LEN > 24 and KEY_LEN < 32:
            KEY = key + padding_string[:32 - KEY_LEN]

        elif KEY_LEN > 32:
            KEY = key[:32]

        else:
            KEY = key

        return KEY

    def _decrypt(self, encrypted, passphrase):
        aes = AES.new(passphrase, AES.MODE_CFB, '1234567812345678')
        decrypt_pass = aes.decrypt(base64.b64decode(encrypted))
        return decrypt_pass.decode('utf-8')
