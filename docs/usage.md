## Usage of the HPE 3PAR Volume Plug-in for Docker

The following guide covers many of the options used for provisioning volumes and volume management within standalone Docker environments as well as Kubernetes/OpenShift environments.

* ### [Using HPE 3PAR Volume Plug-in with Docker](#docker_usage)
  * [Creating a basic HPE 3PAR volume](#basic)
  * [Volume optional parameters](#options)
  * [Creating replicated volume](#replication)
  * [Deleting a volume](#delete)
  * [Listing volumes](#list)
  * [Inspecting a volume](#inspect)
  * [Mounting a volume](#mount)
  * [Unmounting a volume](#unmount)
  * [Creating a volume with QoS rules](#qos)
  * [Cloning a volume](#clone)
  * [Enabling compression on volume](#compression)
  * [Enabling file permissions and ownership](#file-permission-owner)
  * [Managing volumes using multiple backends](#multi-array-feature)
  

* ### [Using HPE 3PAR Volume Plug-in with Kubernetes/OpenShift](#k8_usage)
  * [Kubernetes/OpenShift Terms](#terms)
  * [StorageClass Example](#sc)
    * [StorageClass options](#sc_parameters)
  * [Persistent Volume Claim Example](#pvc)
  * [Pod Example](#pod)
  * [Restarting the Containerized HPE 3PAR Volume Plug-in](#restart)

---


## Within Docker<a name="docker_usage"></a>
The following section covers the supported actions for the **HPE 3PAR Volume Plug-in** within a **Docker** environment.

  * [Creating a basic HPE 3PAR volume](#basic)
  * [Volume optional parameters](#options)
  * [Creating replicated volume](#replication)
  * [Deleting a volume](#delete)
  * [Listing volumes](#list)
  * [Inspecting a volume](#inspect)
  * [Mounting a volume](#mount)
  * [Unmounting a volume](#unmount)
  * [Creating a volume with QoS rules](#qos)
  * [Cloning a volume](#clone)
  * [Enabling compression on volume](#compression)
  * [Enabling file permissions and ownership](#file-permission-owner)
  * [Managing volumes using multiple backends](#multi-array-feature)
  * [Creating a snapshot or virtual-copy of a volume](#snapshot)
  * [Creating HPE 3PAR snapshot schedule](#snapshot_schedule)
  * [Display help on usage](#usage-help)
  * [Display available backends and their status](#backends-status)
  * [Importing legacy volumes as docker volumes](#import-vol)

If you are using **Kubernetes** or **OpenShift**, please go the [Kubernetes/OpenShift Usage section](#k8_usage).

### Creating a basic HPE 3PAR volume<a name="basic"></a>
```
$ sudo docker volume create -d hpe --name <vol_name>
```

### HPE 3PAR Docker Volume parameters<a name="options"></a>
The **HPE 3PAR Docker Volume Plug-in** supports several optional parameters that can be used during volume creation:

- **size** -- specifies the desired size in GB of the volume. If size is not specified during volume creation, it defaults to 100 GB.

- **provisioning** -- specifies the type of provisioning to use (thin, full, dedup). If provisioning is not specified during volume creation, it defaults to thin provisioning. For dedup provisioning, CPG with SSD device type must be configured.

- **flash-cache** -- specifies whether flash cache should be used or not (True, False).

- **compression** -- enables or disabled compression on the volume which is being created. It is only supported for thin/dedup volumes 16 GB in size or larger.
  * Valid values for compression are (true, false) or (True, False).
  * Compression is only supported on 3par OS version 3.3.1. (**introduced in plugin version 2.1**)

- **mountConflictDelay** -- specifies period in seconds to wait for a mounted volume to gracefully unmount from a node before it can be mounted to another. If graceful unmount doesn't happen within the specified time then a forced cleanup of the VLUN is performed so that volume can be remounted to another node. (**introduced in plugin version 2.1**)

- **qos-name** -- name of existing VVset on the HPE 3PAR where QoS rules are applied. (**introduced in plugin version 2.1**)

- **cpg** -- name of user CPG to be used in the operation instead of the one specified in hpe.conf. (**introduced in plugin version 3.0**)

- **snapcpg** -- name of snapshot CPG to be used in the operation instead of the one specified in hpe.conf. (**introduced in plugin version 3.0**)

  In case, *snapcpg* option is not explicitly specified, then:
  * Snapshot CPG takes the value of *hpe3par_snapcpg* from 'hpe.conf' if specified.
  * If *hpe3par_snapcpg* is not specified in 'hpe.conf', then snapshot CPG takes the 
    value of optional parameter *cpg*.
  * If both *hpe3par_snapcpg* and *cpg* are not specified, then snapshot CPG takes the value
    of *hpe3par_cpg* specified in 'hpe.conf'.

- **replicationGroup** -- name of an existing remote copy group on the HPE 3PAR. (**introduced in plugin version 3.0**)

- **fsOwner** -- user ID and group ID that should own root directory of file system. (**introduced in plugin version 3.0**)

- **fsMode** -- mode of the root directory of file system to be specified as octal number. (**introduced in plugin version 3.0**)

- **backend** -- backend to be used for the volume creation. (**introduced in plugin version 3.0**)

- **help** -- displays usage help and backend initialization status. (**introduced in plugin version 3.0**)


>Note: Setting flash-cache to True does not guarantee flash-cache will be used. The backend system
must have the appropriate SSD setup configured too.

The following is an example Docker command creating a full provisioned, 50 GB volume:
```
$ docker volume create -d hpe --name <vol_name> -o size=50 -o provisioning=full
```

### Creating replicated volume<a name="replication"></a>
```
$ docker volume create -d hpe --name <vol_name> -o replicationGroup=<3PAR RCG name>
```
For details, please see [Replication: HPE 3PAR Docker Storage Plugin](replication.md)


### Enabling file permissions and ownership<a name="file-permission-owner"></a>
1. To set permissions of root directory of a file system:
```
$ docker volume create -d hpe --name <volume-name> -o fsMode=<octal-number-specified-in-chmod>
```

2. To set ownership of root directory of a file system:
```
$ docker volume create -d hpe --name <volume-name> -o fsOwner=<UserId>:<GroupId>
```
For details, please see [Enabling file permissions and ownership](file-permission-owner.md)


### Managing volumes using multiple backends<a name="multi-array-feature"></a>
```
$ docker volume create -d hpe --name <volume-name> -o backend=<backend-name>
```
For details, please see [Managing volumes using multiple backends](multi-array-feature.md)


### Deleting a volume<a name="delete"></a>
```
$ docker volume rm <vol_name>
```

### Listing volumes<a name="list"></a>
```
$ docker volume ls
```

### Inspecting a volume<a name="inspect"></a>
```
$ docker volume inspect <vol_name>
```

### Mounting a volume<a name="mount"></a>
Use the following command to mount a volume and start a bash prompt:
```
$ docker run -it -v <vol_name>:/<mount_point>/ --volume-driver hpe <image_name> bash
```

On Docker 17.06 or later, run below command:
```
$ docker run -it --mount type=volume,src=<vol-name>,dst=<container-path>,volume-driver=<driver>,volume-opt=<KEY0>=<VALUE0>,volume-opt=<KEY1>=<VALUE1> --name mycontainer <IMAGE>
```

>Note: If the volume does not exist it will be created.

The image used for mounting can be any image located on https://hub.docker.com/ or
the local filesystem. See https://docs.docker.com/v1.8/userguide/dockerimages/
for more details.

### Unmounting a volume<a name="unmount"></a>
Exiting the bash prompt will cause the volume to unmount:
```
/ exit
```

The volume is still associated with a container at this point.

Run the following command to get the container ID associated with the volume:
```
$ sudo docker ps -a
```

Then stop the container:
```
$ sudo docker stop <container_id>
```

Next, delete the container:
```
$ sudo docker rm <container_id>
```

Finally, remove the volume:
```
$ sudo docker volume rm <vol_name>
```

### Creating a volume with an existing VVset and QoS rules (**introduced in plugin version 2.1**)<a name="qos"></a>
```
$ docker volume create -d hpe --name <target_vol_name> -o qos-name=<vvset_name>
```
>**Note:** The **VVset** defined in **vvset_name** MUST exist in the HPE 3PAR and have QoS rules applied.

### Creating a clone of a volume (**introduced in plugin version 2.1**)<a name="clone"></a>
```
$ docker volume create -d hpe --name <target_vol_name> -o cloneOf=<source_vol_name>
```
### Creating compressed volume (**introduced in plugin version 2.1**)<a name="compression"></a>
```
$ docker volume create -d hpe --name <target_vol_name> -o compression=true
```

### Creating a snapshot or virtualcopy of a volume (**introduced in plugin version 2.1**)<a name="snapshot"></a>
```
$ docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=<source_vol_name>
```
**Snapshot optional parameters**
- **expirationHours** -- specifies the expiration time for a snapshot in hours and will be automatically deleted from the 3PAR once the time defined in **expirationHours** expires.

- **retentionHours**  -- specifies the retention time a snapshot in hours. The snapshot will not be able to be deleted from the 3PAR until the number of hours defined in **retentionHours** have expired.

>**Note:**
>* If **snapcpg** is not configured in `hpe.conf` then the **cpg** defined in `hpe.conf` will be used for snapshot creation.
>
>* If both **expirationHours** and **retentionHours** are used while creating a snapshot, then **retentionHours** should be *less* than **expirationHours**
```
$ docker volume create -d hpe --name <snapshot_name> -o virtualCopyOf=<source_vol_name> -o expirationHours=3
```
>**Note:** To mount a snapshot, you can use the same commands as [mounting a volume](#mount) as specified above.


### Importing non-docker managed volumes (**introduced in plugin version 3.0**)<a name="import-vol"></a>
```
$ docker volume create -d hpe --name <docker_volume_name> -o importVol=<3par_volume_name>
```

>**Note:** To import a snapshot, you have to first import the parent volume of the snapshot as docker volume

### Displaying help on usage (**introduced in plugin version 3.0**)<a name="usage-help"></a>
```
$ docker volume create -d hpe -o help
```

### Displaying available backends and their status (**introduced in plugin version 3.0**)<a name="backends-status"></a>
```
$ docker volume create -d hpe -o help=backends
```


### Creating HPE 3PAR snapshot schedule (**introduced in plugin version 3.0**)<a name="snapshot_schedule"></a>
```
$ docker volume create -d hpe --name <snapshot-name> -o virtualCopyOf=<source-volume> 
-o scheduleFrequency=<cron-format-string-within-double-quotes> -o scheduleName=<name> 
-o snapshotPrefix=<snapshot-prefix> -o expHrs=<expiration-hours> -o retHrs=<retention-hours>
```
For details, please see [Creating HPE 3PAR snapshot schedule](create_snapshot_schedule.md)


## Usage of the HPE 3PAR Volume Plug-in for Docker in Kubernetes/OpenShift<a name="k8_usage"></a>

The following section will cover different operations and commands that can be used to familiarize yourself and verify the installation of the HPE 3PAR Volume Plug-in for Docker by provisioning storage using Kubernetes/OpenShift resources like **PersistentVolume**, **PersistentVolumeClaim**, **StorageClass**, **Pods**, etc.

* [Kubernetes/OpenShift Terms](#terms)
* [StorageClass Example](#sc)
  * [StorageClass options](#sc_parameters)
* [Persistent Volume Claim Example](#pvc)
* [Pod Example](#pod)
* [Restarting the Containerized HPE 3PAR Volume Plug-in](#restart)

To learn more about Persistent Volume Storage and Kubernetes/OpenShift, go to:
https://kubernetes.io/docs/tasks/configure-pod-container/configure-persistent-volume-storage/

### Key Kubernetes/OpenShift Terms:<a name="k8_terms"></a>
* **kubectl** – command line interface for running commands against Kubernetes clusters.
* **oc** – command line interface for running commands against OpenShift platform.
* **PV** – Persistent Volume is a piece of storage in the cluster that has been provisioned by an administrator.
* **PVC** – Persistent Volume Claim is a request for storage by a user.
* **SC** – Storage Class provides a way for administrators to describe the “classes” of storage they offer.
* **hostPath volume** – mounts a file or directory from the host node’s filesystem into your Pod.

To get started, in an OpenShift environment, we need to relax the security of your cluster, so pods are allowed to 
use the **hostPath** volume plugin without granting everyone access to the privileged **SCC**:

1. Edit the restricted SCC:
```
$ oc edit scc restricted
```

2. Add `allowHostDirVolumePlugin: true`

3. Save the changes

4. Restart node service (master node).
```
$ sudo systemctl restart origin-node.service
```

Below is an example yaml specification to create Persistent Volumes using the **HPE 3PAR FlexVolume driver**. The **HPE 3PAR FlexVolume driver** is a simple daemon that listens for **PVCs** and satisfies those claims based on the defined **StorageClass**.

>Note: If you have OpenShift installed, **kubectl create** and **oc create** commands can be used interchangeably when creating **PVs**, **PVCs**, and **SCs**.

**Dynamic volume provisioning** allows storage volumes to be created on-demand. To enable dynamic provisioning, a cluster administrator needs to pre-create one or more **StorageClass** objects for users. The **StorageClass** object defines the storage provisioner (in our case the **HPE 3PAR Volume Plug-in for Docker**) and parameters to be used when requesting persistent storage within a Kubernetes/Openshift environment. The **StorageClass** acts like a "storage profile" and gives the storage admin control over the types and characteristics of the volumes that can be provisioned within the Kubernetes/OpenShift environment. For example, the storage admin can create multiple **StorageClass** profiles that have size restrictions, if they are full or thin provisioned, compressed, etc.

### StorageClass Example<a name="sc"></a>

The following creates a **StorageClass "sc1"** that provisions a compressed volume with the help of HPE 3PAR Docker Volume Plugin.

```yaml
$ sudo kubectl create -f - << EOF
---
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: sc1
provisioner: hpe.com/hpe
parameters:
  size: "16"
  compression: "true"
EOF
```

#### Supported StorageClass parameters<a name="sc_parameters"></a>

| StorageClass Options | Type    | Parameters                                 | Example                          |
|----------------------|---------|--------------------------------------------|----------------------------------|
| size                 | integer | -                                          | size: "10"                       |
| provisioning         | String  | thin, thick                                | provisioning: "thin"             |
| flash-cache          | String  | true, false                                | flash-cache: "true"              |
| compression          | boolean | true, false                                | compression: "true"              |
| MountConflictDelay   | integer | -                                          | MountConflictDelay: "30"         |
| qos-name             | String  | vvset name                                 | qos-name: "<vvset_name>"         |
| cloneOf              | String  | volume name                                | cloneOf: "<volume_name>"         |
| virtualCopyOf        | String  | volume name                                | virtualCopyOf: "<volume_name>"   |
| expirationHours      | integer | option of virtualCopyOf                    | expirationHours: "10"            |
| retentionHours       | integer | option of virtualCopyOf                    | retentionHours: "10"             |
| accessModes          | String  | ReadWriteOnce                              | accessModes: <br> &nbsp;&nbsp;  - ReadWriteOnce    |
| replicationGroup     | String  | 3PAR RCG name                              | replicationGroup: "Test-RCG"     |


### Persistent Volume Claim Example<a name="pvc"></a>

Now let’s create a claim **PersistentVolumeClaim** (**PVC**). Here we specify the **PVC** name **pvc1** and reference the **StorageClass "sc1"** that we created in the previous step.

```yaml
$ sudo kubectl create -f - << EOF
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pvc1
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: sc1
EOF
```

At this point, after creating the **SC** and **PVC** definitions, the volume hasn’t been created yet. The actual volume gets created on-the-fly during the pod deployment and volume mount phase.

### Pod Example<a name="pod"></a>

So, let’s create a **pod "pod1"** using the **nginx** container along with some persistent storage:

```yaml
$ sudo kubectl create -f - << EOF
---
kind: Pod   
apiVersion: v1
metadata:
  name: pod1
spec:
  containers:
  - name: nginx
    image: nginx
    volumeMounts:
    - name: export
      mountPath: /export
  restartPolicy: Always
  volumes:
  - name: export
    persistentVolumeClaim:
      claimName: pvc1
EOF
```

When the pod gets created and a mount request is made, the volume is now available and can be seen using the following command:

```
$ docker volume ls
DRIVER   VOLUME NAME
hpe      export
```
On the Kubernetes/OpenShift side, it should now look something like this:
```
$ kubectl get pv,pvc,pod -o wide
NAME       CAPACITY   ACCESSMODES   RECLAIMPOLICY   STATUS    CLAIM            STORAGECLASS   REASON   AGE
pv/pv1     20Gi       RWO           Retain          Bound     default/pvc1                             11m

NAME         STATUS    VOLUME    CAPACITY   ACCESSMODES   STORAGECLASS   AGE
pvc/pvc1     Bound     pv100     20Gi       RWO                          11m

NAME                          READY     STATUS    RESTARTS   AGE       IP             NODE
po/pod1                       1/1       Running   0          11m       10.128.1.53    cld6b16
```

**Static provisioning** is a feature that is native to Kubernetes and that allows cluster admins to make existing storage devices available to a cluster. As a cluster admin, you must know the details of the storage device, its supported configurations, and mount options.

To make existing storage available to a cluster user, you must manually create the storage device, a PV,PVC and POD.

Below is an example yaml specification to create Persistent Volumes using the HPE 3PAR FlexVolume driver. 

```
Note: If you have OpenShift installed, kubectl create and oc create commands can be used interchangeably when creating PVs, PVCs, and PODs.
```

Persistent volume Example
The following creates a Persistent volume "pv-first" with the help of HPE 3PAR Docker Volume Plugin.

```yaml
$ sudo kubectl create -f - << EOF
---
apiVersion: v1
kind: PersistentVolume
metadata:                                             
  name: pv-first
spec:
    capacity:
      storage: 10Gi
    accessModes:
    - ReadWriteOnce
    flexVolume:
      driver: hpe.com/hpe
      options: 
        size: "10"
EOF
```

Persistent Volume Claim Example
Now let’s create a claim PersistentVolumeClaim (PVC). Here we specify the PVC name pvc-first.

```yaml
$ sudo kubectl create -f - << EOF
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pvc-first
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
EOF
```

At this point, after creating the PV and PVC definitions, the volume hasn’t been created yet. The actual volume gets created on-the-fly during the pod deployment and volume mount phase.

Pod Example
So, let’s create a pod "pod-first" using the minio container along with some persistent storage:

```yaml
$ sudo kubectl create -f - << EOF
---
apiVersion: v1
kind: Pod
metadata:
  name: pod-first
spec:
  containers:
  - name: minio
    image: minio/minio:latest
    args:
    - server
    - /export
    env:
    - name: MINIO_ACCESS_KEY
      value: minio
    - name: MINIO_SECRET_KEY
      value: doryspeakswhale
    ports:
    - containerPort: 9000
    volumeMounts:
    - name: export
      mountPath: /export
  volumes:
    - name: export
      persistentVolumeClaim:
        claimName: pvc-first
EOF
```
Now the **pod** can be deleted to unmount the Docker volume. Deleting a **Docker volume** does not require manual clean-up because the dynamic provisioner provides automatic clean-up. You can delete the **PersistentVolumeClaim** and see the **PersistentVolume** and **Docker volume** automatically deleted.


Congratulations, you have completed all validation steps and have a working **Kubernetes/OpenShift** environment.

### Restarting the Containerized plugin<a name="restart"></a>

If you need to restart the containerized plugin used in Kubernetes/OpenShift environments, run the following command:

```
$ docker stop <container_id_of_plugin>
```

>Note: The /run/docker/plugins/hpe.sock and /run/docker/plugins/hpe.sock.lock files are not automatically removed when you stop the container. Therefore, these files will need to be removed manually between each run of the plugin.

```
$ docker start <container_id_of_plugin>
```
