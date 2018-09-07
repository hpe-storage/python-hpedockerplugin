## Usage of the 3PAR Volume Plug-in for Docker

The following guide covers many of the options used for provisioning volumes and volume management within standalone Docker environments as well as Kubernetes/OpenShift environments.

### Sections

* [Using 3PAR Volume Plug-in with Docker](#docker_usage)
  * [Create a basic HPE 3PAR volume](#basic)
  * [Volume optional parameters](#options)
  * [Deleting a Volume](#delete)
  * [List Volumes](#list)
  * [Inspect a Volume](#inspect)
  * [Mounting a Volume](#mount)
  * [Unmounting a Volume](#unmount)
  * [Creating a Volume with QoS rules](#qos)
  * [Cloning a Volume](#clone)
  * [Enabling compression on Volume](#compression)



* [Using 3PAR Volume Plug-in with Kubernetes/OpenShift](#k8_usage)



## Within Docker<a name="docker_usage"></a>
The following are the currently supported actions that can be taken using the HPE 3PAR Volume Plug-in for Docker.

### Creating a basic HPE 3PAR volume<a name="basic"></a>
```
sudo docker volume create -d hpe --name <vol_name>
```

### HPE 3PAR Docker Volume parameters<a name="options"></a>
The **HPE 3PAR Docker Volume Plug-in** supports several optional parameters that can be used during volume creation:

- **size** -- specifies the desired size in GB of the volume. If size is not specified during volume creation , it defaults to 100 GB.

- **provisioning** -- specifies the type of provisioning to use (thin, full, dedup). If provisioning is not specified during volume creation, it defaults to thin provisioning. For dedup provisioning, CPG with SSD device type must be configured.

- **flash-cache** -- specifies whether flash cache should be used or not (True, False).

- **compression** -- enables or disabled compression on the volume which is being created. It is only supported for thin/dedup volumes 16 GB in size or larger.
  * Valid values for compression are (true, false) or (True, False).
  * Compression is only supported on 3par OS version 3.3.1 (**introduced in plugin version 2.1**)


- **mountConflictDelay** -- specifies period in seconds to wait for a mounted volume to gracefully unmount from a node before it can be mounted to another. If graceful unmount doesn't happen within the specified time then a forced cleanup of the VLUN is performed so that volume can be remounted to another node.(**introduced in plugin version 2.1**)

- **qos-name** -- name of existing VVset on the HPE 3PAR where QoS rules are applied.(**introduced in plugin version 2.1**)

>Note: Setting flash-cache to True does not gurantee flash-cache will be used. The backend system
must have the appropriate SSD setup configured too.

The following is an example Docker command creating a full provisioned, 50 GB volume:
```
docker volume create -d hpe --name <vol_name> -o size=50 -o provisioning=full
```

### Deleting a volume<a name="delete"></a>
```
docker volume rm <vol_name>
```

### List volumes<a name="list"></a>
```
docker volume ls
```

### Inspect a volume<a name="inspect"></a>
```
docker volume inspect <vol_name>
```

### Mounting a volume<a name="mount"></a>
Use the following command to mount a volume and start a bash prompt:
```
docker run -it -v <vol_name>:/<mount_point>/ --volume-driver hpe <image_name> bash
```

On Docker 17.06 or later, run below command:
```
docker run -it --mount type=volume,src=<VOLUME-NAME>,dst=<CONTAINER-PATH>,volume-driver=<DRIVER>,volume-opt=<KEY0>=<VALUE0>,volume-opt=<KEY1>=<VALUE1> --name mycontainer <IMAGE>
```

>Note: If the volume does not exist it will be created.

The image used for mounting can be any image located on https://hub.docker.com/ or
the local filesystem. See https://docs.docker.com/v1.8/userguide/dockerimages/
for more details.

### Unmounting a volume<a name="unmount"></a>
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

### Creating a volume with an existing VVset and QoS rules (**introduced in plugin version 2.1**)<a name="qos"></a>
```
docker volume create -d hpe --name <target_vol_name> -o qos-name=<vvset_name>
```
>**Note** The VVset defined in **vvset_name** MUST exist in the HPE 3PAR and have QoS rules applied.

### Creating a clone of a volume (**introduced in plugin version 2.1**)<a name="clone"></a>
```
docker volume create -d hpe --name <target_vol_name> -o cloneOf=<source_vol_name>
```
### Creating compressed volume (**introduced in plugin version 2.1**)<a name="compression"></a>
```
docker volume create -d hpe --name <target_vol_name> -o compression=true
```

### Creating a snapshot or virtualcopy of a volume (**introduced in plugin version 2.1**)<a name="snapshot"></a>
```
docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=<source_vol_name>
```
**Snapshot optional parameters**
- **expirationHours** -- specifies the expiration time for a snapshot in hours and will be automatically deleted from the 3PAR once the time defined in **expirationHours** expires.

- **retentionHours**  -- specifies the retention time a snapshot in hours. The snapshot will not be able to be deleted from the 3PAR until the number of hours defined in **retentionHours** have expired.

>**Note:**
>* If **snapcpg** is not configured in `hpe.conf` then the **cpg** defined in `hpe.conf` will be used for snapshot creation.
>
>* If both **expirationHours** and **retentionHours** are used while creating a snapshot then **retentionHours** should be *less* than **expirationHours**

```
docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=<source_vol_name> -o expirationHours=3
```


>**Note:** To mount a snapshot, you can use the same commands as [mounting a volume](#mount) as specified above.
