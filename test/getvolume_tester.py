import copy

from hpe3parclient import exceptions

import test.fake_3par_data as data
import test.hpe_docker_unit_test as hpedockerunittest
from oslo_config import cfg
CONF = cfg.CONF


class GetVolumeUnitTest(hpedockerunittest.HpeDockerUnitTestExecutor):
    def _get_plugin_api(self):
        return 'volumedriver_get'

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_with_snapshots

    def override_configuration(self, all_configs):
        pass


class TestGetVolumeWithQos(GetVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {"provisioning": "thin",
                         "qos-name": "vvk_vvset",
                         "size": "2",
                         "backend": "DEFAULT"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_qos
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryQoSRule.return_value = data.qos_from_3par_wsapi

    def check_response(self, resp):
        expected = {
            u'Volume': {
                u'Devicename': u'',
                u'Status': {
                    u'qos_detail': {
                        u'Latency': u'10 sec',
                        u'enabled': None,
                        u'maxBWS': u'40.0 MB/sec',
                        u'maxIOPS': u'2000000 IOs/sec',
                        u'minBWS': u'30.0 MB/sec',
                        u'minIOPS': u'10000 IOs/sec',
                        u'priority': u'Normal',
                        u'vvset_name': u'vvk_vvset'
                    },
                    u'volume_detail': {
                        u'3par_vol_name': data.VOLUME_3PAR_NAME,
                        u'backend': 'DEFAULT',
                        u'compression': None,
                        u'flash_cache': None,
                        u'fsMode': None,
                        u'fsOwner': None,
                        u'provisioning': u'thin',
                        u'size': 2,
                        u'mountConflictDelay': data.MOUNT_CONFLICT_DELAY,
                        u'cpg': data.HPE3PAR_CPG,
                        u'snap_cpg': data.HPE3PAR_CPG2,
                        u'domain': None
                    }
                },
                u'Name': u'volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7',
                u'Mountpoint': u''
            },
            u'Err': u''
        }

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryQoSRule.assert_called()


class TestGetVolumeWithGetQoSFails(GetVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {"provisioning": "thin",
                         "qos-name": "vvk_vvset",
                         "size": "2",
                         "backend": "DEFAULT"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_qos
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.queryQoSRule.side_effect = [
            exceptions.HTTPNotFound("QoS vvk_vvset not found")
        ]

    def check_response(self, resp):
        expected = {
            u'Volume': {
                u'Devicename': u'',
                u'Status': {
                    u'qos_detail': "ERROR: Failed to retrieve QoS "
                                   "'vvk_vvset' from 3PAR",
                    u'volume_detail': {
                        u'3par_vol_name': data.VOLUME_3PAR_NAME,
                        u'backend': 'DEFAULT',
                        u'compression': None,
                        u'flash_cache': None,
                        u'fsMode': None,
                        u'fsOwner': None,
                        u'provisioning': u'thin',
                        u'size': 2,
                        u'mountConflictDelay': data.MOUNT_CONFLICT_DELAY,
                        u'cpg': data.HPE3PAR_CPG,
                        u'snap_cpg': data.HPE3PAR_CPG2,
                        u'domain': None
                    }
                },
                u'Name': u'volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7',
                u'Mountpoint': u''
            },
            u'Err': u''
        }

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.queryQoSRule.assert_called()


class TestGetRcgVolume(GetVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {"provisioning": "thin",
                         "replicationGroup": data.RCG_NAME,
                         "size": "2",
                         "backend": "3par_pp_rep"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        self.rep_vol = copy.deepcopy(data.replicated_volume)
        self.rep_vol['backend'] = '3par_pp_rep'
        mock_etcd.get_vol_byname.return_value = self.rep_vol
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getRemoteCopyGroup.return_value = \
            data.normal_rcg['primary_3par_rcg']

    def check_response(self, resp):
        expected = {
            u'Volume': {
                u'Devicename': u'',
                u'Status': {
                    u'rcg_detail': {'rcg_name': data.RCG_NAME,
                                    'policies': data.pp_rcg_policies,
                                    'role': 'Primary'},
                    u'volume_detail': {
                        u'3par_vol_name': data.VOLUME_3PAR_NAME,
                        u'backend': '3par_pp_rep',
                        u'compression': None,
                        u'flash_cache': None,
                        u'fsMode': None,
                        u'fsOwner': None,
                        u'provisioning': u'thin',
                        u'size': 2,
                        u'mountConflictDelay': data.MOUNT_CONFLICT_DELAY,
                        u'cpg': data.HPE3PAR_CPG,
                        u'snap_cpg': data.HPE3PAR_CPG2,
                        u'secondary_cpg': 'FC_r1',
                        u'secondary_snap_cpg': 'FC_r5',
                        u'domain': None
                    }
                },
                u'Name': u'volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7',
                u'Mountpoint': u''
            },
            u'Err': u''
        }

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getRemoteCopyGroup.assert_called()


class TestGetRcgVolumeFails(GetVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {"provisioning": "thin",
                         "replicationGroup": data.RCG_NAME,
                         "size": "2",
                         "backend": "3par_pp_rep"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        self.rep_vol = copy.deepcopy(data.replicated_volume)
        self.rep_vol['backend'] = '3par_pp_rep'
        mock_etcd.get_vol_byname.return_value = self.rep_vol
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getRemoteCopyGroup.side_effect = [
            exceptions.HTTPNotFound("RCG %s not found" % data.RCG_NAME)
        ]

    def check_response(self, resp):
        expected = {
            u'Volume': {
                u'Devicename': u'',
                u'Status': {
                    u'rcg_detail': "ERROR: Failed to retrieve RCG '%s' "
                                   "from 3PAR" % data.RCG_NAME,
                    u'volume_detail': {
                        u'3par_vol_name': data.VOLUME_3PAR_NAME,
                        u'backend': '3par_pp_rep',
                        u'compression': None,
                        u'flash_cache': None,
                        u'fsMode': None,
                        u'fsOwner': None,
                        u'provisioning': u'thin',
                        u'size': 2,
                        u'mountConflictDelay': data.MOUNT_CONFLICT_DELAY,
                        u'cpg': data.HPE3PAR_CPG,
                        u'snap_cpg': data.HPE3PAR_CPG2,
                        u'secondary_cpg': 'FC_r1',
                        u'secondary_snap_cpg': 'FC_r5',
                        u'domain': None
                    }
                },
                u'Name': u'volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7',
                u'Mountpoint': u''
            },
            u'Err': u''
        }

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getRemoteCopyGroup.assert_called()


class TestCloneVolume(GetVolumeUnitTest):
    def get_request_params(self):
        return {"Name": data.VOLUME_NAME,
                "Opts": {"provisioning": "dedup",
                         "cloneOf": data.VOLUME_NAME,
                         "size": "2"}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.return_value = data.volume_dedup
        mock_etcd.get_vol_path_info.return_value = None

    def check_response(self, resp):
        expected = {
            u'Volume': {
                u'Devicename': u'',
                u'Status': {
                    u'volume_detail': {
                        u'3par_vol_name': data.VOLUME_3PAR_NAME,
                        u'backend': 'DEFAULT',
                        u'compression': None,
                        u'flash_cache': None,
                        u'provisioning': u'dedup',
                        u'size': 2,
                        u'fsMode': None,
                        u'fsOwner': None,
                        u'mountConflictDelay': data.MOUNT_CONFLICT_DELAY,
                        u'cpg': data.HPE3PAR_CPG,
                        u'snap_cpg': data.HPE3PAR_CPG,
                        u'domain': None
                    }
                },
                u'Name': u'volume-d03338a9-9115-48a3-8dfc-35cdfcdc15a7',
                u'Mountpoint': u''
            },
            u'Err': u''
        }

        self._test_case.assertEqual(resp, expected)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()


class GetSnapshotUnitTest(GetVolumeUnitTest):
    pass


class TestSyncSnapshots(GetSnapshotUnitTest):
    def __init__(self, **kwargs):
        super(type(self), self).__init__(**kwargs)
        self._snap1 = copy.deepcopy(data.snap1)
        self._snap2 = copy.deepcopy(data.snap2)
        self._vol_with_snaps = copy.deepcopy(data.volume_with_snapshots)

    def get_request_params(self):
        return {"Name": data.SNAPSHOT_NAME1,
                "Opts": {}}

    def setup_mock_objects(self):
        mock_etcd = self.mock_objects['mock_etcd']
        mock_etcd.get_vol_byname.side_effect = [
            None,
            self._snap1,
            self._vol_with_snaps,
            self._snap2,
            self._snap1,
        ]
        mock_etcd.get_vol_path_info.return_value = None

        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getSnapshotsOfVolume.return_value = \
            data.bkend_snapshots

    def check_response(self, resp):
        snap_detail = {
            u'3par_vol_name': data.SNAPSHOT_3PAR_NAME,
            u'backend': 'DEFAULT',
            u'compression': None,
            u'is_snap': True,
            u'parent_id': data.VOLUME_ID,
            u'parent_volume': data.VOLUME_NAME,
            u'provisioning': None,
            u'size': 2,
            u'fsOwner': None,
            u'fsMode': None,
            u'expiration_hours': '10',
            u'retention_hours': '10',
            u'snap_cpg': None,
            u'mountConflictDelay': data.MOUNT_CONFLICT_DELAY
        }

        expected = {
            u'Err': u'',
            u'Volume': {
                u'Devicename': u'',
                u'Mountpoint': u'',
                u'Name': u'snapshot-1',
                u'Status': {
                    u'snap_detail': snap_detail
                }
            }
        }

        self._test_case.assertEqual(expected, resp)

        # Check if these functions were actually invoked
        # in the flow or not
        mock_3parclient = self.mock_objects['mock_3parclient']
        mock_3parclient.getWsApiVersion.assert_called()
        mock_3parclient.getSnapshotsOfVolume.assert_called()
