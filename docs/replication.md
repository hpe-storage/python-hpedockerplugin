# Replication #
Replication of Docker volumes is supported for two types:
1. Active/Passive based replication
2. Peer Persistence based replication

Core to the idea of replication is the concept of remote copy group (RCG) that aggregates all the volumes that
need to be replicated simultaneously.

## Active/Passive based replication ##
In Active/Passive based replication, VLUNs corresponding to the replicated volumes are served by active array
only - no VLUNs for these volumes exist on secondary array at this time. When a RCG is failed over manually
to secondary array, the secondary array becomes active and start serving these VLUNs the host(s). In this case,
any container that had the volume(s) mounted would need to be restarted for it to be able to use the volume(s)
being served from secondary array post-failover.

Following configuration entry needs to be added to hpe.conf for it to be called active/passive based replication:

replication_device = backend_id:<Array-Name>,
                     replication_mode:<synchronous|asynchronous|streaming>,
                     cpg_map:<Source-CPG>:<Target-CPG>,
                     snap_cpg_map:<Source-Snap-CPG>:<Target-Snap-CPG>
                     hpe3par_api_url:https://<IP>:8080/api/v1,
                     hpe3par_username:<3PAR-Username>,
                     hpe3par_password:<3PAR-Password>,
                     san_ip:<IP>,
                     san_login:<3PAR-SAN-Username>,
                     san_password:<3PAR-SAN-Password>

In case of asynchronous replication mode, ‘sync_period’ must be defined between range 300 and 31622400 seconds.
If not defined, it defaults to 900.

If this is for ISCSI based protocol, and if there are multiple ISCSI IP addresses, the hpe_iscsi_address must be
assigned ISCSI IP addresses delimited by semi-colon. This is applicable for replication_device section ONLY.


### Creation of replicated volume ###
docker volume create -d hpe --name <volume_name> -o replicationGroup=<3PAR_RCG_Name> [Options...]

For replication, new option "replicationGroup" has been added. This denotes 3PAR Remote Copy Group.
In case RCG doesn't exist on the array, it gets created

### Failover workflow for Active/Passive based replication ###
Following steps must be carried out in order to do failover:
1. On host, the container using the replicated volume must be stopped or exited if it is running so that volume
is unmounted from the primary array.

2. Perform manual failover on the secondary array using the below command:
setrcopygroup failover <RCG_Name_On_Secondary_Array>
setrcopygroup recover <RCG_Name_On_Secondary_Array>

3. Restart the container so that volume that is served by failed over array is mounted this time

### Failback workflow for Active/Passive based replication ###
Following steps must be carried out in order to do failover:
1. On host, the container using the replicated volume must be stopped or exited if it is running so that volume
is unmounted from the secondary array.

2. Perform manual restore on the secondary array
setrcopygroup restore <RCG_Name_On_Secondary_Array>

3. Restart the container so that volume that is served by primary array is mounted this time


## Peer Persistence based replication ##
In case of Peer Persistence based replication, VLUNs corresponding to the replicated volumes are created on BOTH
the arrays but served only by the primary array. When RCG is switched over or primary array goes down, the
secondary array starts serving the VLUNs.

Following configuration entry needs to be added to hpe.conf for it to be called Peer Persistence based replication:

replication_device = backend_id:<Array-Name>,
                     quorum_witness_ip:<IP>,
                     replication_mode:synchronous,
                     cpg_map:<Source-CPG>:<Target-CPG>,
                     snap_cpg_map:<Source-Snap-CPG>:<Target-Snap-CPG>
                     hpe3par_api_url:https://<IP>:8080/api/v1,
                     hpe3par_username:<3PAR-Username>,
                     hpe3par_password:<3PAR-Password>,
                     san_ip:<IP>,
                     san_login:<3PAR-SAN-Username>,
                     san_password:<3PAR-SAN-Password>

Presence of "quorum_witness_ip" field makes it a Peer Persistence based replication configuration.
"replication_mode" MUST be set to "synchronous" as a pre-requisite for Peer Persistence based replication.

### Manual switchover workflow for Peer Persistence based replication ###
Following command must be executed on primary array in order to do switchover:
setrcopygroup switchover <RCG_Name_On_Secondary_Array>

### Delete replicated volume ###
docker volume rm <volume_name>

This deletes the volume. If this was the last volume present in RCG then the RCG is also removed from the backend.