import json
import mock

THIS_NODE_ID = "This-Node-Id"
OTHER_NODE_ID = "Other-Node-Id"
KNOWN_HOSTS_FILE = 'dummy'
HPE3PAR_CPG = 'DockerCPG'
HPE3PAR_CPG2 = 'fakepool'
HPE3PAR_CPG_SNAP = 'DockerCPGSnap'
HPE3PAR_USER_NAME = 'testUser'
HPE3PAR_USER_PASS = 'testPassword'
HPE3PAR_SAN_IP = '2.2.2.2'
HPE3PAR_SAN_SSH_PORT = 999
HPE3PAR_SAN_SSH_CON_TIMEOUT = 44
HPE3PAR_SAN_SSH_PRIVATE = 'foobar'

CHAP_USER_KEY = "HPQ-docker-CHAP-name"
CHAP_PASS_KEY = "HPQ-docker-CHAP-secret"

FLASH_CACHE_ENABLED = 1
FLASH_CACHE_DISABLED = 2

# EXISTENT_PATH error code returned from hpe3parclient
EXISTENT_PATH = 73

VOLUME_ID = 'd03338a9-9115-48a3-8dfc-35cdfcdc15a7'
CLONE_ID = 'd03338a9-9115-48a3-8dfc-000000000000'
VOLUME_TYPE_ID_DEDUP = 'd03338a9-9115-48a3-8dfc-11111111111'
VOL_TYPE_ID_DEDUP_COMPRESS = 'd03338a9-9115-48a3-8dfc-33333333333'
VOLUME_TYPE_ID_FLASH_CACHE = 'd03338a9-9115-48a3-8dfc-22222222222'
VOLUME_NAME = 'volume-' + VOLUME_ID
DOCKER_VOL_NAME = 'test-vol-001'
VOL_DISP_NAME = 'test-vol-001'
SNAPSHOT_ID1 = '2f823bdc-e36e-4dc8-bd15-de1c7a28ff31'
SNAP1_3PAR_NAME = 'dcs-L4I73ONuTci9Fd4ceij-MQ'
SNAPSHOT_NAME1 = 'snapshot-1'
SNAPSHOT_ID2 = '8da7488a-7920-451a-ad18-0e41eca15d25'
SNAPSHOT_NAME2 = 'snapshot-2'
SNAPSHOT_ID3 = 'f5d9e226-2995-4d66-a5bd-3e373f4ff772'
SNAPSHOT_NAME3 = 'snapshot-3'
SNAPSHOT_ID4 = 'f5d9e226-2995-4d66-a5bd-3e373f4ff774'
SNAPSHOT_NAME4 = 'snapshot-4'
VOLUME_3PAR_NAME = 'dcv-0DM4qZEVSKON-DXN-NwVpw'
SNAPSHOT_3PAR_NAME1 = 'dcs-0DM4qZEVSKON-DXN-NwVpw'
SNAPSHOT_3PAR_NAME = 'dcs-L4I73ONuTci9Fd4ceij-MQ'
TARGET_IQN = 'iqn.2000-05.com.3pardata:21810002ac00383d'
TARGET_LUN = 90
MOUNT_CONFLICT_DELAY = 3
# fake host on the 3par
FAKE_HOST = 'fakehost'
FAKE_DOCKER_HOST = 'fakehost@foo#' + HPE3PAR_CPG
VOLUME_ID_SNAP = '761fc5e5-5191-4ec7-aeba-33e36de44156'

RCG_NAME = "TEST-RCG"
REMOTE_RCG_NAME = "TEST-RCG.r123456"
RCG_STARTED = 3
RCG_STOPPED = 5
ROLE_PRIMARY = 1
ROLE_PRIMARY_REV = 1
ROLE_SECONDARY = 2

FAKE_DESC = 'test description name'
FAKE_FC_PORTS = [{'portPos': {'node': 7, 'slot': 1, 'cardPort': 1},
                  'type': 1,
                  'portWWN': '0987654321234',
                  'protocol': 1,
                  'mode': 2,
                  'linkState': 4},
                 {'portPos': {'node': 6, 'slot': 1, 'cardPort': 1},
                  'type': 1,
                  'portWWN': '123456789000987',
                  'protocol': 1,
                  'mode': 2,
                  'linkState': 4}]

