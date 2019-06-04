import pytest
import docker
import yaml
import re

from .base import BaseAPIIntegrationTest, TEST_API_VERSION
from .helpers import requires_api_version

from . import utils
import urllib3

from time import sleep, time
from .etcdutil import EtcdUtil
from hpe3parclient import exceptions as exc
from hpe3parclient.client import HPE3ParClient
from oslo_utils import units

# Importing test data from YAML config file
#with open("tests/integration/testdata/test_config.yml", 'r') as ymlfile:
with open("testdata/test_config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile)

# Declaring Global variables and assigning the values from YAML config file

PLUGIN_TYPE = cfg['plugin']['type']
ETCD_HOST = cfg['etcd']['host']
ETCD_PORT = cfg['etcd']['port']
CLIENT_CERT = cfg['etcd']['client_cert']
CLIENT_KEY = cfg['etcd']['client_key']
HPE3PAR_API_URL = cfg['backend']['3Par_api_url']
HPE3PAR2_API_URL = cfg['backend2']['3Par_api_url']
HPE3PAR3_API_URL = cfg['ActivePassiveRepBackend']['3Par_api_url']
HPE3PAR4_API_URL = cfg['filepersona']['3Par_api_url']
PORTS_ZONES = cfg['multipath']['ports_zones']
PORTS_ZONES2 = cfg['multipath2']['ports_zones']
SNAP_CPG = cfg['snapshot']['snap_cpg']
SNAP_CPG2 = cfg['snapshot2']['snap_cpg']
SNAP_CPG3 = cfg['snapshot3']['snap_cpg']
DOMAIN = cfg['qos']['domain']
MIN_IO = cfg['qos']['min_io']
MAX_IO = cfg['qos']['max_io']
MIN_BW = cfg['qos']['min_bw']
MAX_BW = cfg['qos']['max_bw']
LATENCY = cfg['qos']['latency']
PRIORITY = cfg['qos']['priority']
HPE3PAR_IP = cfg['backend']['3Par_IP']
HPE3PAR_IP1 = cfg['filepersona']['3Par_IP']

if PLUGIN_TYPE == 'managed':
    HPE3PAR = cfg['plugin']['managed_plugin_latest']
    HPE3PAR_OLD = cfg['plugin']['managed_plugin_old']
    CERTS_SOURCE = cfg['plugin']['certs_source']
else:
    HPE3PAR = cfg['plugin']['containerized_plugin']

@requires_api_version('1.21')
class HPE3ParVolumePluginTest(BaseAPIIntegrationTest):
    """
    This class covers all base methods to verify entities in Docker Engine.
    """
    # CentOS - hpedocker-dm-uuid-mpath-360002ac00000000000019e470001c00a
    # Ubuntu - hpedocker-scsi-360002ac0000000000001d2750001c00a
    # lets keep generic for now
    mount = r"hpedocker-"
    #mount = r"hpedocker-(?:dm-uuid-mpath|dm-name|scsi)"
    compile_mount_regex = re.compile(mount)

    def hpe_create_volume(self, name, driver, **kwargs):
        client = docker.APIClient(
            version=TEST_API_VERSION, timeout=600,
            **docker.utils.kwargs_from_env()
        )
        if 'flash_cache' in kwargs:
            kwargs['flash-cache'] = kwargs.pop('flash_cache')
        if 'qos_name' in kwargs:
            kwargs['qos-name'] = kwargs.pop('qos_name')

        # Create a volume
        docker_volume = client.create_volume(name=name, driver=driver,
                                                  driver_opts=kwargs)
        # Verify volume entry in docker managed plugin system
        self.assertIn('Name', docker_volume)
        self.assertEqual(docker_volume['Name'], name)
        self.assertIn('Driver', docker_volume)
        if driver == HPE3PAR:
            self.assertEqual(docker_volume['Driver'], HPE3PAR)
        else:
            self.assertEqual(docker_volume['Driver'], HPE3PAR_OLD)
        # Verify all volume optional parameters in docker managed plugin system
        driver_options = ['size', 'provisioning', 'flash-cache', 'compression', 'cloneOf',
                          'qos-name', 'mountConflictDelay', 'importVol', 'backend', 'virtualCopyOf', 'scheduleFrequency', 'scheduleName', 'snapshotPrefix']

        for option in driver_options:
            if option in kwargs:
                self.assertIn(option, docker_volume['Options'])
                self.assertEqual(docker_volume['Options'][option], kwargs[option])
            else:
                self.assertNotIn(option, docker_volume['Options'])

        return docker_volume

    def hpe_delete_volume(self, volume, force=False):
        # Delete a volume
        self.client.remove_volume(volume['Name'], force=force)
        volumes = self.client.volumes()
        # Verify if volume is deleted from docker managed plugin system
        if volumes['Volumes']:
            self.assertNotIn(volume, volumes['Volumes'])
        else:
            self.assertEqual(volumes['Volumes'], None)

    def hpe_inspect_volume(self, volume, **kwargs):
        # Inspect a volume.
        inspect_volume = self.client.inspect_volume(volume['Name'])
        self.assertEqual(volume['Name'], inspect_volume['Name'])
        self.assertEqual(volume['Driver'], inspect_volume['Driver'])
        self.assertEqual(volume['Options'], inspect_volume['Options'])
        self.assertIn('Status', inspect_volume)
        self.assertIn('volume_detail', inspect_volume['Status'])

        volume_details = ['size', 'provisioning', 'flash_cache', 'compression', 'mountConflictDelay', 'importVol', 'cpg', 'snapcpg', 'backend']
        qos_detail = ['enabled', 'maxIOPS', 'minIOPS', 'priority', 'vvset_name']

        for option in volume_details:
            if option == 'importVol':
                if option in kwargs:
                    self.assertIn(option, inspect_volume['Options'])
                    self.assertEqual(inspect_volume['Options'][option], kwargs[option])
            elif option == 'cpg':
                if option in kwargs:
                    self.assertIn(option, inspect_volume['Options'])
                    self.assertEqual(inspect_volume['Options'][option], kwargs[option])
            elif option == 'snapcpg':
                if option in kwargs:
                    self.assertIn("snap_cpg", inspect_volume['Status']['volume_detail'])
                    self.assertEqual(inspect_volume['Status']['volume_detail']['snap_cpg'], kwargs[option])
                else:
                    if (inspect_volume['Status']['volume_detail']['backend'] == 'DEFAULT'):
                        self.assertEqual(inspect_volume['Status']['volume_detail']['snap_cpg'],SNAP_CPG)
                    elif (inspect_volume['Status']['volume_detail']['backend'] == 'ActivePassiveRepBackend'):
                        self.assertEqual(inspect_volume['Status']['volume_detail']['snap_cpg'], SNAP_CPG3)

                    else:
                        self.assertEqual(inspect_volume['Status']['volume_detail']['snap_cpg'],SNAP_CPG2)

            elif option ==  'backend':
                if option in kwargs:
                    self.assertIn(option, inspect_volume['Options'])
                    self.assertEqual(inspect_volume['Options'][option], kwargs[option])

            else:
                if option in kwargs:
                    self.assertIn(option, inspect_volume['Status']['volume_detail'])
                    self.assertEqual(inspect_volume['Status']['volume_detail'][option], kwargs[option])
                else:
                    if option == 'size':
                        self.assertEqual(inspect_volume['Status']['volume_detail'][option], 100)
                    elif option == 'provisioning':
                        self.assertEqual(inspect_volume['Status']['volume_detail'][option], 'thin')
                    elif option == 'mountConflictDelay':
                        self.assertEqual(inspect_volume['Status']['volume_detail'][option], 30)
                    elif option == 'backend':
                        self.assertEqual(inspect_volume['Status']['volume_detail'][option], 'DEFAULT')
                    else:
                        self.assertEqual(inspect_volume['Status']['volume_detail'][option], None)
            self.assertEqual(inspect_volume['Status']['volume_detail']['3par_vol_name'][:3], 'dcv' 
)
        for option in qos_detail:
            if option in kwargs:
                self.assertIn(option, inspect_volume['Status']['qos_detail'])
                self.assertEqual(inspect_volume['Status']['qos_detail'][option], kwargs[option])
            else:
                pass
        if 'replicationGroup' in kwargs:
            self.assertEqual(inspect_volume['Status']['rcg_detail']['role'], 'Primary')
            self.assertEqual(inspect_volume['Status']['rcg_detail']['rcg_name'], kwargs['replicationGroup'])
        
        # Validating if the snapshot 'virtualCopyOf' value is same as the 'Parent volume' of the snapshot
        if 'snapshot_name' in kwargs:
            snapshots = inspect_volume['Status']['Snapshots'][0] 
            if 'snap_schedule' in snapshots:
                self.assertEqual(kwargs['snapshot_name'], snapshots['ParentName'])

        return inspect_volume

    def hpe_inspect_share(self, volume, **kwargs):
        #Inspect a share  
        inspect_volume = self.client.inspect_volume(volume['Name'])
        self.assertEqual(volume['Name'], inspect_volume['Name'])
        self.assertEqual(volume['Driver'], inspect_volume['Driver'])
        self.assertEqual(volume['Options'], inspect_volume['Options'])
        self.assertIn('Status', inspect_volume)
        # Loop until the status of the share is set to "AVAILABLE"
        timeout = time() + 600
        while 1:
            inspect_volume = self.client.inspect_volume(volume['Name'])
            sleep(10)
            if inspect_volume['Status']['status'] == 'AVAILABLE' or time() > timeout:
                break

        if inspect_volume['Status']['status'] == 'AVAILABLE':
            #Login to 3par array and get available file share list 
            hpe3par_cli = self._hpe_get_3par_client_login_filePersona()
            uri = '/fileshares/'
            fileshare_list = hpe3par_cli.http.get(uri)
            #Loop through above created list to find 'id' of the share in 'volume' object
            members = fileshare_list[1]['members']
            for i in members:
                if i.get('name') == volume['Name']:
                    fshare_index = members.index(i)
                    fshare_details = members[fshare_index]  
            #Get file share details and assert values with docker inspect volume output         
            uri = '/fileshares/%s' % fshare_details['id']
            fileshare_info = hpe3par_cli.http.get(uri)

            self.assertEqual(fileshare_info[1]['name'], inspect_volume['Name'])
            self.assertEqual(inspect_volume['Status']['protocol'], 'nfs')
            self.assertEqual(inspect_volume['Status']['fpg'], fileshare_info[1]['fpg'])
            self.assertEqual(inspect_volume['Status']['vfs'], fileshare_info[1]['vfs'])
            #Assert 'cpg','vfs', and 'size' details of share, with showfpg,showvfs,showfsquota 3par cli output.
            show_fpg = hpe3par_cli._run(['showfpg', '-d', fileshare_info[1]['fpg']])
            self.assertEqual(inspect_volume['Status']['cpg'], show_fpg[17].split(':')[1].strip())
            show_vfs = hpe3par_cli._run(['showvfs', '-d', '-vfs', fileshare_info[1]['vfs']])
            self.assertEqual(inspect_volume['Status']['vfsIPs'][0][0], show_vfs[(-2)].split(',')[1])
            self.assertEqual(inspect_volume['Status']['vfsIPs'][0][1], show_vfs[(-2)].split(',')[2])
            show_fsize = hpe3par_cli._run(['showfsquota', '-fpg', fileshare_info[1]['fpg']])
            size_unit = (inspect_volume['Status']['size']).split(" ")[1]
            if size_unit == "GiB":
                self.assertEqual(int(inspect_volume['Status']['size'].split(" ")[0]), int(show_fsize[2].split(",")[-2])/1024)
            if size_unit == "TiB":
                size_in_GiB = int(show_fsize[2].split(",")[-2])/1024
                self.assertEqual(int(inspect_volume['Status']['size'].split(" ")[0]), size_in_GiB/1024)

            #Assert client IP's of share after share mount.
            if 'mount' in kwargs:

                any_in = lambda c, d: any((i in d for i in c))
                self.assertEqual(any_in(inspect_volume['Status']['clientIPs'], fileshare_info[1]['nfsClientlist']), True)
            hpe3par_cli.logout()

            return fileshare_info




    def hpe_create_snapshot(self, snapshot_name, driver, **kwargs):
        # Create a snapshot
        snapshot_creation = self.client.create_volume(name=snapshot_name, driver=driver,
                                                      driver_opts=kwargs)
        # Verify snapshot entry in docker managed plugin system
        self.assertIn('Name', snapshot_creation)
        self.assertEqual(snapshot_creation['Name'], snapshot_name)
        self.assertIn('Driver', snapshot_creation)
        if driver == HPE3PAR:
            self.assertEqual(snapshot_creation['Driver'], HPE3PAR)
        else:
            self.assertEqual(snapshot_creation['Driver'], HPE3PAR_OLD)

        volumes = self.client.volumes()
        # Verify if created snapshot is not available docker volume lists
        self.assertIn(snapshot_creation, volumes['Volumes'])

        inspect_volume_snapshot = self.client.inspect_volume(kwargs['virtualCopyOf'])
        snapshots = inspect_volume_snapshot['Status']['Snapshots']
        snapshot_list = []
        i = 0
        for i in range(len(snapshots)):
            snapshot_list.append(snapshots[i]['Name'])
        self.assertIn(snapshot_name, snapshot_list)

        return snapshot_creation

    def hpe_inspect_snapshot(self, snapshot, **kwargs):
        # Inspect a snapshot
        inspect_snapshot = self.client.inspect_volume(kwargs['snapshot_name'])
        snapshot_options = ['virtualCopyOf', 'expirationHours', 'retentionHours', 'mountConflictDelay']

        for option in snapshot_options:
            if option in kwargs:
               if 'importVol' in kwargs:
                   self.assertEqual(inspect_snapshot['Status']['snap_detail']['parent_volume'],
                                             kwargs['virtualCopyOf'])
               else:
                   self.assertIn(option, snapshot['Options'])
                   self.assertEqual(snapshot['Options'][option], kwargs[option])
            else:
               self.assertNotIn(option, snapshot['Options'])

        self.assertEqual(inspect_snapshot['Status']['snap_detail']['is_snap'],
                         True)
        self.assertEqual(inspect_snapshot['Status']['snap_detail']['parent_volume'],
                         kwargs['virtualCopyOf'])
        if 'size' in kwargs:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['size'],
                             int(kwargs['size']))
        else:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['size'],
                             100)

        if 'mountConflictDelay' in kwargs:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['mountConflictDelay'],
                             int(kwargs['mountConflictDelay']))
        else:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['mountConflictDelay'],
                             30)

        if 'expirationHours' in kwargs:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['expiration_hours'],
                             int(kwargs['expirationHours']))
        else:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['expiration_hours'], None)

        if 'retentionHours' in kwargs:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['retention_hours'],
                             int(kwargs['retentionHours']))
        else:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['retention_hours'], None)
        if 'snapcpg' in kwargs:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['snap_cpg'],
                             (kwargs['snapcpg']))
        else:
            if (inspect_snapshot['Status']['snap_detail']['backend'] == 'DEFAULT'):
               self.assertEqual(inspect_snapshot['Status']['snap_detail']['snap_cpg'],
                             SNAP_CPG)
            else:
               self.assertEqual(inspect_snapshot['Status']['snap_detail']['snap_cpg'],
                             SNAP_CPG2)

        if 'snap_schedule' in  inspect_snapshot['Status']['snap_detail']:
            self.assertEqual(snapshot['Options']['scheduleFrequency'], inspect_snapshot['Status']['snap_detail']['snap_schedule']['sched_frequency'])
            self.assertEqual(snapshot['Options']['snapshotPrefix'], inspect_snapshot['Status']['snap_detail']['snap_schedule']['snap_name_prefix'])
            self.assertEqual(snapshot['Options']['scheduleName'], inspect_snapshot['Status']['snap_detail']['snap_schedule']['schedule_name'])
            self.assertEqual(snapshot['Options']['expHrs'], str(inspect_snapshot['Status']['snap_detail']['snap_schedule']['sched_snap_exp_hrs']))
            self.assertEqual(snapshot['Options']['retHrs'], str(inspect_snapshot['Status']['snap_detail']['snap_schedule']['sched_snap_ret_hrs']))

 

        if 'backend' in kwargs:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['backend'],
                             (kwargs['backend']))
        else:
            self.assertEqual(inspect_snapshot['Status']['snap_detail']['backend'],
                             'DEFAULT')

        self.assertEqual(inspect_snapshot['Status']['snap_detail']['3par_vol_name'][:3],'dcs')

        '''
        snap_details = ['compression', 'flash_cache', 'provisioning']

        for index in snap_details:
            self.assertEqual(inspect_snapshot['Status']['snap_detail'][index], None)
        '''

    def hpe_delete_snapshot(self, volume_name, snapshot_name, force=False, retention=None):
        # Delete a volume
        if retention:
            try:
                self.client.remove_volume(snapshot_name, force=force)
            except docker.errors.APIError as ex:
                resp = ex.status_code
                self.assertEqual(resp, 500)
        else:
            self.client.remove_volume(snapshot_name, force=force)
        result = self.client.inspect_volume(volume_name)
        if 'Snapshots' not in result['Status']:
            pass
        else:
            snapshots = result['Status']['Snapshots']
            snapshot_list = []
            i = 0
            for i in range(len(snapshots)):
                snapshot_list.append(snapshots[i]['Name'])
            if retention is not None:
                self.assertIn(snapshot_name, snapshot_list)
            else:
                self.assertNotIn(snapshot_name, snapshot_list)

    def hpe_create_host_config(self, volume_driver, binds, *args, **kwargs):
        # Create a host configuration to setup container
        host_config = self.client.create_host_config(volume_driver=volume_driver,
                                                     binds=[binds], *args, **kwargs
        )
        return host_config

    def hpe_create_container(self, image, command, host_config, *args, **kwargs):
        # Create a container
        container_info = self.client.create_container(image, command=command,
                                                      host_config=host_config,
                                                      *args, **kwargs
        )
        self.assertIn('Id', container_info)
        id = container_info['Id']
        self.tmp_containers.append(id)
        return container_info

    def hpe_mount_volume(self, image, command, host_config, *args, **kwargs):
        # Create a container
        container_info = self.client.create_container(image, command=command,
                                                      host_config=host_config,
                                                      *args, **kwargs
        )
        self.assertIn('Id', container_info)
        id = container_info['Id']
        self.tmp_containers.append(id)
        # Mount volume to this container
        self.client.start(id)
        # Inspect this container
        inspect_start = self.client.inspect_container(id)
        # Verify if container is mounted correctly in docker host.
        self.assertIn('Config', inspect_start)
        self.assertIn('Id', inspect_start)
        self.assertTrue(inspect_start['Id'].startswith(id))
        self.assertIn('Image', inspect_start)
        self.assertIn('State', inspect_start)
        self.assertIn('Running', inspect_start['State'])
        self.assertEqual(inspect_start['State']['Running'], True)
        self.assertNotEqual(inspect_start['Mounts'], None)
        mount = dict(inspect_start['Mounts'][0])
        if host_config['VolumeDriver'] == HPE3PAR:
            self.assertEqual(mount['Driver'], HPE3PAR)
        else:
            self.assertEqual(mount['Driver'], HPE3PAR_OLD)
        self.assertEqual(mount['RW'], True)
        self.assertEqual(mount['Type'], 'volume')
        self.assertNotEqual(mount['Source'], None)
        if not inspect_start['State']['Running']:
            self.assertIn('ExitCode', inspect_start['State'])
            self.assertEqual(inspect_start['State']['ExitCode'], 0)
        return container_info

    def hpe_unmount_volume(self, container_id):
 
        # Unmount volume
        self.client.stop(container_id)
        # Inspect this container
        inspect_stop = self.client.inspect_container(container_id)
        self.assertIn('State', inspect_stop)
        # Verify if container is unmounted correctly in docker host.
        state = inspect_stop['State']
        self.assertIn('Running', state)
        self.assertEqual(state['Running'], False)
        return

    def is_mounted(self, mount_source):
        if self.compile_mount_regex.search(mount_source) is not None:
            return True
        else:
            return False

    def hpe_inspect_container_volume_mount(self, volume_name, container_name):
        # Inspect container
        inspect_container = self.client.inspect_container(container_name)
        mount_source = inspect_container['Mounts'][0]['Source']
        if PLUGIN_TYPE == 'managed':
            mount_status = self.is_mounted(mount_source)
            count = 0
            while mount_status == False and count < 25:
                inspect_container = self.client.inspect_container(container_name)
                mount_source = inspect_container['Mounts'][0]['Source']
                mount_status = self.is_mounted(mount_source)
                count = count + 1
                sleep(5)
            self.assertEqual(mount_status, True)
        else:
            mount_status = self.is_mounted(mount_source)
            count = 0
            while mount_status == False and count < 25:
                inspect_container = self.client.inspect_container(container_name)
                mount_source = inspect_container['Mounts'][0]['Source']
                mount_status = self.is_mounted(mount_source)
                count = count + 1
                sleep(5)
            self.assertEqual(mount_status, True)
        # Inspect volume
        inspect_volume = self.client.inspect_volume(volume_name)
        mountpoint = inspect_volume['Mountpoint']
        mount_status2 = self.is_mounted(mountpoint)
        self.assertEqual(mount_status2, True)

    def hpe_inspect_container_volume_unmount(self, volume_name, container_name):
        # Inspect container
        inspect_container = self.client.inspect_container(container_name)
        mount_source = inspect_container['Mounts'][0]['Source']
        if PLUGIN_TYPE == 'managed':
            mount_status = self.is_mounted(mount_source)
            count = 0
            while mount_status == True and count < 25:
                inspect_container = self.client.inspect_container(container_name)
                mount_source = inspect_container['Mounts'][0]['Source']
                mount_status = self.is_mounted(mount_source)
                count = count + 1
                sleep(5)
            self.assertEqual(mount_status, False)
        else:
            mount_status = self.is_mounted(mount_source)
            count = 0
            while mount_status == True and count < 25:
                inspect_container = self.client.inspect_container(container_name)
                mount_source = inspect_container['Mounts'][0]['Source']
                mount_status = self.is_mounted(mount_source)
                count = count + 1
                sleep(5)
            self.assertEqual(mount_status, False)

        # Inspect volume
        inspect_volume = self.client.inspect_volume(volume_name)
        mountpoint = inspect_volume['Mountpoint']
        mount_status2 = self.is_mounted(mountpoint)
        self.assertEqual(mount_status2, False)

    def hpe_volume_not_created(self, volume_name):
        # Verify volume is not created
        volumes = self.client.volumes()
        if not isinstance(volumes['Volumes'], list):
           pass
        elif isinstance(volumes['Volumes'], list): 
           number_volume=len(volumes['Volumes'])
           volumes_present=[]
           for i in range(number_volume):
               volumes_present.append(volumes['Volumes'][i]['Name'])
           self.assertNotIn(volume_name, volumes_present)

