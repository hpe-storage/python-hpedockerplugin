####################################################################
# Reliability Test Script for HPE 3Par Docker Volume plugin
#
#      randomly performs:  volume & snapshot creation, deletion, mount and unmount
#      for a duration of time.
#
#       Prerequisites:
#           - a running Docker engine
#           - Docker SDK
#           - Python Packages
#           - HPE 3Par Docker Volume plugin in enabled state
######################################################################

import argparse
import os
from os import sys
import random
import logging
import time
from time import time
from datetime import timedelta
import commands
import docker


# Test global variables

BUSYBOX = 'busybox:latest'
TEST_API_VERSION = os.environ.get('DOCKER_TEST_API_VERSION')

logger = None

totalActions = 0
totalActions_create_volume = 0
totalActions_delete_volume = 0
totalActions_mount_volume = 0
totalActions_unmount_volume = 0
totalActions_create_snapshot = 0
totalActions_delete_snapshot = 0
totalActions_mount_snapshot = 0
totalActions_unmount_snapshot = 0

totalErrors = 0
totalErrors_create_volume = 0
totalErrors_delete_volume = 0
totalErrors_mount_volume = 0
totalErrors_unmount_volume = 0
totalErrors_create_snapshot = 0
totalErrors_delete_snapshot = 0
totalErrors_mount_snapshot = 0
totalErrors_unmount_snapshot = 0

clock_start = time()

volumeCount=0
snapshotCount=0

waitTimeInMinutes = 5

parser = argparse.ArgumentParser()
parser.add_argument("-maxVolumes")
parser.add_argument("-maxVolumeSize", default=10)
parser.add_argument("-duration")
parser.add_argument("-plugin")
parser.add_argument("-etcd")
parser.add_argument("-provisioning")
parser.add_argument("-backend")
parser.add_argument("-cpg")
parser.add_argument("-logfile", default=("./DockerChoTest-%d.log" % time()))
args = parser.parse_args()

def prompt_for_arg(arg, field, prompt, default):
    if getattr(arg, field) is None:
        try:
            r = raw_input(prompt)
            if len(r) > 0:
                setattr(arg, field, r)
            else:
                setattr(arg, field, default)
        except:
            print "Aborted."
            sys.exit()

prompt_for_arg(args, "maxVolumes", "Max number of volumes to create (8): ", "8")
prompt_for_arg(args, "duration", "Test duration in minutes (1): ", "1")
prompt_for_arg(args, "plugin", "Name of the plugin repository with version (hpe:latest): ", "hpe:latest")
prompt_for_arg(args, "provisioning", "Provisioning type of volumes (thin, full or dedup): ", "thin")
prompt_for_arg(args, "etcd", "Name of the etcd container (etcd): ", "etcd")
prompt_for_arg(args, "backend", "Name of the backend (default): ", "selected_default_backend")
prompt_for_arg(args, "cpg", "Name of the CPG (Default CPG in hpe.conf): ", "selected_default_cpg")
print

args.duration = int(args.duration)
args.maxVolumes = int(args.maxVolumes)
args.maxVolumeSize = int(args.maxVolumeSize)
HPE3PAR = args.plugin
PROVISIONING = args.provisioning
ETCD_CONTAINER = args.etcd
CPG = args.cpg
BACKEND = args.backend


#######################################################

##### Logging Functions ######################################
def SetupLogging(logfile=None):
    # create logger
    global logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s%(message)s', datefmt="[%Y-%m-%d][%H:%M:%S]")

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)

    # also log to a file given on command line
    if logfile:
        ch = logging.FileHandler(logfile,"w")
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

