import copy

import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest
from hpe3parclient import exceptions


class MountVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def __init__(self, is_snap=False, vol_params=None):
        self._backend_name = None
        self._vol_type = None
        self._rep_type = None
        self._is_snap = is_snap
        self._rcg_state = None
        if not is_snap:
            if vol_params:
                self._rcg_state = vol_params.get('rcg_state')
                self._vol_type = vol_params['vol_type']
                if self._vol_type == 'replicated':
                    self._rep_type = vol_params['rep_type']
                    if self._rep_type == 'active-passive':
                        self._backend_name = '3par_ap_sync_rep'
                        self._vol = copy.deepcopy(data.replicated_volume)
                        self._vol['backend'] = self._backend_name
            else:
                self._vol = copy.deepcopy(data.volume)
        else:
            self._vol = copy.deepcopy(data.snap1)

    def _get_plugin_api(self):
        return 'volumedriver_mount'

    def get_request_params(self):
        opts = {'mount-volume': 'True'}
        if self._backend_name:
            opts['backend'] = self._backend_name
        return {"Name": self._vol['display_name'],
                "ID": "Fake-Mount-ID",
                "Opts": opts}

    def setup_mock_objects(self):
        def _setup_mock_3parclient():
            # Allow child class to make changes
            if self._rep_type == 'active-passive':
                mock_3parclient = self.mock_objects['mock_3parclient']
                if self._rcg_state == 'normal':
                    mock_3parclient.getRemoteCopyGroup.side_effect = [
                        data.normal_rcg['primary_3par_rcg'],
                        data.normal_rcg['secondary_3par_rcg']
                    ]
                elif self._rcg_state == 'failover':
                    mock_3parclient.getRemoteCopyGroup.side_effect = [
                        data.failover_rcg['primary_3par_rcg'],
                        data.failover_rcg['secondary_3par_rcg']
                    ]
                elif self._rcg_state == 'recover':
                    mock_3parclient.getRemoteCopyGroup.side_effect = [
                        data.recover_rcg['primary_3par_rcg'],
                        data.recover_rcg['secondary_3par_rcg']
                    ]
                elif self._rcg_state == 'rcgs_not_gettable':
                    mock_3parclient.getRemoteCopyGroup.side_effect = [
                        exceptions.HTTPNotFound("Primary RCG not found"),
                        exceptions.HTTPNotFound("Secondary RCG not found"),
                    ]
                elif self._rcg_state == 'only_primary_rcg_gettable':
                    mock_3parclient.getRemoteCopyGroup.side_effect = [
                        data.normal_rcg['primary_3par_rcg'],
                        exceptions.HTTPNotFound("Secondary RCG not found"),
                    ]
                elif self._rcg_state == 'only_secondary_rcg_gettable':
                    mock_3parclient.getRemoteCopyGroup.side_effect = [
                        exceptions.HTTPNotFound("Primary RCG not found"),
                        data.failover_rcg['secondary_3par_rcg'],
                    ]
                else:
                    raise Exception("Invalid rcg_state specified")

            self.setup_mock_3parclient()

        def _setup_mock_etcd():
            mock_etcd = self.mock_objects['mock_etcd']
            mock_etcd.get_vol_byname.return_value = self._vol
            # Allow child class to make changes
            self.setup_mock_etcd()

        def _setup_mock_fileutil():
            mock_fileutil = self.mock_objects['mock_fileutil']
            mock_fileutil.mkdir_for_mounting.return_value = '/tmp'
            # Let the flow create filesystem
            mock_fileutil.has_filesystem.return_value = False
            # Allow child class to make changes
            self.setup_mock_fileutil()

        def _setup_mock_osbrick_connector():
            mock_connector = self.mock_objects['mock_osbricks_connector']
            # Same connector has info for both FC and ISCSI
            mock_connector.get_connector_properties.return_value = \
                data.connector_multipath_enabled
            # Allow child class to make changes
            self.setup_mock_osbrick_connector()

        def _setup_mock_protocol_connector():
            mock_protocol_connector = \
                self.mock_objects['mock_protocol_connector']
            # MUST provide an existing path on FS for FilePath to work
            mock_protocol_connector.connect_volume.return_value = \
                {'path': '/tmp'}

            # Allow child class to make changes
            self.setup_mock_protocol_connector()

        _setup_mock_3parclient()
        _setup_mock_etcd()
        _setup_mock_fileutil()
        _setup_mock_protocol_connector()
        _setup_mock_osbrick_connector()

    def setup_mock_3parclient(self):
        pass

    def setup_mock_etcd(self):
        pass

    def setup_mock_fileutil(self):
        pass

    def setup_mock_protocol_connector(self):
        pass

    def setup_mock_osbrick_connector(self):
        pass


