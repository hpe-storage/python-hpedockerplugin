# Active/Passive Based Replication #

In Active/Passive based replication, only one array is in active state 
at any point of time serving the VLUNs of a given replicated volume.

When a remote copy group (RCG) is failed over manually via 3PAR CLI to the
secondary array, the secondary array becomes active. However, the VLUNs
of the failed over volumes are still not exported by the secondary array
to the host. In order to trigger that, the container/POD running on the 
host needs to be restarted.

## Configuring replication enabled backend
**For FC Host** 
```sh
host_etcd_port_number=<ETCD_PORT_NUMBER>
hpe3par_username=<Source-3PAR-Username>
hpe3par_password=<Source-3PAR-Password>
hpe3par_cpg=<Source-User-CPG>
hpedockerplugin_driver=hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver
logging=DEBUG
san_ip=<Source-3PAR-SAN-IP>
san_login=<Source-3PAR-SAN-Username>
san_password=<Source-3PAR-SAN-Password>
host_etcd_ip_address=<IP1>[:PORT1[,IP2[:PORT2]][,IP3[:PORT3]]...]
hpe3par_api_url=https://<Source-Array-IP>:8080/api/v1
replication_device = backend_id:<Target-Array-Hostname>,
                     replication_mode:<synchronous | asynchronous | streaming>,
                     cpg_map:<Source-User-CPG>:<Target-User-CPG>,
                     snap_cpg_map:<Source-Snap-CPG>:<Target-Snap-CPG>
                     hpe3par_api_url:https://<Target-Array-IP>:8080/api/v1,
                     hpe3par_username:<3PAR-Username>,
                     hpe3par_password:<3PAR-Password>,
                     san_ip:<3PAR-SAN-IP>,
                     san_login:<3PAR-SAN-Username>,
                     san_password:<3PAR-SAN-Password>
```

*Note*:

1. In case of asynchronous replication mode, *sync_period* field can optionally be 
defined as part of *replication_device* entry and it should be between range 300 
and 31622400 seconds. If not defined, it defaults to 900 seconds.
2. Both *cpg_map* and *snap_cpg_map* in *replication_device* section are mandatory.
3. If password is encrypted for primary array, it must be encrypted for secondary array
as well using the same *pass-phrase*


**For ISCSI Host** 
```sh
host_etcd_port_number=<ETCD_PORT_NUMBER>
hpe3par_username=<Source-3PAR-Username>
hpe3par_password=<Source-3PAR-Password>
hpe3par_cpg=<Source-User-CPG>
hpedockerplugin_driver=hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver
logging=DEBUG
san_ip=<Source-3PAR-SAN-IP>
san_login=<Source-3PAR-SAN-Username>
san_password=<Source-3PAR-SAN-Password>
host_etcd_ip_address=<IP1>[:PORT1[,IP2[:PORT2]][,IP3[:PORT3]]...]
hpe3par_api_url=https://<Source-Array-IP>:8080/api/v1
hpe3par_iscsi_ips=<ISCSI_IP1>[,ISCSI_IP2,ISCSI_IP3...]
replication_device=backend_id:<Source-Array-Host-Name>,
replication_device = backend_id:<Target-Array-Name>,
                     replication_mode:<synchronous | asynchronous | streaming>,
                     cpg_map:<Source-User-CPG>:<Target-User-CPG>,
                     snap_cpg_map:<Source-Snap-CPG>:<Target-Snap-CPG>
                     hpe3par_api_url:https://<Target-Array-IP>:8080/api/v1,
                     hpe3par_username:<3PAR-Username>,
                     hpe3par_password:<3PAR-Password>,
                     san_ip:<3PAR-SAN-IP>,
                     san_login:<3PAR-SAN-Username>,
                     san_password:<3PAR-SAN-Password>
                     hpe3par_iscsi_ips=<ISCSI_IP1>[;ISCSI_IP2;ISCSI_IP3...]
```
*Note*:

1. Both *cpg_map* and *snap_cpg_map* in *replication_device* section are mandatory.
2. *hpe3par_iscsi_ips* MUST be defined upfront for both source and target arrays.
3. *hpe3par_iscsi_ips* can be a single ISCSI IP or a list of ISCSI IPs delimited by 
semi-colon. Delimiter for this field is applicable for *replication_device* section ONLY.
4. If password is encrypted for primary array, it MUST be encrypted for secondary array
as well using the same *pass-phrase*.
5. In case of asynchronous replication mode, *sync_period* field can optionally be
defined as part of *replication_device* entry and it should be between range 300 
and 31622400 seconds. If not defined, it defaults to 900 seconds.


## Managing Replicated Volumes ###
### Create replicated volume ###
This command allows creation of replicated volume along with RCG creation if the RCG
does not exist on the array. Newly created volume is then added to the RCG.
Existing RCG name can be used to add multiple newly created volumes to it.
```sh
$ docker volume create -d hpe --name <volume_name> -o replicationGroup=<3PAR_RCG_Name> [Options...]
```
where,
- *replicationGroup*: Name of a new or existing replication copy group on 3PAR array

One or more following *Options* can be specified additionally:
1. *size:* Size of volume in GBs
2. *provisioning:* Provision type of a volume to be created.
Valid values are thin, dedup, full with thin as default.
3. *backend:* Name of the backend to be used for creation of the volume. If not 
specified, "DEFAULT" is used providied it is initialized successfully.
4. *mountConflictDelay:* Waiting period in seconds to be used during mount operation
of the volume being created. This happens when this volume is mounted on say Node1 and
Node2 wants to mount it. In such a case, Node2 will wait for *mountConflictDelay* 
seconds for Node1 to unmount the volume. If even after this wait, Node1 doesn't unmount
the volume, then Node2 forcefully removes VLUNs exported to Node1 and the goes ahead 
with the mount process.
5. *compression:* This flag specifies if the volume is a compressed volume. Allowed 
values are *True* and *False*.

#### Example ####

**Create a replicated volume having size 1GB with a non-existing RCG using backend "ActivePassiceRepBackend"**
```sh
$ docker volume create -d hpe --name Test_RCG_Vol -o replicationGroup=Test_RCG -o size=1 -o backend=ActivePassiceRepBackend 
```
This will create volume Test_RCG_Vol along with TEST_RCG remote copy group. The volume
will then be added to the TEST_RCG.
Please note that in case of failure during the operation at any stage, previous actions
are rolled back.
E.g. if for some reason, volume Test_RCG_Vol could not be added to Test_RCG, the volume
is removed from the array.


### Failover a remote copy group ###

There is no single Docker command or option to support failover of a RCG. Instead, following 
steps must be carried out in order to do it:
1. On the host, the container using the replicated volume must be stopped or exited if it is running. 
This triggers unmount of the volume(s) from the primary array.

2. On the primary array, stop the remote copy group manually:
```sh
$ stoprcopygroup <RCG_Name>
```

3. On the secondary array, execute *failover* command:
```sh
$ setrcopygroup failover <RCG_Name_On_Secondary_Array>
```

4. Restart the container. This time the VLUNs would be served by the failed-over or secondary array

### Failback workflow for Active/Passive based replication ###
There is no single Docker command or option to support failback of a RCG. Instead, 
following steps must be carried out in order to do it:
1. On the host, the container using the replicated volume must be stopped or exited if it is running.
This triggers unmount of the volume(s) from the failed-over or secondary array.

2. On the secondary array, execute *recover* and *restore* commands:
```sh
$ setrcopygroup recover <RCG_Name_On_Secondary_Array>
$ setrcopygroup restore <RCG_Name_On_Secondary_Array>
```

3. Restart the container so that the primary array exports VLUNs to the host this time.


### Delete replicated volume ###
```sh
$ docker volume rm <volume_name>
```
This command allows the user to delete a replicated volume. If this was the last 
volume present in RCG then the RCG is also removed from the backend.


**See also:**
[Peer Persistence Based Replication](peer-persistence-based-replication.md)