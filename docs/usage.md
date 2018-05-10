## Usage
The following are the currently supported actions that can be taken using the HPE 3PAR Volume Plug-in for Docker.

#### Creating a volume
```
sudo docker volume create -d hpe --name <vol_name>
```

There are several optional parameters that can be used during volume creation:

- size -- It specifies the desired size in GB of the volume. If size is not specified during volume creation , it defaults to 100 GB.
- provisioning -- It specifies the type of provisioning to use (thin, full, dedup). If provisioning is not specified during volume creation, it defaults to thin provisioning. For dedup provisioning, CPG with SSD device type must be configured.
- flash-cache -- It specifies whether flash cache should be used or not (True, False).
- compression -- It enables or disabled compression on volume which is being created. It is only supported for thin/dedup volumes of size greater or equal to 16 GB. Valid values for compression are (true, false) or (True, False). Compression is only supported on 3par OS version 3.3.1 (**introduced in plugin version 2.1**)
- mountConflictDelay -- specifies period in seconds. This parameter is used to wait for a
mounted volume to gracefully unmount from some node before it can be mounted on the current
node. If graceful unmount doesn't happen within mountConflictDelay seconds then a forced
cleanup of VLUN from the backend is performed so that volume can be mounted on the current
node.(**introduced in plugin version 2.1**)
- qos_name -- name of existing VVset on 3PAR where QoS rules are applied.(**introduced in plugin version 2.1**)

Note: Setting flash-cache to True does not gurantee flash-cache will be used. The backend system
must have the appropriate SSD setup configured too.

The following is an example call creating a full provisioned, 50 GB volume:
```
sudo docker volume create -d hpe --name <vol_name> -o size=50 -o provisioning=full
```

#### Deleting a volume
```
sudo docker volume rm <vol_name>
```

#### List volumes
```
sudo docker volume ls
```

#### Inspect a volume
```
sudo docker volume inspect <vol_name>
```

#### Mounting a volume
Use the following command to mount a volume and start a bash prompt:
```
sudo docker run -it -v <vol_name>:/<mount_point>/ --volume-driver hpe <image_name> bash
```

On Docker 17.06 or later, run below command:
```
sudo docker run -it --mount type=volume,src=<VOLUME-NAME>,dst=<CONTAINER-PATH>,volume-driver=<DRIVER>,volume-opt=<KEY0>=<VALUE0>,volume-opt=<KEY1>=<VALUE1> --name mycontainer <IMAGE>
```

Note: If the volume does not exist it will be created.

The image used for mounting can be any image located on https://hub.docker.com/ or
the local filesystem. See https://docs.docker.com/v1.8/userguide/dockerimages/
for more details. 

#### Unmounting a volume
Exiting the bash prompt will cause the volume to unmount:
```
exit
```

The volume is still associated with a container at this point.

Run the following command to get the container ID associated with the volume:
```
sudo docker ps -a
```

Then stop the container:
```
sudo docker stop <container_id>
```

Next, delete the container:
```
sudo docker rm <container_id>
```

Finally, remove the volume:
```
sudo docker volume rm <vol_name>
```

#### Creating a volume with existing vvset associated with QoS rules(**introduced in plugin version 2.1**)
```
docker volume create -d hpe --name <target_vol_name> -o qos-name=<vvset_name>
```
Note -- 'vvset_name' should be present in 3par and should have QoS rules set to it.

#### Creating a clone of a volume(**introduced in plugin version 2.1**)
```
docker volume create -d hpe --name <target_vol_name> -o cloneOf=<source_vol_name>
```
#### Creating compressed volume(**introduced in plugin version 2.1**)
```
docker volume create -d hpe --name <target_vol_name> -o compression=true
```

#### Creating a snapshot or virtualcopy of a volume(**introduced in plugin version 2.1**)
```
docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=<source_vol_name>
```
There are couple of optional parameters that can be used during snapshot creation:
- expirationHours -- specifies the expiration time for snapshot in hours
- retentionHours  -- specifies the retention time for snapshot in hours

Note:1. If snapcpg is not configured in hpe.conf then cpg would be used for snapshot.
     2. expirationHours and retentionHours are valid attributes of a volume but 2.1
        plugin ignores these parameters and are valid only for snapshots currently.

```
docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=<source_vol_name> -o expirationHours=3
```
Note:

- When snapshot is created with expirationHours, snapshot is automatically deleted from 3PAR once expirationHours are over. When user does docker volume inspect on parent volume after expiration hours of snapshot, this will list the only those snapshots which are not expired.
- When snapshot is created with retentionHours, user cannot delete snashot until the retentionHours are over. If both expirationHours and retentionHours are used while creating snapshot then retentionHours should be less than expirationHours
        
```
Note: Same approch similar to volume mount is used for mounting a snapshot to a container.
```