VVS_NAME = "myvvs"

# Provisioning
THIN = 'thin'
FULL = 'full'
DEDUP = 'dedup'

FAKE_ISCSI_PORT = {'portPos': {'node': 8, 'slot': 1, 'cardPort': 1},
                   'protocol': 2,
                   'mode': 2,
                   'IPAddr': '10.50.3.59',
                   'iSCSIName': TARGET_IQN,
                   'linkState': 4}

FAKE_ISCSI_PORTS = [{
    'IPAddr': '1.1.1.2',
    'iSCSIName': TARGET_IQN,
}]

volume = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'qos_name': None,
    'compression': None,
    'fsMode': None,
    'fsOwner': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'cpg': HPE3PAR_CPG,
    'snap_cpg': HPE3PAR_CPG2,
    'backend': 'DEFAULT'
}

replicated_volume = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'qos_name': None,
    'compression': None,
    'fsMode': None,
    'fsOwner': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'cpg': HPE3PAR_CPG,
    'snap_cpg': HPE3PAR_CPG2,
    'backend': 'DEFAULT',
    'rcg_info': {'local_rcg_name': RCG_NAME,
                 'remote_rcg_name': REMOTE_RCG_NAME}
}

pp_rcg_policies = {'autoRecover': False,
                   'overPeriodAlert': False,
                   'autoFailover': False,
                   'pathManagement': False}
normal_rcg = {
    'primary_3par_rcg': {
        'name': RCG_NAME,
        'role': ROLE_PRIMARY,
        'targets': [{'roleReversed': False,
                     'policies': pp_rcg_policies
                     }],
    },
    'secondary_3par_rcg': {
        'role': ROLE_SECONDARY,
        'targets': [{'roleReversed': False}]
    }
}

failover_rcg = {
    'primary_3par_rcg': {
        'role': ROLE_PRIMARY,
        'targets': [{'roleReversed': False}]
    },
    'secondary_3par_rcg': {
        'role': ROLE_PRIMARY_REV,
        'targets': [{'roleReversed': True}]
    }
}

recover_rcg = {
    'primary_3par_rcg': {
        'role': ROLE_SECONDARY,
        'targets': [{'roleReversed': True}]
    },
    'secondary_3par_rcg': {
        'role': ROLE_PRIMARY,
        'targets': [{'roleReversed': True}]
    }
}


json_path_info = \
    '{"connection_info": {"driver_volume_type": "iscsi", ' \
    '"data": {"target_luns": [3, 3], "target_iqns": ' \
    '["iqn.2000-05.com.3pardata:22210002ac019d52", ' \
    '"iqn.2000-05.com.3pardata:23210002ac019d52"], ' \
    '"target_discovered": true, "encrypted": false, ' \
    '"target_portals": ["10.50.3.59:3260", "10.50.3.60:3260"], ' \
    '"auth_password": "aTYvRmaEihE4eK2X", "auth_username": ' \
    '"csimbe06-b01", "auth_method": "CHAP"}}, "path": "/dev/dm-2", ' \
    '"device_info": {"path": "/dev/disk/by-id/dm-uuid-mpath-360002a' \
    'c00000000001008f9900019d52", "scsi_wwn": "360002ac000000000010' \
    '08f9900019d52", "type": "block", "multipath_id": "360002ac0000' \
    '0000001008f9900019d52"}, "name": "test-vol-001", "mount_dir": "/opt' \
    '/hpe/data/hpedocker-dm-uuid-mpath-360002ac00000000001008f99000' \
    '19d52"}'

# Volumes list for list-volumes operation
vols_list = [
    {
        'display_name': 'test-vol-001',
        'size': 310,
        'path_info': json_path_info
    },
    {
        'display_name': 'test-vol-002',
        'size': 555,
        'path_info': json_path_info
    }
]


path_info = json.loads(json_path_info)

vol_mounted_on_this_node = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'qos_name': None,
    'compression': None,
    'fsOwner': None,
    'fsMode': None,
    'snapshots': [],
    'node_mount_info': {THIS_NODE_ID: ['Fake-Mount-ID']},
    'path_info': json_path_info,
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'backend': 'DEFAULT'
}

