import copy

import fake_3par_data as data
import hpe_docker_unit_test as hpedockerunittest
from oslo_config import cfg
CONF = cfg.CONF


class GetVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_get'

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots

    def override_configuration(self, config):
        pass


class GetSnapshotUnitTest(GetVolumeUnitTest):
    pass


class TestSyncSnapshots(GetSnapshotUnitTest):
    def get_request_params(self):
        snap_path = '/'.join([data.VOLUME_NAME,
                              data.SNAPSHOT_NAME1])
        return {"Name": snap_path,
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = \
            copy.deepcopy(data.volume_with_snapshots)
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getVolumeSnapshots.return_value = data.bkend_snapshots
        mock_3parclient.getVolume.return_value = data.volume_from_3par_wsapi

    def check_response(self, resp):
        expected = {u'Volume':
                    {u'Size': 2, u'Devicename': u'', u'Status':
                        {u'Settings': {u'expirationHours': u'10',
                                       u'retentionHours': u'10'},
                         u'volume_detail': {u'provisioning': u'thin',
                                            u'size': u'102400 MiB'}},
                     u'Name': u'volume-d03338a9-9115-48a3-8dfc-'
                              u'35cdfcdc15a7/snapshot-1',
                     u'Mountpoint': u''}, u'Err': u''}

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolumeSnapshots.assert_called()


class TestQosVolume(GetVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {"provisioning": "thin",
                         "qos-name": "vvk_vvset",
                         "size": "2"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_qos
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryQoSRule.return_value = data.qos_from_3par_wsapi
        mock_3parclient.getVolume.return_value = data.volume_from_3par_wsapi

    def check_response(self, resp):
        expected = {u'Volume':
                    {u'Size': 2, u'Devicename': u'', u'Status':
                     {u'qos_detail': {u'Latency': u'10sec',
                                      u'enabled': None,
                                      u'maxBWS': u'40 MB/sec',
                                      u'maxIOPS': u'2000000 IOs/sec',
                                      u'minBWS': u'30 MB/sec',
                                      u'minIOPS': u'10000 IOs/sec',
                                      u'priority': u'Normal'},
                      u'volume_detail': {u'provisioning': u'thin',
                                         u'size': u'102400 MiB'}},
                     u'Name': u'volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7',
                     u'Mountpoint': u''}, u'Err': u''}

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryQoSRule.assert_called()
        mock_3parclient.getVolume.assert_called()


class TestCloneVolume(GetVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {"provisioning": "thin",
                         "cloneOf": data.VOLUME_NAME,
                         "size": "2"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_clone
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getVolume.return_value = data.volume_from_3par_wsapi

    def check_response(self, resp):
        expected = {u'Volume':
                    {u'Size': 2, u'Devicename': u'', u'Status':
                     {u'volume_detail': {u'provisioning': u'thin',
                                         u'compressionState': u'NO',
                                         u'copyType': u'Physical Copy',
                                         u'deduplicationState': u'NO',
                                         u'provisioning': u'thin',
                                         u'size': u'102400 MiB'}},
                     u'Name': u'volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7',
                     u'Mountpoint': u''}, u'Err': u''}

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolume.assert_called()