# Method for message logger and count the number of operations performed during the test
def LogMessage(msg="",actionIncrement=0,action=None):
    global totalActions
    global totalActions_create_volume
    global totalActions_delete_volume
    global totalActions_mount_volume
    global totalActions_unmount_volume
    global totalActions_create_snapshot
    global totalActions_delete_snapshot
    global totalActions_mount_snapshot
    global totalActions_unmount_snapshot

    totalActions += actionIncrement

    entry = "[A:%d,E:%d] %s" % (totalActions, totalErrors, msg)

    logger.info(entry)

    if action and action == "create_volume":
        totalActions_create_volume += actionIncrement
    elif action and action == "delete_volume":
        totalActions_delete_volume += actionIncrement
    elif action and action == "mount_volume":
        totalActions_mount_volume += actionIncrement
    elif action and action == "unmount_volume":
        totalActions_unmount_volume += actionIncrement
    elif action and action == "create_snapshot":
        totalActions_create_snapshot += actionIncrement
    elif action and action == "delete_snapshot":
        totalActions_delete_snapshot += actionIncrement
    elif action and action == "mount_snapshot":
        totalActions_mount_snapshot += actionIncrement
    elif action and action == "unmount_snapshot":
        totalActions_unmount_snapshot += actionIncrement

    if msg == "break out wait after 15 minutes...":
        dump = commands.getstatusoutput('top -bn1')
        entry = "[A:%d,E:%d] %s" % (totalActions, totalErrors, dump)
        logger.info(entry)

# Method for error logger and count the number of errors occurred during the tests
def LogError(msg="", errorIncrement=1, action=None):
    global totalErrors
    global totalErrors_create_volume
    global totalErrors_delete_volume
    global totalErrors_mount_volume
    global totalErrors_unmount_volume
    global totalErrors_create_snapshot
    global totalErrors_delete_snapshot
    global totalErrors_mount_snapshot
    global totalErrors_unmount_snapshot

    totalErrors += errorIncrement

    entry = "[A:%d,E:%d] ERROR >>>>>> %s" % (totalActions, totalErrors, msg)
    logger.info(entry)

    if action and action == "create_volume":
        totalErrors_create_volume += errorIncrement
    elif action and action == "delete_volume":
        totalErrors_delete_volume += errorIncrement
    elif action and action == "mount_volume":
        totalErrors_mount_volume += errorIncrement
    elif action and action == "unmount_volume":
        totalErrors_unmount_volume += errorIncrement
    elif action and action == "create_snapshot":
        totalErrors_create_snapshot += errorIncrement
    elif action and action == "delete_snapshot":
        totalErrors_delete_snapshot += errorIncrement
    elif action and action == "mount_snapshot":
        totalErrors_mount_snapshot += errorIncrement
    elif action and action == "unmount_snapshot":
        totalErrors_unmount_snapshot += errorIncrement

# Method for logging test results and test time after performing the different actions
def TestFinished():
    global clock_start
    LogMessage( "Test performed %s actions." % totalActions)
    LogMessage( "Test performed %s create volume actions." % totalActions_create_volume)
    LogMessage( "Test performed %s delete volume actions." % totalActions_delete_volume)
    LogMessage( "Test performed %s mount volume actions." % totalActions_mount_volume)
    LogMessage( "Test performed %s unmount volume actions." % totalActions_unmount_volume)
    LogMessage("Test performed %s create snapshot actions." % totalActions_create_snapshot)
    LogMessage("Test performed %s delete snapshot actions." % totalActions_delete_snapshot)
    LogMessage("Test performed %s mount snapshot actions." % totalActions_mount_snapshot)
    LogMessage("Test performed %s unmount snapshot actions." % totalActions_unmount_snapshot)

    LogMessage( "Test observed  %s errors." % totalErrors)
    LogMessage( "Test observed  %s create volume errors." % totalErrors_create_volume)
    LogMessage( "Test observed  %s delete volume errors." % totalErrors_delete_volume)
    LogMessage( "Test observed  %s mount volume errors." % totalErrors_mount_volume)
    LogMessage( "Test observed  %s unmount volume errors." % totalErrors_unmount_volume)
    LogMessage( "Test observed  %s create snapshot errors." % totalErrors_create_snapshot)
    LogMessage( "Test observed  %s delete snapshot errors." % totalErrors_delete_snapshot)
    LogMessage( "Test observed  %s mount snapshot errors." % totalErrors_mount_snapshot)
    LogMessage( "Test observed  %s unmount snapshot errors." % totalErrors_unmount_snapshot)


    LogMessage( "Total test time: %s" % timedelta(seconds=time()-clock_start))
    LogMessage( "Test finished.")

##### Exception Classes ######################################
class TestError:
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

