import mock

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
GOODNESS_FUNCTION = \
    "stats.capacity_utilization < 0.6? 100:25"
FILTER_FUNCTION = \
    "stats.total_volumes < 400 && stats.capacity_utilization < 0.8"

CHAP_USER_KEY = "HPQ-docker-CHAP-name"
CHAP_PASS_KEY = "HPQ-docker-CHAP-secret"

FLASH_CACHE_ENABLED = 1
FLASH_CACHE_DISABLED = 2

# EXISTENT_PATH error code returned from hpe3parclient
EXISTENT_PATH = 73

VOLUME_ID = 'd03338a9-9115-48a3-8dfc-35cdfcdc15a7'
SRC_CG_VOLUME_ID = 'bd21d11b-c765-4c68-896c-6b07f63cfcb6'
CLONE_ID = 'd03338a9-9115-48a3-8dfc-000000000000'
VOLUME_TYPE_ID_REPLICATED = 'be9181f1-4040-46f2-8298-e7532f2bf9db'
VOLUME_TYPE_ID_DEDUP = 'd03338a9-9115-48a3-8dfc-11111111111'
VOL_TYPE_ID_DEDUP_COMPRESS = 'd03338a9-9115-48a3-8dfc-33333333333'
VOLUME_TYPE_ID_FLASH_CACHE = 'd03338a9-9115-48a3-8dfc-22222222222'
VOLUME_NAME = 'volume-' + VOLUME_ID
VOLUME_NAME_3PAR = 'osv-0DM4qZEVSKON-DXN-NwVpw'
SNAPSHOT_ID1 = '2f823bdc-e36e-4dc8-bd15-de1c7a28ff31'
SNAPSHOT_NAME1 = 'snapshot-2f823bdc-e36e-4dc8-bd15-de1c7a28ff31'
SNAPSHOT_ID2 = '8da7488a-7920-451a-ad18-0e41eca15d25'
SNAPSHOT_NAME2 = 'snapshot-8da7488a-7920-451a-ad18-0e41eca15d25'
VOLUME_3PAR_NAME = 'osv-0DM4qZEVSKON-DXN-NwVpw'
SNAPSHOT_3PAR_NAME = 'oss-L4I73ONuTci9Fd4ceij-MQ'
RCG_3PAR_NAME = 'rcg-0DM4qZEVSKON-DXN-N'
CLIENT_ID = "12345"
# fake host on the 3par
FAKE_HOST = 'fakehost'
FAKE_DOCKER_HOST = 'fakehost@foo#' + HPE3PAR_CPG
VOLUME_ID_SNAP = '761fc5e5-5191-4ec7-aeba-33e36de44156'
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
                   'IPAddr': '1.1.1.2',
                   'iSCSIName': ('iqn.2000-05.com.3pardata:'
                                 '21810002ac00383d'),
                   'linkState': 4}
volume = {'name': VOLUME_NAME,
          'id': VOLUME_ID,
          'display_name': 'Foo Volume',
          'size': 2,
          'host': FAKE_DOCKER_HOST,
          'provisioning': THIN,
          'flash_cache': None,
          'compression': None,
          'snapshots': []}

snapshot1 = {'name': SNAPSHOT_NAME1,
             'id': SNAPSHOT_ID1,
             'parent_id': VOLUME_ID,
             'expiration_hours': '10',
             'retention_hours': '10'}

snapshot2 = {'name': SNAPSHOT_NAME2,
             'id': SNAPSHOT_ID2,
             'parent_id': VOLUME_ID,
             'expiration_hours': '5',
             'retention_hours': '5'}

snapshot3 = {'name': SNAPSHOT_NAME2,
             'id': SNAPSHOT_ID2,
             # This is a child of snapshot1
             'parent_id': SNAPSHOT_ID1,
             'expiration_hours': '5',
             'retention_hours': '5'}

volume_with_snapshots = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': 'Foo Volume',
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'compression': None,
    'snapshots': [snapshot1, snapshot2]}


volume_with_multilevel_snapshot = {
    'name': VOLUME_NAME,
    'id': VOLUME_ID,
    'display_name': 'Foo Volume',
    'size': 2,
    'host': FAKE_DOCKER_HOST,
    'provisioning': THIN,
    'flash_cache': None,
    'compression': None,
    'snapshots': [snapshot1, snapshot2, snapshot3]}

volume_encrypted = {'name': VOLUME_NAME,
                    'id': VOLUME_ID,
                    'display_name': 'Foo Volume',
                    'size': 2,
                    'host': FAKE_DOCKER_HOST,
                    'encryption_key_id': 'fake_key',
                    'provisioning': THIN,
                    'flash_cache': None,
                    'snapshots': []}

volume_dedup_compression = {'name': VOLUME_NAME,
                            'id': VOLUME_ID,
                            'display_name': 'Foo Volume',
                            'size': 16,
                            'host': FAKE_DOCKER_HOST,
                            'compression': None,
                            'flash_cache': None,
                            'provisioning': DEDUP,
                            'snapshots': []}