# Done
class TestMountVolumeFCHost(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.fake_fc_host]
        mock_client.queryHost.return_value = data.fake_hosts

        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('fake'),
                data.host_vluns1,
                data.host_vluns2]
        else:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('fake'),
                data.snap_host_vluns1,
                data.snap_host_vluns2]

        # Existing VLUN not found hence create new one
        mock_client.createVLUN.return_value = data.location

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        # In case of 'rcgs_not_gettable', 'Err' is returned
        if self._rcg_state == 'rcgs_not_gettable':
            expected = {'Err': "Remote copy group 'TEST-RCG' not found"}
            self._test_case.assertEqual(resp, expected)
        else:
            expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
            for key in expected_keys:
                self._test_case.assertIn(key, resp)

            # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
            #          u'Err': u'', u'Devicename': u'/tmp'}
            self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
            self._test_case.assertEqual(resp['Name'],
                                        self._vol['display_name'])
            self._test_case.assertEqual(resp['Err'], u'')
            self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_etcd = self.mock_objects['mock_etcd']
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        if self._rcg_state != 'rcgs_not_gettable':
            mock_3parclient.getVolume.assert_called()
            mock_3parclient.getCPG.assert_called()
            mock_3parclient.getHost.assert_called()
            mock_3parclient.queryHost.assert_called()
            # mock_3parclient.getPorts.assert_called()
            mock_3parclient.getHostVLUNs.assert_called()
            mock_3parclient.createVLUN.assert_called()

            mock_fileutil = self.mock_objects['mock_fileutil']
            mock_fileutil.has_filesystem.assert_called()
            mock_fileutil.create_filesystem.assert_called()
            mock_fileutil.mkdir_for_mounting.assert_called()
            mock_fileutil.mount_dir.assert_called()
            # lost+found directory removed or not
            mock_fileutil.remove_dir.assert_called()

            mock_etcd.update_vol.assert_called()

            mock_protocol_connector = \
                self.mock_objects['mock_protocol_connector']
            mock_protocol_connector.connect_volume.assert_called()

        mock_etcd.get_vol_byname.assert_called()


# Host not registered with supplied name
# Host exists for supplied WWN + VLUN exists
# For host creation, both getHost and queryHost should not return anything
class TestMountVolumeFCHostVLUNExists(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.fake_fc_host]
        mock_client.queryHost.return_value = data.fake_hosts
        # Use existing VLUN. No need to create new one
        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                data.host_vluns1,
                data.host_vluns2]
        else:
            mock_client.getHostVLUNs.side_effect = [
                data.snap_host_vluns1,
                data.snap_host_vluns2]

        mock_client.createVLUN.return_value = data.location

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        mock_3parclient.queryHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        # mock_3parclient.createVLUN.assert_called()

        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.has_filesystem.assert_called()
        mock_fileutil.create_filesystem.assert_called()
        mock_fileutil.mkdir_for_mounting.assert_called()
        mock_fileutil.mount_dir.assert_called()
        # lost+found directory removed or not
        mock_fileutil.remove_dir.assert_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.assert_called()
        mock_etcd.update_vol.assert_called()

        mock_protocol_connector = self.mock_objects['mock_protocol_connector']
        mock_protocol_connector.connect_volume.assert_called()


