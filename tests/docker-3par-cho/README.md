## HPE 3PAR Docker Volume Plugin- Continuous Hours (CHO) Testing

### Overview
This document details the steps necessary to perform a Reliability testing or we can say Continuous Hours of Operation (aka CHO) tests against HPE 3PAR Docker Volume Plugin. This testing allows us to verify that no bugs creep up after lengthy use of those components of volume plugin.

### Setup
Setup Docker Engine environment normally.

Install Docker SDK using "pip install docker" command.

Install and enable the HPE 3PAR Docker Volume plugin

```
Pull tests from Git
git clone https://github.com/hpe-storage/python-hpedockerplugin -b test_automation
cd python-hpedockerplugin/tests/docker-3par-cho/
```
 
### Run tests
A single CLI command is used to trigger the testing. This command must include the appropriate parameters to be used for testing along with the duration of the test. By default the test will ask for the pertinent information, but it's best to have it all in the command line for convenience.

```
$ python hpe_3par_cho_test.py -duration <time in minutes> -maxVolumes <number> -plugin <plugin> -maxVolumeSize <number> -provisioning <provisioning type> -etcd <etcd container> -logfile <path for logs>
```
 
### Some notes about the command:
duration: It is in minutes. Standard duration is 96 hours or 5760 minutes. Defaults to 1 minute.

maxVolumes: It is the maximum number of volumes that will be active at any one time during the test run.  Defaults to 8.

maxVolumeSize: It is the maximum size of volume. Defaults to 10 GB.

logfile: It is recommend to create a unique log file for each run. Defaults to "./DockerChoTest-<time>.log"

plugin: Plugin name must be the plugin repository name which is in enabled state. Defaults to "hpe"

etcd: It must be the etcd container name which is in running state. Defaults to "etcd"

provisioning: proviosioning type must be thin, full or dedup. Defaults to "thin"

cpg: As part of multiCPG feature, user can specify the CPG which he/she wants to set as CPG for hpe plugin. (Default value of CPG is picked up from hpe.conf)

backend: If user wants to use multiArray feature, he/she can specify the BACKEND name which is already set in hpe.conf. (Default backend is set under "DEFAULT" section in hpe.conf)