##### Docker Volume Plugin class ######################################
class Docker3ParVolumePlugin():
    # method to perform create volume operation
    def create_volume(self, name, **kwargs):
        client = docker.from_env(version=TEST_API_VERSION)
        if 'flash_cache' in kwargs:
            kwargs['flash-cache'] = kwargs.pop('flash_cache')
        # Create a volume
        volume = client.volumes.create(name=name, driver=HPE3PAR,
                                       labels={'type': 'volume'},
                                       driver_opts=kwargs
        )
        assert volume.id
        assert volume.name == name
        assert volume.attrs['Driver'] == HPE3PAR
        assert volume.attrs['Options'] == kwargs
        get_volume = client.volumes.get(volume.id)
        assert get_volume.name == name
        return volume

    # method to perform delete volume operation
    def delete_volume(self, volume):
        client = docker.from_env(version=TEST_API_VERSION)
        volume.remove()
        assert volume not in client.volumes.list()
        return True

    # method to perform mount operation on volume
    def mount_volume(self, volume):
        client = docker.from_env(version=TEST_API_VERSION)
        container = client.containers.run(BUSYBOX, "sh", detach=True,
                                          tty=True, stdin_open=True,
                                          volumes=[volume.name + ':/insidecontainer'],
                                          labels={'volume': volume.name, 'mount': 'volume'}
        )
        container.exec_run("sh -c 'echo \"data\" > /insidecontainer/test'")
        return container

    # method to perform unmount operation on volume and delete containers after performing operation
    def unmount_volume(self, container):
        ExecResult = container.exec_run("cat /insidecontainer/test")
        assert ExecResult.exit_code == 0
        assert ExecResult.output == 'data\n'
        container.stop()
        assert container.wait()['StatusCode'] == 0 or 137
        container.remove()
        return True

    # method to perform create snapshot operation
    def create_snapshot(self, name, **kwargs):
        client = docker.from_env(version=TEST_API_VERSION)
        # Create a snapshot
        snapshot = client.volumes.create(name=name, driver=HPE3PAR,
                                         labels={'type': 'snapshot'},
                                         driver_opts=kwargs
        )
        assert snapshot.id
        assert snapshot.name == name
        assert snapshot.attrs['Driver'] == HPE3PAR
        assert snapshot.attrs['Options'] == kwargs
        get_snapshot = client.volumes.get(snapshot.id)
        assert get_snapshot.name == name
        return snapshot

    # method to perform delete snapshot operation
    def delete_snapshot(self, snapshot):
        client = docker.from_env(version=TEST_API_VERSION)
        snapshot.remove()
        assert snapshot not in client.volumes.list()
        return True

    # method to perform mount operation on snapshot
    def mount_snapshot(self, snapshot):
        client = docker.from_env(version=TEST_API_VERSION)
        container = client.containers.run(BUSYBOX, "sh", detach=True,
                                          tty=True, stdin_open=True,
                                          volumes=[volume.name + ':/insidecontainer'],
                                          labels={'snapshot': snapshot.name, 'mount': 'snapshot'}
        )
        container.exec_run("sh -c 'echo \"data\" > /insidecontainer/test'")
        return container

    # method to perform unmount operation on snapshot and delete containers after performing operation
    def unmount_snapshot(self, container):
        ExecResult = container.exec_run("cat /insidecontainer/test")
        assert ExecResult.exit_code == 0
        assert ExecResult.output == 'data\n'
        container.stop()
        assert container.wait()['StatusCode'] == 0 or 137
        container.remove()
        return True


##### Individual test functions ######################################

def test_create_volume():
    global volumeCount
    name = "volume-%d" % volumeCount
    volumeCount += 1
    capacity = random.randint(1,args.maxVolumeSize)
    LogMessage("==========> Performing create of new %d GB volume: %s <==========" % (capacity,name))
    if CPG == "selected_default_cpg" and BACKEND == "selected_default_backend":
        volume = dcv.create_volume(name, size=str(capacity), provisioning=PROVISIONING)
    elif CPG == "selected_default_cpg":
        volume = dcv.create_volume(name, size=str(capacity), provisioning=PROVISIONING, backend=BACKEND)
    elif BACKEND == "selected_default_backend":
        volume = dcv.create_volume(name, size=str(capacity), provisioning=PROVISIONING, cpg=CPG)
    else:
        volume = dcv.create_volume(name, size=str(capacity), provisioning=PROVISIONING, cpg=CPG, backend=BACKEND)

    return volume

