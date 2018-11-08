## Usage
The following are the currently supported actions that can be taken using the HPE Docker plugin.

#### Creating an HPE volume

```
docker volume create -d hpe --name <vol_name>
```

There are several optional parameters that can be used during volume creation:

- size -- specifies the desired size in GB of the volume.
- cpg -- specifes the cpg for a volume.
- snpcpg -- specifies the snap cpg for a volume.
- provisioning -- specifies the type of provisioning to use (thin, full, dedup).
- flash-cache -- specifies whether flash cache should be used or not (True, False).
- fsMode -- Represent the file mode to be applied to the root directory of the filesystem, in the form of octall digits.
- fsOwner -- Represent user id and group id that should own the root directory of the filesystem,
in the form of [userId:groupId]
- mountConflictDelay -- specifies period in seconds. This parameter is used to wait for a
mounted volume to gracefully unmount from some node before it can be mounted on the current
node. If graceful unmount doesn't happen within mountConflictDelay seconds then a forced
cleanup of VLUN from the backend is performed so that volume can be mounted on the current
node.
Note: Setting flash-cache to True does not gurantee flash-cache will be used. The backend system
must have the appropriate SSD setup configured, too.

The following is an example call creating a full provisioned, 50 GB volume:

```
docker volume create -d hpe --name <vol_name> -o size=50 -o provisioning=full
```

Note -- The dedup provisioning and flash-cache options are only supported by the
3PAR StoreServ driver currently.


#### Creating a volume using cpg and snapcpg

```
docker volume create -d hpe --name <target_vol_name> -o cpg=<cpg_name> -o snapcpg=<snapcpg_name>
```
Note -- 'cpg & snapcpg' should be present in 3par


#### Creating a volume using existing QOS

```
docker volume create -d hpe --name <target_vol_name> -o qos-name=<vvset_name>
```
Note -- 'vvset_name' should be present in 3par

#### Managing a legacy volume & snapshot

```
docker volume create -d hpe --name <target_vol_name> -o importVol=<3par_volume|3par_snapshot>
```

#### Displaying help

```
docker volume create -d hpe -o help
```

#### Displaying available backends with their status

```
docker volume create -d hpe -o help=backends
```

#### Deleting a volume

```
docker volume rm <vol_name>
```

#### List volumes

```
docker volume ls
```

#### Inspect a volume

```
docker volume inspect <vol_name>
```

#### Creating a clone of a volume

```
docker volume create -d hpe --name <target_vol_name> -o cloneOf=<source_vol_name>
```
#### Creating compressed volume

```
docker volume create -d hpe --name <target_vol_name> -o compression=true
```


#### Creating a snapshot or virtualcopy of a volume

```
docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=<source_vol_name>
```
There are couple of optional parameters that can be used during snapshot creation:
- expirationHours -- specifies the expiration time for snapshot in hours
- retentionHours  -- specifies the retention time for snapshot in hours

Note:1. If snapcpg is not configured in hpe.conf then cpg would be used for snapshot.
     2. expirationHours and retentionHours are valid attributes of a volume but 2.1
        plugin ignores these parameters and are valid only for snapshots currently.

#### Inspect a snapshot

```
docker volume inspect <snapshot_name>
```

#### Delete a snapshot

```
docker volume rm <snapshot_name>
```

#### Mounting a volume/snapshot

Use the following command to mount a volume and start a bash prompt:

```
docker run -it -v <vol_name>:/<mount_point>/ --volume-driver hpe <image_name> bash
```

<vol_name> here can be both snapshot (or) a base volume created by the plugin.

Note:
1. If the volume does not exist it will be created.
2. Volume created through this command will always be via backend 'DEFAULT'.
3. If the backend 'DEFAULT' is replication enabled and volume doesn't exist, this command will not succeed
   Hence it is highly recommended that 'DEFAULT' backend is not replication enabled.

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
docker ps -a
```

Then stop the container:

```
docker stop <container_id>
```

Next, delete the container:

```
docker rm <container_id>
```

Finally, remove the volume:

```
docker volume rm <vol_name>
```

Note: Same approch similar to volume mount is used for mounting a snapshot to a container.

#### Providing File Permission and File Owner to a Volume.

Use the below command to give ownership to a non-root user by providing UID and GID.
````
docker volume create -d hpe --name <vol_name> -o size=<vol_size> -o fsOwner=<userID:groupId>
````

Use the below command to change the mode.
````
docker volume create -d hpe --name <vol_name> -o size=<vol_size> -o fsMode=<file_mode>
````
<file_mode> is 1 to 4 octal digits that represent the file mode to be applied.