class HPE3ParBackendVerification(BaseAPIIntegrationTest):
    """
    This class covers all the methods to verify entities in 3Par array.
    """

    def _hpe_get_3par_client_login(self):
        # Login to 3Par array and initialize connection for WSAPI calls
        hpe_3par_cli = HPE3ParClient(HPE3PAR_API_URL, True, False, None, True)
        hpe_3par_cli.login('3paradm', '3pardata')
        hpe_3par_cli.setSSHOptions(HPE3PAR_IP, '3paradm', '3pardata')
        return hpe_3par_cli

    def _hpe_get_3par_client_login_replication(self):
        # Login to 3Par array and initialize connection for WSAPI calls
        hpe_3par_cli = HPE3ParClient(HPE3PAR3_API_URL, True, False, None, True)
        hpe_3par_cli.login('3paradm', '3pardata')
        return hpe_3par_cli    


    def _hpe_get_3par_client_login_multi_array(self):
        # Login to 3Par array and initialize connection for WSAPI calls
        hpe_3par_cli = HPE3ParClient(HPE3PAR2_API_URL, True, False, None, True)
        hpe_3par_cli.login('3paradm', '3pardata')
        return hpe_3par_cli

    def _hpe_get_3par_client_login_filePersona(self):
        # Login to 3Par array and initialize connection for WSAPI calls
        hpe_3par_cli = HPE3ParClient(HPE3PAR4_API_URL, True, False, None, True)
        hpe_3par_cli.login('3paradm', '3pardata')
        hpe_3par_cli.setSSHOptions(HPE3PAR_IP1, '3paradm', '3pardata')
        return hpe_3par_cli


    def hpe_verify_volume_created(self, volume_name, vvs_name=None, **kwargs):

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if 'backend' in kwargs:
            hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
            hpe3par_cli = self._hpe_get_3par_client_login()

        # Get volume details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume = et.get_vol_byname(volume_name)

        etcd_volume_id = etcd_volume['id']
        backend_volume_name = utils.get_3par_vol_name(etcd_volume_id)
        # Get volume details from 3Par array
        hpe3par_volume = hpe3par_cli.getVolume(backend_volume_name)

        # Loop to wait for completion of cloning
        count = 0
        while hpe3par_volume['copyType'] == 2 and count < 60:
            hpe3par_volume = hpe3par_cli.getVolume(backend_volume_name)
            count = count + 1
            sleep(10)

        # Verify volume and its properties in 3Par array
        self.assertEqual(hpe3par_volume['name'], backend_volume_name)
        self.assertEqual(hpe3par_volume['copyType'], 1)
        self.assertEqual(hpe3par_volume['state'], 1)
        if 'size' in kwargs:
            self.assertEqual(hpe3par_volume['sizeMiB'], int(kwargs['size']) * 1024)
        else:
            self.assertEqual(hpe3par_volume['sizeMiB'], 102400)
        if 'provisioning' in kwargs:
            if kwargs['provisioning'] == 'full':
                self.assertEqual(hpe3par_volume['provisioningType'], 1)
            elif kwargs['provisioning'] == 'thin':
                self.assertEqual(hpe3par_volume['provisioningType'], 2)
            elif kwargs['provisioning'] == 'dedup':
                self.assertEqual(hpe3par_volume['provisioningType'], 6)
                self.assertEqual(hpe3par_volume['deduplicationState'], 1)
        else:
            self.assertEqual(hpe3par_volume['provisioningType'], 2)
        if 'flash_cache' in kwargs:
            if vvs_name:
                vvset = hpe3par_cli.getVolumeSet(vvs_name)
                # Ensure flash-cache-policy is set on the vvset
                self.assertEqual(vvset['flashCachePolicy'], 1)
                # Ensure the created volume is a member of the vvset
                self.assertIn(backend_volume_name,
                              [vv_name for vv_name in vvset['setmembers']]
                )
            elif kwargs['flash_cache'] == 'true':
                vvset_name = utils.get_3par_vvset_name(etcd_volume_id)
                vvset = hpe3par_cli.getVolumeSet(vvset_name)
                # Ensure flash-cache-policy is set on the vvset
                self.assertEqual(vvset['flashCachePolicy'], 1)
                # Ensure the created volume is a member of the vvset
                self.assertIn(backend_volume_name,
                              [vv_name for vv_name in vvset['setmembers']]
                )
            else:
                vvset_name = utils.get_3par_vvset_name(etcd_volume_id)
                vvset = hpe3par_cli.getVolumeSet(vvset_name)
                # Ensure vvset is not available in 3par.
                self.assertEqual(vvset, None)
        if 'compression' in kwargs:
            if kwargs['compression'] == 'true':
                self.assertEqual(hpe3par_volume['compressionState'], 1)
            else:
                self.assertEqual(hpe3par_volume['compressionState'], 2)
        if 'clone' in kwargs:
            if "snapcpg" in kwargs:
                self.assertEqual(hpe3par_volume['snapCPG'], kwargs['snapcpg'])
            else:
                if 'backend' in kwargs:
                    self.assertEqual(hpe3par_volume['snapCPG'], SNAP_CPG2)
                else:
                    self.assertEqual(hpe3par_volume['snapCPG'], SNAP_CPG)
            self.assertEqual(hpe3par_volume['copyType'], 1)
        if 'qos' in kwargs:
            vvset = hpe3par_cli.getVolumeSet(vvs_name)
            self.assertEqual(vvset['qosEnabled'], True)
            qos = hpe3par_cli.queryQoSRule(vvs_name)
            self.assertNotEqual(qos, None)
            self.assertIn(backend_volume_name,
                          [vv_name for vv_name in vvset['setmembers']]
            )
        if 'importVol' in kwargs:
            self.assertEqual(etcd_volume['display_name'],kwargs['importVol'])
            self.assertEqual(hpe3par_volume['name'][:3], "dcv")
        if 'cpg' in kwargs:
            self.assertEqual(hpe3par_volume['userCPG'],kwargs['cpg'])
        if 'snapcpg' in kwargs:
            self.assertEqual(hpe3par_volume['snapCPG'],kwargs['snapcpg'])


        hpe3par_cli.logout()


    def hpe_verify_share_created(self, volume_name, fileshare_id):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login_filePersona()

        #Get share details from wsapi

        uri = '/fileshares/%s' % fileshare_id
        fileshare_info = hpe3par_cli.http.get(uri)

        self.assertEqual(fileshare_info[1]['name'], volume_name)
        hpe3par_cli.logout()

    def hpe_verify_share_deleted(self, volume_name):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login_filePersona()

        uri = '/fileshares/'
        fileshare_list = hpe3par_cli.http.get(uri)
        #Loop through above created list and validate share not in list
        members = fileshare_list[1]['members']
        for i in members:
            self.assertNotEqual(i.get('name'),volume_name)

        hpe3par_cli.logout()


    def hpe_verify_volume_deleted(self, volume_name, backend=None):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