vol_mounted_on_other_node = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'qos_name': None,
    'compression': None,
    'fsOwner': None,
    'fsMode': None,
    'snapshots': [],
    'node_mount_info': {OTHER_NODE_ID: ['Fake-Mount-ID']},
    'path_info': path_info,
    'old_path_info': [(THIS_NODE_ID, json_path_info)],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'backend': 'DEFAULT'
}


volume_mounted_twice_on_this_node = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'qos_name': None,
    'compression': None,
    'fsOwner': None,
    'fsMode': None,
    'snapshots': [],
    'node_mount_info': {THIS_NODE_ID: ['Fake-Mount-ID', 'Fake-Mount-ID']},
    'path_info': path_info,
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'backend': 'DEFAULT'
}

snap1_metadata = {
    'name': SNAPSHOT_NAME1,
    'id': SNAPSHOT_ID1,
    'parent_name': VOLUME_NAME,
    'parent_id': VOLUME_ID,
    'expiration_hours': '10',
    'retention_hours': '10',
    'fsOwner': None,
    'fsMode': None
}

snap1 = {
    'name': SNAPSHOT_NAME1,
    'id': SNAPSHOT_ID1,
    'display_name': SNAPSHOT_NAME1,
    'parent_id': VOLUME_ID,
    'ParentName': VOLUME_NAME,
    'is_snap': True,
    'has_schedule': False,
    'size': 2,
    'snap_metadata': snap1_metadata,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'backend': 'DEFAULT'
}

snap2_metadata = {
    'name': SNAPSHOT_NAME2,
    'id': SNAPSHOT_ID2,
    'parent_name': VOLUME_NAME,
    'parent_id': VOLUME_ID,
    'expiration_hours': '10',
    'retention_hours': '10',
    'fsOwner': None,
    'fsMode': None
}

snap2 = {
    'name': SNAPSHOT_NAME2,
    'id': SNAPSHOT_ID2,
    'display_name': SNAPSHOT_NAME2,
    'parent_id': VOLUME_ID,
    'ParentName': VOLUME_NAME,
    'is_snap': True,
    'has_schedule': False,
    'size': 2,
    'snap_metadata': snap2_metadata,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
}

snap3_metadata = {
    'name': SNAPSHOT_NAME2,
    'id': SNAPSHOT_ID2,
    'parent_name': SNAPSHOT_NAME1,
    'parent_id': SNAPSHOT_ID1,
    'expiration_hours': '10',
    'retention_hours': '10',
    'fsOwner': None,
    'fsMode': None
}
snap3 = {
    'name': SNAPSHOT_NAME3,
    'id': SNAPSHOT_ID3,
    'display_name': SNAPSHOT_NAME3,
    # This is a child of ref_to_snap1
    'parent_id': SNAPSHOT_ID1,
    'ParentName': SNAPSHOT_NAME1,
    'is_snap': True,
    'size': 2,
    'snap_metadata': snap3_metadata,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
}

snap4_schedule = {
    'schedule_name': "3parsched1",
    'snap_name_prefix': "pqrst",
    'sched_frequency': "10 * * * *",
    'sched_snap_exp_hrs': 4,
    'sched_snap_ret_hrs': 2
}
snap4_metadata = {
    'name': SNAPSHOT_NAME4,
    'id': SNAPSHOT_ID4,
    'parent_name': SNAPSHOT_NAME1,
    'parent_id': SNAPSHOT_ID1,
    'expiration_hours': None,
    'retention_hours': None,
    'fsOwner': None,
    'fsMode': None,
    'snap_schedule': snap4_schedule,
}
snap4 = {
    'name': SNAPSHOT_NAME4,
    'id': SNAPSHOT_ID4,
    'display_name': SNAPSHOT_NAME4,
    # This is a child of ref_to_snap1
    'parent_id': VOLUME_ID,
    'ParentName': VOLUME_NAME,
    'is_snap': True,
    'has_schedule': True,
    'size': 2,
    'snap_metadata': snap4_metadata,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'backend': 'DEFAULT'
}

ref_to_snap1 = {
    'name': SNAPSHOT_NAME1,
    'id': SNAPSHOT_ID1,
    'parent_id': VOLUME_ID,
    'ParentName': VOLUME_NAME,
}

