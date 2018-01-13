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

    def check_response(self, resp):
        expected = {u'Volume':
                    {u'Size': 2, u'Devicename': u'', u'Status':
                        {u'Settings': {u'expirationHours': u'10',
                                       u'retentionHours': u'10'}},
                     u'Name': u'volume-d03338a9-9115-48a3-8dfc-'
                              u'35cdfcdc15a7/snapshot-1',
                     u'Mountpoint': u''}, u'Err': u''}

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getVolumeSnapshots.assert_called()