# Host + VLUN doesn't exist
class TestMountVolumeNoFCHostNoVLUN(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.fake_fc_host]
        # This will make the flow create a new host on 3PAR
        mock_client.queryHost.return_value = None
        # Create new VLUN
        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('VLUNs not found for host'),
                data.host_vluns1,
                data.host_vluns2]
        else:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('VLUNs not found for host'),
                data.snap_host_vluns1,
                data.snap_host_vluns2]

        mock_client.createVLUN.return_value = data.location

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        mock_3parclient.queryHost.assert_called()
        # Important check for this TC
        mock_3parclient.createHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        # Important check for this TC
        mock_3parclient.createVLUN.assert_called()

        # TODO: This is common check across all TCs and can
        # be moved to base class
        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.has_filesystem.assert_called()
        mock_fileutil.create_filesystem.assert_called()
        mock_fileutil.mkdir_for_mounting.assert_called()
        mock_fileutil.mount_dir.assert_called()
        # lost+found directory removed or not
        mock_fileutil.remove_dir.assert_called()

        # TODO: This is common check across all TCs and can
        # be moved to base class
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.assert_called()
        mock_etcd.update_vol.assert_called()

        # TODO: This is common check across all TCs and can
        # be moved to base class
        mock_protocol_connector = self.mock_objects['mock_protocol_connector']
        mock_protocol_connector.connect_volume.assert_called()


# Host + VLUN exists
# New WWN added to existing host
class TestMountVolumeModifyHostVLUNExists(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        if not self._is_snap:
            mock_3parclient.getHostVLUNs.return_value = data.host_vluns
        else:
            mock_3parclient.getHostVLUNs.return_value = data.snap_host_vluns

        mock_3parclient.getHost.return_value = data.fake_fc_host
        mock_3parclient.queryHost.return_value = None
        # mock_3parclient.getVolumeMetaData.return_value = data.volume_metadata
        mock_3parclient.getCPG.return_value = {}

    def setup_mock_fileutil(self):
        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.mkdir_for_mounting.return_value = '/tmp'

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        mock_3parclient.queryHost.assert_called()
        # Important check for this TC
        mock_3parclient.modifyHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()


# Host exists with different name
# VLUN doesn't exist
class TestMountVolumeISCSIHostNoVLUN(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            {'name': data.FAKE_HOST}]
        mock_client.queryHost.return_value = {
            'members': [{
                'name': data.FAKE_HOST
            }]}
        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('fake'),
                data.iscsi_host_vluns1]
        else:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('fake'),
                data.snap_iscsi_host_vluns1]

        mock_client.createVLUN.return_value = data.location
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        mock_3parclient.queryHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        mock_3parclient.createVLUN.assert_called()

        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.has_filesystem.assert_called()
        mock_fileutil.create_filesystem.assert_called()
        mock_fileutil.mkdir_for_mounting.assert_called()
        mock_fileutil.mount_dir.assert_called()
        # lost+found directory removed or not
        mock_fileutil.remove_dir.assert_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.assert_called()
        mock_etcd.update_vol.assert_called()

        mock_protocol_connector = self.mock_objects['mock_protocol_connector']
        mock_protocol_connector.connect_volume.assert_called()


# Host exists with different name
# VLUN also exists
class TestMountVolumeISCSIHostVLUNExist(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            {'name': data.FAKE_HOST}]
        mock_client.queryHost.return_value = {
            'members': [{
                'name': data.FAKE_HOST
            }]}
        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                data.iscsi_host_vluns1,
                data.iscsi_host_vluns2]
        else:
            mock_client.getHostVLUNs.side_effect = [
                data.snap_iscsi_host_vluns1,
                data.snap_iscsi_host_vluns2]

        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        mock_3parclient.queryHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()

        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.has_filesystem.assert_called()
        mock_fileutil.create_filesystem.assert_called()
        mock_fileutil.mkdir_for_mounting.assert_called()
        mock_fileutil.mount_dir.assert_called()
        # lost+found directory removed or not
        mock_fileutil.remove_dir.assert_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.assert_called()
        mock_etcd.update_vol.assert_called()

        mock_protocol_connector = self.mock_objects['mock_protocol_connector']
        mock_protocol_connector.connect_volume.assert_called()


