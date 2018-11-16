# Peer Persistence based replication #
Peer Persistence feature of 3PAR provides a non-disruptive disaster recovery solution wherein in
case of disaster, the hosts automatically and seamlessly get connected to the secondary
array and start seeing the VLUNs which were earlier exported by the failed array.

With Peer Persistence, when a Docker user mounts a replicated volume(s), HPE 3PAR Docker
Plugin creates VLUNs corresponding to the replicated volume(s) on BOTH
the arrays. However, they are served only by the active array with the other array being on
standby mode. When the corresponding RCG is switched over or primary array goes down, 
the secondary array takes over and makes the VLUN(s) available. After swithover, the 
active array goes in standby mode while the other array becomes active.

**Pre-requisites**
1. Remote copy setup is up and running
2. Quorum Witness is running with primary and secondary arrays registered with it
3. Multipath daemon is running so that non-disruptive seamless mounting of VLUN(s)
on the host is possible.


## Configuring replication enabled backend
Compared to Active/Passive configuration, in Peer Persistence, the ONLY discriminator
is the presence of *quorum_witness_ip* sub-field under *replication_device* field - 
rest of the fields are applicable.

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
replication_device = backend_id:<Target-Array-Name>,
                     quorum_witness_ip:<Quorum-Witness-IP>,
                     replication_mode:synchronous,
                     cpg_map:<Source-User-CPG>:<Target-User-CPG>,
                     snap_cpg_map:<Source-Snap-CPG>:<Target-Snap-CPG>
                     hpe3par_api_url:https://<Target-Array-IP>:8080/api/v1,
                     hpe3par_username:<3PAR-Username>,
                     hpe3par_password:<3PAR-Password>,
                     san_ip:<3PAR-SAN-IP>,
                     san_login:<3PAR-SAN-Username>,
                     san_password:<3PAR-SAN-Password>
```

**Note:**

1. *replication_mode* MUST be set to *synchronous* as a pre-requisite for Peer 
Persistence based replication.
2. Both *cpg_map* and *snap_cpg_map* in *replication_device* section are mandatory
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
                     quorum_witness_ip:<Quorum-Witness-IP>,
                     replication_mode:synchronous,
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
4. If password is encrypted for primary array, it must be encrypted for secondary array
as well using the same *pass-phrase*
5. *replication_mode* MUST be set to *synchronous* as a pre-requisite for Peer 
Persistence based replication.

## Managing Replicated Volumes ###

### Create replicated volume ###
This command allows creation of replicated volume along with RCG creation if the RCG
does not exist on the array. Newly created volume is then added to the RCG.
Existing RCG name can be used to add multiple newly created volumes to it.
```sh
docker volume create -d hpe --name <volume_name> -o replicationGroup=<3PAR_RCG_Name> [Options...]
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


### Switchover a remote copy group ###
There is no single Docker command or option to support switchover of a RCG from one 
array to the other. Instead, following 3PAR command must be executed.

```sh
$ setrcopygroup switchover <RCG_Name>
```
where:
- *RCG_Name* is the name of remote copy group on the array where the above command is executed.

Having done the switchover, multipath daemon takes care of seamless mounting of volume(s) from the
switched over array.

### Delete replicated volume ###
This command allows user to delete a replicated volume. If this is the last volume 
present in RCG then the RCG is also removed from the backend.
```sh
docker volume rm <volume_name>
```

**See also:**
[Active/Passive Based Replication](active-passive-based-replication.md)