ref_to_snap2 = {
    'name': SNAPSHOT_NAME2,
    'id': SNAPSHOT_ID2,
    'parent_id': VOLUME_ID,
    'ParentName': VOLUME_NAME
}

ref_to_snap3 = {
    'name': SNAPSHOT_NAME3,
    'id': SNAPSHOT_ID3,
    # This is a child of ref_to_snap1
    'parent_id': SNAPSHOT_ID1,
    'ParentName': VOLUME_NAME
}

ref_to_snap4 = {
    'name': SNAPSHOT_NAME4,
    'id': SNAPSHOT_ID4,
    'parent_id': VOLUME_ID,
    'ParentName': VOLUME_NAME,
    'snap_schedule': snap4_schedule
}

bkend_snapshots = [SNAPSHOT_3PAR_NAME]

# this is the qos we get from wsapi
qos_from_3par_wsapi = {
    'bwMaxLimitKB': 40960,
    'bwMinGoalKB': 30720,
    'ioMaxLimit': 2000000,
    'ioMinGoal': 10000,
    'latencyGoal': 10,
    'priority': 2,
    'name': 'vvk_vvset'
}

volume_with_snapshots = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'compression': None,
    'snapshots': [ref_to_snap1, ref_to_snap2],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'has_schedule': False,
    'backend': 'DEFAULT'
}

volume_with_snap_schedule = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'compression': None,
    'snapshots': [ref_to_snap4],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'has_schedule': False,
    'backend': 'DEFAULT'
}

volume_with_multilevel_snapshot = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'compression': None,
    'snapshots': [ref_to_snap1, ref_to_snap2, ref_to_snap3],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'backend': 'DEFAULT'
}

volume_encrypted = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'encryption_key_id': 'fake_key',
    'provisioning': THIN,
    'flash_cache': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'backend': 'DEFAULT'
}

volume_dedup_compression = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 16,
    'host': FAKE_DOCKER_HOST,
    'compression': None,
    'flash_cache': None,
    'provisioning': DEDUP,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'backend': 'DEFAULT'
}

volume_compression = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 16,
    'host': FAKE_DOCKER_HOST,
    'compression': 'true',
    'provisioning': THIN,
    'flash_cache': None,
    'qos_name': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'cpg': None,
    'snap_cpg': None,
    'backend': 'DEFAULT'
}

volume_dedup = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': DEDUP,
    'flash_cache': None,
    'qos_name': None,
    'compression': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'cpg': HPE3PAR_CPG,
    'snap_cpg': HPE3PAR_CPG,
    'backend': 'DEFAULT'
}

volume_qos = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'qos_name': "vvk_vvset",
    'compression': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'cpg': HPE3PAR_CPG,
    'snap_cpg': HPE3PAR_CPG2,
    'backend': 'DEFAULT'
}

volume_flash_cache = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': 'true',
    'qos_name': None,
    'compression': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'cpg': None,
    'snap_cpg': None,
    'backend': 'DEFAULT'

}

volume_flash_cache_and_qos = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': VOL_DISP_NAME,
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': 'true',
    'qos_name': 'vvk_vvset',
    'compression': None,
    'snapshots': [],
    'mount_conflict_delay': MOUNT_CONFLICT_DELAY,
    'is_snap': False,
    'cpg': None,
    'snap_cpg': None,
    'backend': 'DEFAULT'
}

wwn = ["123456789012345", "123456789054321", "unassigned-wwn1"]

host_vluns1 = [{'active': True,
                'volumeName': VOLUME_3PAR_NAME,
                'portPos': {'node': 7, 'slot': 1, 'cardPort': 1},
                'remoteName': wwn[1],
                'lun': 90, 'type': 0}]

host_vluns2 = [{'active': True,
                'volumeName': VOLUME_3PAR_NAME,
                'portPos': {'node': 6, 'slot': 1, 'cardPort': 1},
                'remoteName': wwn[0],
                'lun': 90, 'type': 0}]