# Host exists with different name
# VLUN also exists
class TestMountVolumeISCSIHostChapOn(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            {'name': data.FAKE_HOST},
            data.fake_host]
        mock_client.queryHost.return_value = None
        mock_client.getVLUN.return_value = {'lun': data.TARGET_LUN}
        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                data.iscsi_host_vluns1,
                data.iscsi_host_vluns1,
                data.iscsi_host_vluns2]
        else:
            mock_client.getHostVLUNs.side_effect = [
                data.snap_iscsi_host_vluns1,
                data.snap_iscsi_host_vluns1,
                data.snap_iscsi_host_vluns2]

        mock_client.getVolumeMetaData.return_value = data.volume_metadata
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def setup_mock_osbrick_connector(self):
        mock_connector = self.mock_objects['mock_osbricks_connector']
        # Same connector has info for both FC and ISCSI
        mock_connector.get_connector_properties.return_value = \
            data.connector

    def override_configuration(self, all_configs):
        all_configs['DEFAULT'].hpe3par_iscsi_chap_enabled = True
        all_configs['DEFAULT'].use_multipath = False

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        mock_3parclient.modifyHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        mock_3parclient.getVolumeMetaData.assert_called()
        mock_3parclient.setVolumeMetaData.assert_called()

        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.has_filesystem.assert_called()
        mock_fileutil.create_filesystem.assert_called()
        mock_fileutil.mkdir_for_mounting.assert_called()
        mock_fileutil.mount_dir.assert_called()
        # lost+found directory removed or not
        mock_fileutil.remove_dir.assert_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.assert_called()
        mock_etcd.update_vol.assert_called()

        mock_protocol_connector = self.mock_objects['mock_protocol_connector']
        mock_protocol_connector.connect_volume.assert_called()


# TODO: Ununsed - to be removed
# Host + VLUN exists
# New IQN added to existing host
class TestMountVolumeModifyISCSIHostVLUNExists_Old(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getHostVLUNs.return_value = data.host_vluns

        # mock_client.getHost.return_value = data.fake_fc_host
        mock_client.getHost.side_effect = [
            {'name': data.FAKE_HOST, 'FCPaths': []},
            {'name': data.FAKE_HOST,
             'FCPaths': [{'wwn': '123456789012345'},
                         {'wwn': '123456789054321'}]}]
        mock_client.queryHost.return_value = None
        # mock_client.getVolumeMetaData.return_value = data.volume_metadata
        mock_client.getCPG.return_value = {}

    def setup_mock_fileutil(self):
        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.mkdir_for_mounting.return_value = '/tmp'

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getWsApiVersion.assert_called()
        mock_client.getVolume.assert_called()
        mock_client.getCPG.assert_called()
        mock_client.getHost.assert_called()
        # mock_client.queryHost.assert_called()
        # Important check for this TC
        mock_client.modifyHost.assert_called()
        # mock_client.getPorts.assert_called()
        mock_client.getHostVLUNs.assert_called()


# Single path
# Host + VLUN doesn't exist
class TestMountVolumeNoISCSIHostNoVLUN(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.fake_host]
        # This will make the flow create a new host on 3PAR
        mock_client.queryHost.return_value = None
        # Create new VLUN
        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('VLUNs not found for host'),
                data.iscsi_host_vluns1,
                data.iscsi_host_vluns2]
        else:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('VLUNs not found for host'),
                data.snap_iscsi_host_vluns1,
                data.snap_iscsi_host_vluns2]

        mock_client.createVLUN.return_value = data.location

    def override_configuration(self, all_configs):
        # config.hpe3par_iscsi_chap_enabled = True
        all_configs['DEFAULT'].use_multipath = False

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getWsApiVersion.assert_called()
        mock_client.getVolume.assert_called()
        mock_client.getCPG.assert_called()
        mock_client.getHost.assert_called()
        mock_client.queryHost.assert_called()
        # Important check for this TC
        mock_client.createHost.assert_called()
        # mock_client.getPorts.assert_called()
        mock_client.getHostVLUNs.assert_called()
        # Important check for this TC
        # mock_client.createVLUN.assert_called()

        # TODO: This is common check across all TCs and can
        # be moved to base class
        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.has_filesystem.assert_called()
        mock_fileutil.create_filesystem.assert_called()
        mock_fileutil.mkdir_for_mounting.assert_called()
        mock_fileutil.mount_dir.assert_called()
        # lost+found directory removed or not
        mock_fileutil.remove_dir.assert_called()

        # TODO: This is common check across all TCs and can
        # be moved to base class
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.assert_called()
        mock_etcd.update_vol.assert_called()

        # TODO: This is common check across all TCs and can
        # be moved to base class
        mock_protocol_connector = self.mock_objects['mock_protocol_connector']
        mock_protocol_connector.connect_volume.assert_called()