def test_create_snapshot(volume_name):
    global snapshotCount
    name = "snapshot-%d" % snapshotCount
    snapshotCount += 1
    LogMessage("==========> Performing create of new snapshot of %s : %s <==========" % (volume_name, name))
    snapshot = dcv.create_snapshot(name, virtualCopyOf=volume_name)
    return snapshot

#######################################################

# This part will perform create_volume, mount_unmount_volume and delete_volume
# operations randomly till the time in minutes passed as duration during running this test.

SetupLogging(args.logfile)
random.seed()

LogMessage("=====================STARTING %s TESTS===================" % os.path.basename(os.sys.argv[0]))
LogMessage("Args: %s" % args)


try:
    client = docker.from_env(version=TEST_API_VERSION)
    dcv = Docker3ParVolumePlugin()

    ######################################################
    # Defining actions and % of time they should be performed (from previous entry to %)
    # create volume    - 15%
    # create snapshot  - 12%
    # mount volume     - 13%
    # unmount volume   - 13%
    # mount snapshot   - 10%
    # unmount snapshot - 10%
    # delete snapshot  - 12%
    # delete volume    - 15%
    #######################################################

    actions = [("create_volume", 15),("create_snapshot", 27),("mount_volume", 40),
               ("unmount_volume", 53), ("mount_snapshot", 63), ("unmount_snapshot", 73),
               ("delete_snapshot", 85),("delete_volume", 100)]

    volumes = []
    volume_list = []
    container_list = []
    action = None
    hour_start = time()

    while (time() - clock_start) < int(args.duration) * 60:

        num = random.randint(1, 100)
        action = [action for (action, value) in actions if num <= value][0]

        try:
            if action == "create_volume":
                volumes = client.volumes.list(filters = {'driver':HPE3PAR,
                                                         'label': 'type=volume'})
                if len(volumes) >= args.maxVolumes - 1:
                    continue
                else:
                    performed_action= test_create_volume()
                    if performed_action:
                        LogMessage("************Successfully completed %s operation.**************" % action,1,action)

            elif action == "mount_volume":
                volumes = client.volumes.list(filters = {'dangling':True, 'driver':HPE3PAR,
                                                         'label': 'type=volume'})
                dangling_volumes = len(volumes)
                if dangling_volumes > 0:
                    random_volume = volumes[random.randint(0, (dangling_volumes-1))]
                    LogMessage("==========> Performing mount operation for volume: %s <==========" % random_volume.name)
                    performed_action = dcv.mount_volume(random_volume)
                    if performed_action:
                        LogMessage("************Successfully completed %s operation.************" % action,1,action)

            elif action == "unmount_volume":
                container_list = client.containers.list(all=True,
                                                        filters={'since': ETCD_CONTAINER, 'status': 'running',
                                                                 'label': 'mount=volume'})
                if len(container_list) > 0:
                    LogMessage("==========> Performing unmount operation for volume: %s <==========" % \
                               container_list[0].labels['volume'] )
                    performed_action = dcv.unmount_volume(container_list[0])
                    if performed_action:
                        LogMessage("************Successfully completed %s operation.************" % action,1,action)

            elif action == "delete_volume":
                volumes = client.volumes.list(filters={'dangling': True, 'driver':HPE3PAR,
                                                       'label': 'type=volume'})
                dangling_volumes = len(volumes)
                if dangling_volumes > 0:
                    for volume in volumes:
                        if 'Snapshots' not in volume.collection.get(volume.name).attrs['Status']:
                            LogMessage("==========>Performing delete operation on volume: %s <==========" % volume.name)
                            performed_action = dcv.delete_volume(volume)
                            if performed_action:
                                LogMessage("************Successfully completed %s operation.************" % action,1,action)
                            break

                local_volumes_list = client.volumes.list(filters={'dangling': True, 'driver': 'local'})
                local_volumes = len(local_volumes_list)
                if local_volumes > 0:
                    for local in local_volumes_list:
                        dcv.delete_volume(local)

            elif action == "create_snapshot":
                snapshots = client.volumes.list(filters = {'driver':HPE3PAR,
                                                         'label': 'type=snapshot'})
                if len(snapshots) >= args.maxVolumes - 1:
                    continue
                else:
                    volumes = client.volumes.list(filters={'driver':HPE3PAR, 'label': 'type=volume'})
                    volumes_len = len(volumes)
                    if volumes_len > 0:
                        random_volume = volumes[random.randint(0, (volumes_len - 1))]
                        performed_action= test_create_snapshot(random_volume.name)
                        if performed_action:
                            LogMessage("************Successfully completed %s operation.**************" % action,1,action)

            elif action == "mount_snapshot":
                snapshots = client.volumes.list(filters = {'dangling':True, 'driver':HPE3PAR,
                                                           'label': 'type=snapshot'})
                dangling_snapshots = len(snapshots)
                if dangling_snapshots > 0:
                    random_snapshot = snapshots[random.randint(0, (dangling_snapshots-1))]
                    LogMessage("==========> Performing mount operation for snapshot: %s <==========" % random_snapshot.name)
                    performed_action = dcv.mount_snapshot(random_snapshot)
                    if performed_action:
                        LogMessage("************Successfully completed %s operation.************" % action,1,action)

            elif action == "unmount_snapshot":
                container_list = client.containers.list(all=True,
                                                        filters={'since': ETCD_CONTAINER, 'status': 'running',
                                                                 'label': 'mount=snapshot'})
                if len(container_list) > 0:
                    LogMessage("==========> Performing unmount operation for snapshot: %s <==========" % \
                               container_list[0].labels['snapshot'] )
                    performed_action = dcv.unmount_snapshot(container_list[0])
                    if performed_action:
                        LogMessage("************Successfully completed %s operation.************" % action,1,action)

            elif action == "delete_snapshot":
                snapshots = client.volumes.list(filters={'dangling': True, 'driver':HPE3PAR,
                                                         'label': 'type=snapshot' })
                dangling_snapshots = len(snapshots)
                if dangling_snapshots > 0:
                    random_snapshot = snapshots[random.randint(0, (dangling_snapshots-1))]
                    LogMessage("==========>Performing delete operation on volume: %s <==========" % random_snapshot.name)
                    performed_action = dcv.delete_snapshot(random_snapshot)
                    if performed_action:
                        LogMessage("************Successfully completed %s operation.************" % action,1,action)

            else:
                LogError("Unknown test action '%s'" % action)
                break

        except TestError as e:
            LogError(str(e), 1, action)
            continue
        except docker.errors.APIError as ar:
            LogError(str(ar), 1, action)
            continue
        except docker.errors.NotFound as nf:
            LogError(str(nf), 1, action)
            continue
        except:
            LogError("%s operation failed due to unexpected error."% action, 1, action)
            continue

    # cleaning up containers and volumes
    LogMessage("cleanup...")

    container_list = client.containers.list(all=True, filters = {'since':ETCD_CONTAINER})
    if len(container_list) > 0:
        for container in container_list:
            try:
                container.stop()
                assert container.wait()['StatusCode'] == 0 or 137
                performed_action = container.remove()
                if performed_action:
                    LogMessage("************Successfully removed container in clean up.************")
            except docker.errors.APIError as ar:
                LogMessage(str(ar))
                continue
            except TestError as e:
                LogError(str(e))
                continue
            except Exception as e:
                LogError(str(e))
                continue

    snapshot_list = client.volumes.list(filters={'label': 'type=snapshot' })
    if len(snapshot_list) > 0:
        for snapshot in snapshot_list:
            try:
                performed_action = dcv.delete_snapshot(snapshot)
            except TestError as e:
                LogError(str(e))
                continue
            except docker.errors.APIError as ar:
                LogError(str(ar))
                continue
            except Exception as e:
                LogError(str(e))
                continue

    volume_list = client.volumes.list()
    if len(volume_list) > 0:
        for volume in volume_list:
            try:
                performed_action = dcv.delete_volume(volume)
            except TestError as e:
                LogError(str(e))
                continue
            except docker.errors.APIError as ar:
                LogError(str(ar))
                continue
            except Exception as e:
                LogError(str(e))
                continue

except TestError as e:
    LogError(str(e))
    LogError("Aborting test.  Too frightened to continue.", 0)


############################################
LogMessage("==================================================================")
TestFinished()
LogMessage("FINISHED")