host_vluns = [{'active': True,
               'volumeName': VOLUME_3PAR_NAME,
               'portPos': {'node': 7,
                           'slot': 1,
                           'cardPort': 1},
               'remoteName': wwn[1],
               'lun': 90, 'type': 0},
              {'active': False,
               'volumeName': VOLUME_3PAR_NAME,
               'portPos': {'node': 9,
                           'slot': 1,
                           'cardPort': 1},
               'remoteName': wwn[0],
               'lun': 90, 'type': 0}]

snap_host_vluns1 = [
    {
        'active': True,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'portPos': {'node': 7, 'slot': 1, 'cardPort': 1},
        'remoteName': wwn[1],
        'lun': 90, 'type': 0
    }
]

snap_host_vluns2 = [
    {
        'active': True,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'portPos': {'node': 6, 'slot': 1, 'cardPort': 1},
        'remoteName': wwn[0],
        'lun': 90, 'type': 0
    }
]

snap_host_vluns = [
    {
        'active': True,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'portPos': {
            'node': 7,
            'slot': 1,
            'cardPort': 1
        },
        'remoteName': wwn[1],
        'lun': 90, 'type': 0
    },
    {
        'active': False,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'portPos': {
            'node': 9,
            'slot': 1,
            'cardPort': 1
        },
        'remoteName': wwn[0],
        'lun': 90, 'type': 0
    }
]

iscsi_host_vluns = [{'active': True,
                     'hostname': FAKE_HOST,
                     'volumeName': VOLUME_3PAR_NAME,
                     'lun': TARGET_LUN, 'type': 0,
                     'remoteName': TARGET_IQN,
                     'portPos': {'node': 8, 'slot': 1, 'cardPort': 1}},
                    {'active': False,
                     'hostname': FAKE_HOST,
                     'volumeName': VOLUME_3PAR_NAME,
                     'lun': TARGET_LUN, 'type': 0,
                     'remoteName': TARGET_IQN,
                     'portPos': {'node': 9, 'slot': 1, 'cardPort': 1}}]

snap_iscsi_host_vluns = [
    {
        'active': True,
        'hostname': FAKE_HOST,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'lun': TARGET_LUN, 'type': 0,
        'remoteName': TARGET_IQN,
        'portPos': {'node': 8, 'slot': 1, 'cardPort': 1}
    },
    {
        'active': False,
        'hostname': FAKE_HOST,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'lun': TARGET_LUN, 'type': 0,
        'remoteName': TARGET_IQN,
        'portPos': {'node': 9, 'slot': 1, 'cardPort': 1}
    }
]

iscsi_host_vluns1 = [
    {
        'active': True,
        'hostname': FAKE_HOST,
        'volumeName': VOLUME_3PAR_NAME,
        'lun': TARGET_LUN, 'type': 0,
        'remoteName': TARGET_IQN,
        'portPos': {'node': 8, 'slot': 1, 'cardPort': 1}
    }
]

iscsi_host_vluns2 = [
    {
        'active': True,
        'volumeName': VOLUME_3PAR_NAME,
        'lun': TARGET_LUN, 'type': 0,
        'remoteName': TARGET_IQN,
    }
]

snap_iscsi_host_vluns1 = [
    {
        'active': True,
        'hostname': FAKE_HOST,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'lun': TARGET_LUN, 'type': 0,
        'remoteName': TARGET_IQN,
        'portPos': {'node': 8, 'slot': 1, 'cardPort': 1}
    }
]

snap_iscsi_host_vluns2 = [
    {
        'active': True,
        'volumeName': SNAPSHOT_3PAR_NAME,
        'remoteName': TARGET_IQN,
        'lun': TARGET_LUN, 'type': 0
    }
]

fake_fc_host = {'name': FAKE_HOST,
                'FCPaths': [
                    {'driverVersion': None,
                     'firmwareVersion': None,
                     'hostSpeed': 0,
                     'model': None,
                     'portPos': {'cardPort': 1, 'node': 7,
                                 'slot': 1},
                     'vendor': None,
                     'wwn': wwn[0]},
                    {'driverVersion': None,
                     'firmwareVersion': None,
                     'hostSpeed': 0,
                     'model': None,
                     'portPos': {'cardPort': 1, 'node': 6,
                                 'slot': 1},
                     'vendor': None,
                     'wwn': wwn[1]},
                ]}