volume_compression = {'name': VOLUME_NAME,
                      'id': VOLUME_ID,
                      'display_name': 'Foo Volume',
                      'size': 16,
                      'host': FAKE_DOCKER_HOST,
                      'compression': 'true',
                      'provisioning': THIN,
                      'flash_cache': None,
                      'snapshots': []}

volume_dedup = {'name': VOLUME_NAME,
                'id': VOLUME_ID,
                'display_name': 'Foo Volume',
                'size': 2,
                'host': FAKE_DOCKER_HOST,
                'provisioning': DEDUP,
                'flash_cache': None,
                'compression': None,
                'snapshots': []}

volume_qos = {'name': VOLUME_NAME,
              'id': VOLUME_ID,
              'display_name': 'Foo Volume',
              'size': 2,
              'host': FAKE_DOCKER_HOST,
              'provisioning': THIN,
              'flash_cache': None,
              'compression': None,
              'snapshots': []}

volume_flash_cache = {'name': VOLUME_NAME,
                      'id': VOLUME_ID,
                      'display_name': 'Foo Volume',
                      'size': 2,
                      'host': FAKE_DOCKER_HOST,
                      'provisioning': THIN,
                      'flash_cache': 'true',
                      'compression': None,
                      'snapshots': []}

wwn = ["123456789012345", "123456789054321"]

connector = {'ip': '10.0.0.2',
             'initiator': 'iqn.1993-08.org.debian:01:222',
             'wwpns': [wwn[0], wwn[1]],
             'wwnns': ["223456789012345", "223456789054321"],
             'host': FAKE_HOST,
             'multipath': False}

connector_multipath_enabled = {'ip': '10.0.0.2',
                               'initiator': ('iqn.1993-08.org'
                                             '.debian:01:222'),
                               'wwpns': [wwn[0], wwn[1]],
                               'wwnns': ["223456789012345",
                                         "223456789054321"],
                               'host': FAKE_HOST,
                               'multipath': True}

volume_type = {'name': 'gold',
               'deleted': False,
               'updated_at': None,
               'extra_specs': {'cpg': HPE3PAR_CPG2,
                               'qos:maxIOPS': '1000',
                               'qos:maxBWS': '50',
                               'qos:minIOPS': '100',
                               'qos:minBWS': '25',
                               'qos:latency': '25',
                               'qos:priority': 'low'},
               'deleted_at': None,
               'id': 'gold'}

volume_type_dedup_compression = {'name': 'dedup',
                                 'deleted': False,
                                 'updated_at': None,
                                 'extra_specs': {'cpg': HPE3PAR_CPG2,
                                                 'provisioning': 'dedup',
                                                 'compression': 'true'},
                                 'deleted_at': None,
                                 'id': VOL_TYPE_ID_DEDUP_COMPRESS}

volume_type_dedup = {'name': 'dedup',
                     'deleted': False,
                     'updated_at': None,
                     'extra_specs': {'cpg': HPE3PAR_CPG2,
                                     'provisioning': 'dedup'},
                     'deleted_at': None,
                     'id': VOLUME_TYPE_ID_DEDUP}

volume_type_flash_cache = {'name': 'flash-cache-on',
                           'deleted': False,
                           'updated_at': None,
                           'extra_specs': {'cpg': HPE3PAR_CPG2,
                                           'hpe3par:flash_cache': 'true'},
                           'deleted_at': None,
                           'id': VOLUME_TYPE_ID_FLASH_CACHE}

flash_cache_3par_keys = {'flash_cache': 'true'}

cpgs = [
    {'SAGrowth': {'LDLayout': {'diskPatterns': [{'diskType': 2}]},
                  'incrementMiB': 8192},
     'SAUsage': {'rawTotalMiB': 24576,
                 'rawUsedMiB': 768,
                 'totalMiB': 8192,
                 'usedMiB': 256},
     'SDGrowth': {'LDLayout': {'RAIDType': 4,
                               'diskPatterns': [{'diskType': 2}]},
                  'incrementMiB': 32768},
     'SDUsage': {'rawTotalMiB': 49152,
                 'rawUsedMiB': 1023,
                 'totalMiB': 36864,
                 'usedMiB': 1024 * 1},
     'UsrUsage': {'rawTotalMiB': 57344,
                  'rawUsedMiB': 43349,
                  'totalMiB': 43008,
                  'usedMiB': 1024 * 20},
     'additionalStates': [],
     'degradedStates': [],
     'failedStates': [],
     'id': 5,
     'name': HPE3PAR_CPG,
     'numFPVVs': 2,
     'numTPVVs': 0,
     'numTDVVs': 1,
     'state': 1,
     'uuid': '29c214aa-62b9-41c8-b198-543f6cf24edf'}]

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