# Host + VLUN exists
# New WWN added to existing host
# Incomplete TC
class TestMountVolumeModifyISCSIHostVLUNExists(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        if not self._is_snap:
            mock_client.getHostVLUNs.return_value = data.iscsi_host_vluns
        else:
            mock_client.getHostVLUNs.return_value = data.snap_iscsi_host_vluns

        mock_client.getHost.return_value = data.fake_host
        mock_client.queryHost.return_value = None
        # mock_client.getVolumeMetaData.return_value = data.volume_metadata
        mock_client.getCPG.return_value = {}
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def setup_mock_fileutil(self):
        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.mkdir_for_mounting.return_value = '/tmp'

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        # mock_3parclient.queryHost.assert_called()
        # Important check for this TC
        # mock_3parclient.modifyHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()


# Volume mounted on this node
# Another mount request comes in to mount on this node only
class TestVolFencingMountTwiceSameNode(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)

    def setup_mock_etcd(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = copy.deepcopy(
            data.vol_mounted_on_this_node)
        mock_etcd.get_vol_path_info.return_value = copy.deepcopy(
            data.path_info)
        # Allow child class to make changes

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'],
                                    data.path_info['mount_dir'])
        self._test_case.assertEqual(resp['Name'],
                                    data.path_info['name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'],
                                    data.path_info['device_info']['path'])

        # Check that there are zero calls to 3PAR Client
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getCPG.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getVolume.assert_not_called()
        mock_3parclient.getHost.assert_not_called()
        mock_3parclient.queryHost.assert_not_called()
        mock_3parclient.modifyHost.assert_not_called()
        mock_3parclient.getHostVLUNs.assert_not_called()


# Volume mounted on different node
# This node waits for un-mounting of volume from other node
# Other node un-mounts before mount-conflict-delay period ends
class TestVolFencingGracefulUnmount(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._vol_mounted_on_other_node = copy.deepcopy(
            data.vol_mounted_on_other_node)
        self._unmounted_vol = copy.deepcopy(data.volume)

        # Change appropriate fields from vol so that it represents a snapshot
        if self._is_snap:
            self._vol_mounted_on_other_node['is_snap'] = True
            self._vol_mounted_on_other_node['display_name'] = \
                data.SNAPSHOT_NAME1
            self._vol_mounted_on_other_node['snap_metadata'] = \
                data.snap1_metadata
            self._vol_mounted_on_other_node['id'] = data.SNAPSHOT_ID1
            self._unmounted_vol['is_snap'] = True
            self._unmounted_vol['display_name'] = data.SNAPSHOT_NAME1
            self._unmounted_vol['id'] = data.SNAPSHOT_ID1

    def setup_mock_etcd(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            self._vol_mounted_on_other_node,
            self._vol_mounted_on_other_node,
            self._unmounted_vol
        ]
        mock_etcd.get_vol_path_info.return_value = copy.deepcopy(
            data.path_info)

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        if not self._is_snap:
            mock_client.getHostVLUNs.return_value = data.iscsi_host_vluns
        else:
            mock_client.getHostVLUNs.return_value = data.snap_iscsi_host_vluns

        mock_client.getHost.return_value = data.fake_host
        mock_client.queryHost.return_value = None
        # mock_client.getVolumeMetaData.return_value = data.volume_metadata
        mock_client.getCPG.return_value = {}
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def setup_mock_fileutil(self):
        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.mkdir_for_mounting.return_value = '/tmp'

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        # mock_3parclient.queryHost.assert_called()
        # Important check for this TC
        # mock_3parclient.modifyHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()


# Volume Fencing
# Add the new mount ID to the mount-id-list and return
# connection-info
class TestVolFencingForcedUnmount(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._vol_mounted_on_other_node = copy.deepcopy(
            data.vol_mounted_on_other_node)
        if self._is_snap:
            self._vol_mounted_on_other_node['is_snap'] = True
            self._vol_mounted_on_other_node['display_name'] = \
                data.SNAPSHOT_NAME1
            self._vol_mounted_on_other_node['id'] = data.SNAPSHOT_ID1
            self._vol_mounted_on_other_node['snap_metadata'] = \
                data.snap1_metadata

    def setup_mock_etcd(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = \
            self._vol_mounted_on_other_node
        mock_etcd.get_vol_by_id.return_value = \
            self._vol_mounted_on_other_node
        mock_etcd.get_vol_path_info.return_value = copy.deepcopy(
            data.path_info)
        # Allow child class to make changes

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        if not self._is_snap:
            mock_client.getHostVLUNs.return_value = data.iscsi_host_vluns
        else:
            mock_client.getHostVLUNs.return_value = data.snap_iscsi_host_vluns

        mock_client.getHost.return_value = data.fake_host
        mock_client.queryHost.return_value = None
        # mock_client.getVolumeMetaData.return_value = data.volume_metadata
        mock_client.getCPG.return_value = {}
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]
        mock_client.getVLUN.return_value = {'hostname': 'FakeHostName'}
        mock_client.getiSCSIPorts.return_value = data.FAKE_ISCSI_PORTS

    def setup_mock_fileutil(self):
        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.mkdir_for_mounting.return_value = '/tmp'

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.update_vol.assert_called()

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        # mock_3parclient.queryHost.assert_called()
        # Important check for this TC
        # mock_3parclient.modifyHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()


# # Volume Fencing
# # Add the new mount ID to the mount-id-list and return
# # connection-info
# class TestVolFencingForcedUnmountDelVHost(MountVolumeUnitTest):
#     def __init__(self, **kwargs):
#         super(type(self), self).__init__(**kwargs)
#         self._vol_mounted_on_other_node = copy.deepcopy(
#             data.vol_mounted_on_other_node)
#         if self._is_snap:
#             self._vol_mounted_on_other_node['is_snap'] = True
#             self._vol_mounted_on_other_node['display_name'] = \
#                 data.SNAPSHOT_NAME1
#             self._vol_mounted_on_other_node['id'] = data.SNAPSHOT_ID1
#
#     def setup_mock_etcd(self):
#         mock_etcd = self.mock_objects['mock_etcd']
#         mock_etcd.get_vol_byname.return_value = \
#             self._vol_mounted_on_other_node
#         mock_etcd.get_vol_by_id.return_value = \
#             self._vol_mounted_on_other_node
#         mock_etcd.get_vol_path_info.return_value = copy.deepcopy(
#             data.path_info)
#         # Allow child class to make changes
#
#     def setup_mock_3parclient(self):
#         mock_client = self.mock_objects['mock_3parclient']
#         mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
#         if not self._is_snap:
#             mock_client.getHostVLUNs.side_effect = [
#                 data.iscsi_host_vluns,
#                 exceptions.HTTPNotFound('NoVLunForThisHost'),
#                 data.iscsi_host_vluns,
#             ]
#         else:
#             mock_client.getHostVLUNs.side_effect = [
#                 data.snap_iscsi_host_vluns,
#                 exceptions.HTTPNotFound('NoVLunForThisHost')
#                 data.snap_iscsi_host_vluns,
#             ]
#
#         mock_client.getHost.return_value = data.fake_host
#         mock_client.queryHost.return_value = None
#         mock_client.getVolumeMetaData.return_value = data.volume_metadata
#         mock_client.getCPG.return_value = {}
#         mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]
#         mock_client.getVLUN.side_effect = [
#             {'hostname': 'FakeHostName'},
#             exceptions.HTTPNotFound('NoVLunFound'),
#             exceptions.HTTPNotFound('NoVLunFound'),
#             {'hostname': 'FakeHostName'},
#             {'hostname': 'FakeHostName'},
#         ]
#         mock_client.getiSCSIPorts.return_value = data.FAKE_ISCSI_PORTS
#
#     def setup_mock_fileutil(self):
#         mock_fileutil = self.mock_objects['mock_fileutil']
#         mock_fileutil.mkdir_for_mounting.return_value = '/tmp'
#
#     def check_response(self, resp):
#         # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
#         # "Err": "", "Devicename": "/tmp"}
#         expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
#         for key in expected_keys:
#             self._test_case.assertIn(key, resp)
#
#         self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
#         self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
#         self._test_case.assertEqual(resp['Err'], u'')
#         self._test_case.assertEqual(resp['Devicename'], u'/tmp')
#
#         # Check if these functions were actually invoked
#         # in the flow or not
#         mock_3parclient = self.mock_objects['mock_3parclient']
#         mock_3parclient.getWsApiVersion.assert_called()
#         mock_3parclient.getVolume.assert_called()
#         mock_3parclient.getCPG.assert_called()
#         mock_3parclient.getHost.assert_called()
#         # mock_3parclient.queryHost.assert_called()
#         # Important check for this TC
#         # mock_3parclient.modifyHost.assert_called()
#         mock_3parclient.getPorts.assert_called()
#         mock_3parclient.getHostVLUNs.assert_called()
#
#         # Since last VLUN is removed for the host, driver
#         # deletes the host entry from 3PAR using deleteHost
#         # call. Ensure that it got called
#         mock_3parclient.deleteHost.assert_called()


class TestMountPreviousVersionVolumeFCHost(MountVolumeUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        # We need here old type of volume which won't have
        # mount_conflict_delay. After the execution of this TC,
        # mount_conflict_delay should get added to volume again
        self._vol.pop('mount_conflict_delay')

    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.fake_fc_host]
        mock_client.queryHost.return_value = data.fake_hosts

        if not self._is_snap:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('fake'),
                data.host_vluns1,
                data.host_vluns2]
        else:
            mock_client.getHostVLUNs.side_effect = [
                exceptions.HTTPNotFound('fake'),
                data.snap_host_vluns1,
                data.snap_host_vluns2]

        # Existing VLUN not found hence create new one
        mock_client.createVLUN.return_value = data.location

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertIn('mount_conflict_delay', self._vol)

        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], self._vol['display_name'])
        self._test_case.assertEqual(resp['Err'], u'')
        self._test_case.assertEqual(resp['Devicename'], u'/tmp')

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
        mock_3parclient.getCPG.assert_called()
        mock_3parclient.getHost.assert_called()
        mock_3parclient.queryHost.assert_called()
        # mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()
        mock_3parclient.createVLUN.assert_called()

        mock_fileutil = self.mock_objects['mock_fileutil']
        mock_fileutil.has_filesystem.assert_called()
        mock_fileutil.create_filesystem.assert_called()
        mock_fileutil.mkdir_for_mounting.assert_called()
        mock_fileutil.mount_dir.assert_called()
        # lost+found directory removed or not
        mock_fileutil.remove_dir.assert_called()

        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.assert_called()
        mock_etcd.update_vol.assert_called()

        mock_protocol_connector = self.mock_objects['mock_protocol_connector']
        mock_protocol_connector.connect_volume.assert_called()

# class TestMountVolumeWithChap(MountVolumeUnitTest):
#     def setup_mock_objects(self):
#         mock_etcd = self.mock_objects['mock_etcd']
#         mock_etcd.get_vol_byname.return_value = data.volume
#
#         mock_osbrick_connector = self.mock_objects['mock_osbrick_connector']
#
#         # Same connector has info for both FC and ISCSI
#         mock_osbrick_connector.get_connector_properties.return_value = \
#             data.connector_multipath_enabled
#
#     def check_response(self, resp):
#         self._test_case.assertEqual(resp, {u"Err": ''})
#
#         # Check if these functions were actually invoked
#         # in the flow or not
#         mock_3parclient = self.mock_objects['mock_3parclient']
#         mock_3parclient.getWsApiVersion.assert_called()
#         mock_3parclient.createVolume.assert_called()
