# import mock
import fake_3par_data as data
import hpe_docker_unit_test as hpedockerunittest
from hpe3parclient import exceptions


class MountVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_mount'

    def get_request_params(self):
        return {"Name": "test-vol-001",
                "Opts": {'mount-volume': 'True'}}

    def setup_mock_objects(self):
        def _setup_mock_3parclient():
            # Allow child class to make changes
            self.setup_mock_3parclient()

        def _setup_mock_etcd():
            mock_etcd = self.mock_objects['mock_etcd']
            mock_etcd.get_vol_byname.return_value = data.volume
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
    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.fake_fc_host]
        mock_client.queryHost.return_value = data.fake_hosts
        # Existing VLUN not found hence create new one
        mock_client.getHostVLUNs.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.host_vluns1,
            data.host_vluns2]
        mock_client.createVLUN.return_value = data.location

    def check_response(self, resp):
        # resp -> {"Mountpoint": "/tmp", "Name": "test-vol-001",
        # "Err": "", "Devicename": "/tmp"}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], u'test-vol-001')
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
        mock_3parclient.getPorts.assert_called()
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


# Host not registered with supplied name
# Host exists for supplied WWN + VLUN exists
# For host creation, both getHost and queryHost should not return anything
class TestMountVolumeFCHostVLUNExists(MountVolumeUnitTest):
    def setup_mock_3parclient(self):
        mock_client = self.mock_objects['mock_3parclient']
        mock_client.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_client.getCPG.return_value = {}
        mock_client.getHost.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.fake_fc_host]
        mock_client.queryHost.return_value = data.fake_hosts
        # Use existing VLUN. No need to create new one
        mock_client.getHostVLUNs.side_effect = [
            data.host_vluns1,
            data.host_vluns2]
        mock_client.createVLUN.return_value = data.location

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], u'test-vol-001')
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
        mock_3parclient.getPorts.assert_called()
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
class TestMountVolumeFCNoHostNoVLUN(MountVolumeUnitTest):
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
        mock_client.getHostVLUNs.side_effect = [
            exceptions.HTTPNotFound('VLUNs not found for host'),
            data.host_vluns1,
            data.host_vluns2]
        mock_client.createVLUN.return_value = data.location

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], u'test-vol-001')
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
        mock_3parclient.getPorts.assert_called()
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
    def setup_mock_3parclient(self):
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getVolume.return_value = {'userCPG': data.HPE3PAR_CPG}
        mock_3parclient.getHostVLUNs.return_value = data.host_vluns

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
        self._test_case.assertEqual(resp['Name'], u'test-vol-001')
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
        mock_3parclient.getPorts.assert_called()
        mock_3parclient.getHostVLUNs.assert_called()


# Host exists with different name
# VLUN doesn't exist
class TestMountVolumeISCSIHostNoVLUN(MountVolumeUnitTest):
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
        mock_client.getHostVLUNs.side_effect = [
            exceptions.HTTPNotFound('fake'),
            data.iscsi_host_vluns1]
        mock_client.createVLUN.return_value = data.location
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], u'test-vol-001')
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
        mock_3parclient.getPorts.assert_called()
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
        mock_client.getHostVLUNs.side_effect = [
            data.iscsi_host_vluns1,
            data.iscsi_host_vluns2]
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], u'test-vol-001')
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
        mock_3parclient.getPorts.assert_called()
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
        mock_client.getHostVLUNs.side_effect = [
            data.iscsi_host_vluns1,
            data.iscsi_host_vluns1]
        mock_client.getVolumeMetaData.return_value = data.volume_metadata
        mock_client.getiSCSIPorts.return_value = [data.FAKE_ISCSI_PORT]

    def setup_mock_osbrick_connector(self):
        mock_connector = self.mock_objects['mock_osbricks_connector']
        # Same connector has info for both FC and ISCSI
        mock_connector.get_connector_properties.return_value = \
            data.connector

    def override_configuration(self, config):
        config.hpe3par_iscsi_chap_enabled = True
        config.use_multipath = False

    def check_response(self, resp):
        # resp -> {u'Mountpoint': u'/tmp', u'Name': u'test-vol-001',
        #          u'Err': u'', u'Devicename': u'/tmp'}
        expected_keys = ["Mountpoint", "Name", "Err", "Devicename"]
        for key in expected_keys:
            self._test_case.assertIn(key, resp)

        self._test_case.assertEqual(resp['Mountpoint'], u'/tmp')
        self._test_case.assertEqual(resp['Name'], u'test-vol-001')
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
        mock_3parclient.getPorts.assert_called()
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