#        hpe3par_cli = self._hpe_get_3par_client_login()

        if backend is not None:
           hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
           hpe3par_cli = self._hpe_get_3par_client_login()

        # Get volume details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume = et.get_vol_byname(volume_name)
        if etcd_volume is not None:
            etcd_volume_id = etcd_volume['id']
            backend_volume_name = utils.get_3par_vol_name(etcd_volume_id)
            # Get volume details from 3Par array
            hpe3par_volume = hpe3par_cli.getVolume(backend_volume_name)
            self.assertEqual(hpe3par_volume['name'], None)
        else:
            # Verify volume is removed from 3Par array
            self.assertEqual(etcd_volume, None)
        hpe3par_cli.logout()

    def hpe_verify_snapshot_created(self, volume_name, snapshot_name, **kwargs):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if 'backend' in kwargs:
            hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
            hpe3par_cli = self._hpe_get_3par_client_login()

        # Get volume details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume_snapshot = et.get_vol_byname(volume_name)
        etcd_volume_id = etcd_volume_snapshot['id']
        backend_volume_name = utils.get_3par_vol_name(etcd_volume_id)
        etcd_snapshot = etcd_volume_snapshot['snapshots']
        i=0
        for i in range(len(etcd_snapshot)):
            if etcd_snapshot[i]['name'] == snapshot_name:
                etcd_snapshot_id = etcd_snapshot[i]['id']
                backend_snapshot_name = utils.get_3par_snapshot_name(etcd_snapshot_id)
                # Get volume details from 3Par array
                hpe3par_snapshot = hpe3par_cli.getVolume(backend_snapshot_name)
                # Verify volume and its properties in 3Par array
                self.assertEqual(hpe3par_snapshot['name'], backend_snapshot_name)
                self.assertEqual(hpe3par_snapshot['state'], 1)
                self.assertEqual(hpe3par_snapshot['provisioningType'], 3)
                if "snapcpg" in kwargs:
                    self.assertEqual(hpe3par_snapshot['snapCPG'], kwargs['snapcpg'])
                else:
                    if 'backend' in kwargs:
                        self.assertEqual(hpe3par_snapshot['snapCPG'], SNAP_CPG2)
                    else:
                        self.assertEqual(hpe3par_snapshot['snapCPG'], SNAP_CPG)
                self.assertEqual(hpe3par_snapshot['copyType'], 3)
                self.assertEqual(hpe3par_snapshot['copyOf'], backend_volume_name)
                if 'expirationHours' in kwargs:
                    hpe_snapshot_expiration = int(hpe3par_snapshot['expirationTimeSec']) - int(
                        hpe3par_snapshot['creationTimeSec'])
                    hpe_snap_expiration_list = [hpe_snapshot_expiration-2, hpe_snapshot_expiration-1, 
                                                hpe_snapshot_expiration, hpe_snapshot_expiration+1, 
                                                hpe_snapshot_expiration+2]
                    docker_snapshot_expiration = int(kwargs['expirationHours']) * 60 * 60
                    self.assertIn(docker_snapshot_expiration, hpe_snap_expiration_list)
                if 'retentionHours' in kwargs:
                    hpe_snapshot_retention = int(hpe3par_snapshot['retentionTimeSec']) - int(
                        hpe3par_snapshot['creationTimeSec'])
                    hpe_snap_retention_list = [hpe_snapshot_retention-2, hpe_snapshot_retention-1, 
                                               hpe_snapshot_retention, hpe_snapshot_retention+1, 
                                               hpe_snapshot_retention+2]
                    docker_snapshot_retention = int(kwargs['retentionHours']) * 60 * 60
                    self.assertIn(docker_snapshot_retention, hpe_snap_retention_list)
                if 'importVol' in kwargs:
                    etcd_volume_snapshot1 = et.get_vol_byname(snapshot_name)
                    self.assertEqual(etcd_volume_snapshot1['display_name'],kwargs['importVol'])
                    self.assertEqual(hpe3par_snapshot['name'][:3], "dcs")

        hpe3par_cli.logout()

    def hpe_verify_snapshot_deleted(self, volume_name, snapshot_name, backend=None):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if backend is not None:
           hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
           hpe3par_cli = self._hpe_get_3par_client_login()

        # Get volume details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume_snapshot = et.get_vol_byname(volume_name)
        etcd_snapshot = etcd_volume_snapshot['snapshots']
        etcd_snapshot_num = len(etcd_snapshot)
        if etcd_snapshot_num > 0:
            i = 0
            for i in range(etcd_snapshot_num):
                if etcd_snapshot[i]['name'] == snapshot_name:
                    etcd_snapshot_id = etcd_snapshot[i]['id']
                    backend_snapshot_name = utils.get_3par_snapshot_name(etcd_snapshot_id)
                    # Get volume details from 3Par array
                    hpe3par_snapshot = hpe3par_cli.getVolume(backend_snapshot_name)
                    # Verify volume and its properties in 3Par array
                    self.assertEqual(hpe3par_snapshot['name'], None)
        else:
            # Verify volume is removed from 3Par array
            self.assertEqual(etcd_snapshot, [])
        hpe3par_cli.logout()

    def hpe_verify_volume_mount(self, volume_name, backend=None):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if backend is not None:
           hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
           hpe3par_cli = self._hpe_get_3par_client_login()

        # Get volume details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume = et.get_vol_byname(volume_name)
        etcd_volume_id = etcd_volume['id']
        # Get volume details and VLUN details from 3Par array
        backend_volume_name = utils.get_3par_vol_name(etcd_volume_id)
        vluns = hpe3par_cli.getVLUNs()
        vlun_cnt = 0
        # VLUN Verification
        for member in vluns['members']:
            if member['volumeName'] == backend_volume_name and member['active']:
                vlun_cnt += 1
        if backend is not None:
           self.assertEqual(vlun_cnt, PORTS_ZONES2)
        else:
           self.assertEqual(vlun_cnt, PORTS_ZONES)
        hpe3par_cli.logout()

    def hpe_verify_volume_unmount(self, volume_name, backend=None):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if backend is not None:
           hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
           hpe3par_cli = self._hpe_get_3par_client_login()

        # Get volume details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume = et.get_vol_byname(volume_name)
        etcd_volume_id = etcd_volume['id']
        # Get volume details and VLUN details from 3Par array
        backend_volume_name = utils.get_3par_vol_name(etcd_volume_id)

        try:
            vlun = hpe3par_cli.getVLUN(backend_volume_name)
            # Verify VLUN is not present in 3Par array.
            self.assertEqual(vlun, None)
        except exc.HTTPNotFound:
            hpe3par_cli.logout()
            return
        hpe3par_cli.logout()

    def hpe_verify_snapshot_mount(self, snapshot_name, backend=None):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if backend is not None:
           hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
           hpe3par_cli = self._hpe_get_3par_client_login()

        # Get snapshot details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_snapshot = et.get_vol_byname(snapshot_name)
        etcd_snapshot_id = etcd_snapshot['id']
        # Get snapshot details and VLUN details from 3Par array
        backend_snapshot_name = utils.get_3par_snapshot_name(etcd_snapshot_id)
        vluns = hpe3par_cli.getVLUNs()
        vlun_cnt = 0
        # VLUN Verification
        for member in vluns['members']:
            if member['volumeName'] == backend_snapshot_name and member['active']:
                vlun_cnt += 1
        if backend is not None:
           self.assertEqual(vlun_cnt, PORTS_ZONES2)
        else:
           self.assertEqual(vlun_cnt, PORTS_ZONES)
        hpe3par_cli.logout()

    def hpe_verify_snapshot_unmount(self, snapshot_name, backend=None):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if backend is not None:
           hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        else:
           hpe3par_cli = self._hpe_get_3par_client_login()

        # Get snapshot details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_snapshot = et.get_vol_byname(snapshot_name)
        etcd_snapshot_id = etcd_snapshot['id']
        # Get snapshot details and VLUN details from 3Par array
        backend_snapshot_name = utils.get_3par_snapshot_name(etcd_snapshot_id)

        try:
            vlun = hpe3par_cli.getVLUN(backend_snapshot_name)
            # Verify VLUN is not present in 3Par array.
            self.assertEqual(vlun, None)
        except exc.HTTPNotFound:
            hpe3par_cli.logout()
            return
        hpe3par_cli.logout()

    def hpe_get_vlun(self, volume_name):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login()
        # Get volume details from etcd service
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume = et.get_vol_byname(volume_name)
        etcd_volume_id = etcd_volume['id']
        # Get volume details and VLUN details from 3Par array
        backend_volume_name = utils.get_3par_vol_name(etcd_volume_id)
        vlun = hpe3par_cli.getVLUN(backend_volume_name)
        hpe3par_cli.logout()
        return vlun

    def hpe_check_volume(self, volume_name):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login()
        et = EtcdUtil(ETCD_HOST, ETCD_PORT, CLIENT_CERT, CLIENT_KEY)
        etcd_volume = et.get_vol_byname(volume_name)
        etcd_volume_id = etcd_volume['id']
        # Get volume details and VLUN details from 3Par array
        backend_volume_name = utils.get_3par_vol_name(etcd_volume_id)
        hpe3par_volume = hpe3par_cli.getVolume(backend_volume_name)
        hpe3par_cli.logout()
        return hpe3par_volume

    def hpe_create_verify_vvs_with_qos(self, vvs_name):

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login()

        hpe3par_cli.createVolumeSet(vvs_name, domain=DOMAIN)

        qosRule = {}
        if MIN_IO:
            qosRule['ioMinGoal'] = int(MIN_IO)
            if MAX_IO is None:
                qosRule['ioMaxLimit'] = int(MIN_IO)
        if MAX_IO:
            qosRule['ioMaxLimit'] = int(MAX_IO)
            if MIN_IO is None:
                qosRule['ioMinGoal'] = int(MAX_IO)
        if MIN_BW:
            qosRule['bwMinGoalKB'] = int(MIN_BW) * units.Ki
            if MAX_BW is None:
                qosRule['bwMaxLimitKB'] = int(MIN_BW) * units.Ki
        if MAX_BW:
            qosRule['bwMaxLimitKB'] = int(MAX_BW) * units.Ki
            if MIN_BW is None:
                qosRule['bwMinGoalKB'] = int(MAX_BW) * units.Ki
        if LATENCY:
            qosRule['latencyGoal'] = int(LATENCY)
        if PRIORITY:
            qosRule['priority'] = int(PRIORITY)

        try:
            hpe3par_cli.createQoSRules(vvs_name, qosRule)
        except Exception as ex:
            raise ex

        vvset = hpe3par_cli.getVolumeSet(vvs_name)
        self.assertNotEqual(vvset, None)
        self.assertEqual( vvset['qosEnabled'], True)
        # Presence of QoS in VVS
        # at the backend with the QoS values
        try:
            qos = hpe3par_cli.queryQoSRule(vvs_name)
            self.assertNotEqual(qos, None)
        except exc.HTTPNotFound as e:
        # In case vvs is present, QoS is NOT set in the backend
        # Hence we HTTPNotFound exception is caught here which
        # needs to be ignored
            raise e
        hpe3par_cli.logout()

    def hpe_remove_vvs_qos(self, vvs_name):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login()

        hpe3par_cli.deleteQoSRules(vvs_name)
        hpe3par_cli.deleteVolumeSet(vvs_name)
        hpe3par_cli.logout()


    def hpe_recover_remote_copy_group(self, rcg_name, action):

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login_replication()
        rcopyInfo = hpe3par_cli.getRemoteCopyGroup(rcg_name)
        rcopygrpname = rcopyInfo.get("remoteGroupName")

        hpe3par_cli.stopRemoteCopy(rcg_name)
        
        rcopyStatus = hpe3par_cli.remoteCopyGroupStatusStoppedCheck(rcg_name)
        hpe3par_cli.logout()

        hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        hpe3par_cli.recoverRemoteCopyGroupFromDisaster(rcopygrpname, int(action), optional=None)
        hpe3par_cli.recoverRemoteCopyGroupFromDisaster(rcopygrpname, 9)
        hpe3par_cli.logout()
        return rcopygrpname

    
    def hpe_verify_snapshot_schedule(self, schedule_name, snapshot):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login()

        hpe3par_schedule = hpe3par_cli.getSchedule(schedule_name)
        schedule_details_cli = hpe3par_schedule[2].split(',')
        
        self.assertEqual(snapshot['Options']['scheduleName'], schedule_details_cli[0])
        self.assertEqual(snapshot['Options']['scheduleFrequency'], ' '.join(schedule_details_cli[2:7]))
        schedule_command = re.split('\s+', schedule_details_cli[1])
        self.assertEqual(schedule_command[3], (snapshot['Options']['expHrs'])+"h")
        self.assertEqual(schedule_command[5], (snapshot['Options']['retHrs'])+"h")
           
        hpe3par_cli.logout()


    def hpe_wait_for_all_backends_to_initialize(self, driver=None, **kwargs):
        # This is in order to handle Asynchronous backend initialization implemented
        # as part of plugin 3.1
        client = docker.APIClient(
            version=TEST_API_VERSION, timeout=600,
            **docker.utils.kwargs_from_env()
        )
        while True:
            try:
                result = client.create_volume(driver=driver,
                                 driver_opts=kwargs)
                sleep(5)
            except docker.errors.APIError as e:
                if 'INITIALIZING' in str(e):
                    pass
                elif 'FAILED' in str(e):
                    raise e
                else:
                    return


    def hpe_restore_remote_copy_group(self, rcg_name, action):

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        hpe3par_cli = self._hpe_get_3par_client_login_multi_array()
        hpe3par_cli.recoverRemoteCopyGroupFromDisaster(rcg_name, int(action), optional=None)
        hpe3par_cli.logout()