fake_host = {'name': FAKE_HOST,
             'initiatorChapEnabled': False,
             'iSCSIPaths': [{"name": "iqn.1993-08.org.debian:01:222"}]}

fake_hosts = {'members': [{'name': FAKE_HOST}]}

volume_metadata = {'value': 'random-key'}

location = ("%(volume_name)s,%(lun_id)s,%(host)s,%(nsp)s" %
            {'volume_name': VOLUME_3PAR_NAME,
             'lun_id': TARGET_LUN,
             'host': FAKE_HOST,
             'nsp': 'something'})

connector = {'ip': '10.0.0.2',
             'initiator': 'iqn.1993-08.org.debian:01:222',
             'wwpns': [wwn[0], wwn[1]],
             'wwnns': ["223456789012345", "223456789054321"],
             'host': FAKE_HOST,
             'multipath': False}

connector_multipath_enabled = {'ip': '10.0.0.2',
                               'initiator': ('iqn.1993-08.org'
                                             '.debian:01:222'),
                               # Use wwn2 to allow modify-host call
                               'wwpns': [wwn[0], wwn[1], wwn[2]],
                               'wwnns': ["223456789012345",
                                         "223456789054321"],
                               'host': FAKE_HOST,
                               'multipath': True}

TASK_ID = '123456789'
TASK_DONE = 1
TASK_ACTIVE = 2
TASK_FAILED = 999
STATUS_DONE = {'status': 1}
STATUS_ACTIVE = {'status': 2}

mock_client_conf = {
    'PORT_MODE_TARGET': 2,
    'PORT_STATE_READY': 4,
    'PORT_PROTO_ISCSI': 2,
    'PORT_PROTO_FC': 1,
    'PORT_TYPE_HOST': 1,
    'TASK_DONE': TASK_DONE,
    'TASK_ACTIVE': TASK_ACTIVE,
    'HOST_EDIT_ADD': 1,
    'CHAP_INITIATOR': 1,
    'CHAP_TARGET': 2,
    'getPorts.return_value': {
        'members': FAKE_FC_PORTS + [FAKE_ISCSI_PORT]
    }
}

wsapi_version_312 = {'major': 1,
                     'build': 30102422,
                     'minor': 3,
                     'revision': 1}

wsapi_version_for_compression = {'major': 1,
                                 'build': 30301215,
                                 'minor': 6,
                                 'revision': 0}

wsapi_version_for_dedup = {'major': 1,
                           'build': 30201120,
                           'minor': 4,
                           'revision': 1}

wsapi_version_for_flash_cache = {'major': 1,
                                 'build': 30201200,
                                 'minor': 4,
                                 'revision': 2}

wsapi_version_for_remote_copy = {'major': 1,
                                 'build': 30202290,
                                 'minor': 5,
                                 'revision': 0}

# Use this to point to latest version of wsapi
wsapi_version_latest = wsapi_version_for_compression

standard_login = [
    mock.call.login(HPE3PAR_USER_NAME, HPE3PAR_USER_PASS),
    mock.call.setSSHOptions(
        HPE3PAR_SAN_IP,
        HPE3PAR_USER_NAME,
        HPE3PAR_USER_PASS,
        missing_key_policy='AutoAddPolicy',
        privatekey=HPE3PAR_SAN_SSH_PRIVATE,
        known_hosts_file=mock.ANY,
        port=HPE3PAR_SAN_SSH_PORT,
        conn_timeout=HPE3PAR_SAN_SSH_CON_TIMEOUT)]

get_id_login = [
    mock.call.getWsApiVersion(),
    mock.call.login(HPE3PAR_USER_NAME, HPE3PAR_USER_PASS),
    mock.call.setSSHOptions(
        HPE3PAR_SAN_IP,
        HPE3PAR_USER_NAME,
        HPE3PAR_USER_PASS,
        missing_key_policy='AutoAddPolicy',
        privatekey=HPE3PAR_SAN_SSH_PRIVATE,
        known_hosts_file=mock.ANY,
        port=HPE3PAR_SAN_SSH_PORT,
        conn_timeout=HPE3PAR_SAN_SSH_CON_TIMEOUT),
    mock.call.getStorageSystemInfo()]

standard_logout = [
    mock.call.logout()]
