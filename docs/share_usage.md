
# File share usage guide

The HPE 3PAR file share feature allows user to manage NFS file shares 
on 3PAR arrays through Docker interface. 

## Prerequisites
1. HPE 3PAR OS version must be 3.3.1 (MU3)
2. Must have File Persona (102400G) license
3. File Service must be configured on the array

The following guide covers many of the options used for provisioning 
volumes and volume management within standalone Docker environments 
as well as Kubernetes/OpenShift environments.

* ### [Using HPE 3PAR Volume Plug-in for Docker](#docker_usage)
  * [Configuring backend for file share](#configure_backend)
  * [Creating file share](#createshare_cmd)
  * [Creating default file share](#create_def_share)
  * [Creating file share using non-default CPG](#create_share_non_def_cpg)
  * [Creating file share using non-default or legacy FPG](#create_share_non_def_or_leg_fpg)
  * [Creating file share on a non-default FPG and CPG](#create_share_non_def_fpg_and_cpg)
  * [Mounting file share](#mount_share)
  * [Un-mounting file share](#unmount_share)
  * [Inspecting file share](#inspect_share)
  * [Listing file shares](#list_share)
  * [Removing a file share](#remove_share)
  * [Displaying file share help](#show_help)
  * [Displaying file share backend initialization status](#show_status)

* ### [Using HPE 3PAR Volume Plug-in with Kubernetes/OpenShift](#k8_usage)
  * [Kubernetes/OpenShift Terms](#k8_terms)
  * [StorageClass Example](#sc)
    * [StorageClass options](#sc_parameters)
  * [Persistent Volume Claim Example](#pvc)
  * [Pod Example](#pod)
  * [Restarting the Containerized HPE 3PAR Volume Plug-in](#restart)

---

## Configuring backend for file share <a name="configure_backend"></a>
In order to use HPE 3PAR file share feature, user needs to 
configure a backend one for each target array as below:


```sh
[DEFAULT]

# ssh key file required for driver ssh communication with array
ssh_hosts_key_file = /root/.ssh/known_hosts

# IP Address and port number of the ETCD instance
# to be used for storing the share meta data
host_etcd_ip_address =  xxx.xxx.xxx.xxx
host_etcd_port_number = 2379

# Client certificate and key details for secured ETCD cluster
# host_etcd_client_cert = /root/plugin/certs/client.pem
# host_etcd_client_key = /root/plugin/certs/client-key.pem

# Logging level for the plugin logs
logging = DEBUG

# Logging level for 3PAR client logs
hpe3par_debug = True

# Suppress Requests Library SSL warnings
suppress_requests_ssl_warnings = True

# Set the driver to be File driver
hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_file.HPE3PARFileDriver

hpe3par_api_url = https://xxx.xxx.xxx.xxx:8080/api/v1
hpe3par_username = <user>
hpe3par_password = <pwd>
hpe3par_san_ip = xxx.xxx.xxx.xxx
hpe3par_san_login = <san_user>
hpe3par_san_password = <san_pwd>

# Server IP pool is mandatory and can be specified as a mix of range of IPs and
# individual IPs delimited by comma
# Each range or individual IP must be followed by the corresponding subnet mask
# delimited by semi-colon
# E.g.: IP-Range:Subnet-Mask,Individual-IP:SubnetMask…
hpe3par_server_ip_pool = xxx.xxx.xxx.xxx-xxx.xxx.xxx.yyy:255.255.255.0

# Override default size of FPG here. It must be in the range 1TiB – 64TiB. If
# not specified here, it defaults to 16TiB
hpe3par_default_fpg_size = 10
```
User can define multiple backends in case more than one array needs to be managed 
by the plugin.

User can also define backends for block driver(s) along with file driver(s). 
However, a default backend is mandatory for both block and file drivers for the 
default use cases to work. Since ‘DEFAULT’ section can be consumed by either 
block or file driver but not both at the same time, the other driver
is left out without a default backend. In order to satisfy the need for the other 
driver to have default backend, HPE 3PAR Plugin introduces two new keywords to 
denote default backend names to be used in such a situation:
1. DEFAULT_FILE and
2. DEFAULT_BLOCK

In case where user already has ‘DEFAULT’ backend configured for block driver, 
and file driver also needs to be configured, then ‘DEFAULT_FILE’ backend MUST 
be defined. In this case, if there is a non-default backend defined for file 
driver without 'DEFAULT_FILE' backend defined, plugin won't get initialized 
properly.

E.g. in the below configuration, we have two backends, first one for block and 
the second one for file. As you can see, default backend is missing for the file
driver. Due to this, the driver will fail to initialize.
```
[DEFAULT]
...
hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver
...

[3PAR_FILE]
...
hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_file.HPE3PARFileDriver
...
```
Similar is the vice-versa case, where ‘DEFAULT’ is configured as file driver 
and the user wants to configure block driver as well. In this case, ‘DEFAULT_BLOCK’ 
MUST be configured for the plugin to work correctly.

Below is that table of all possible default configurations along
with the behavior column for each combination:

|DEFAULT | DEFAULT_BLOCK | DEFAULT_FILE | BEHAVIOR        |
|--------|---------------|--------------|-----------------|
|BLOCK   |--             |--            | Okay            |
|FILE    |--             |--            | Okay            |
|--      |BLOCK |-- |DEFAULT_BLOCK becomes the default for Block driver|
|--      |-- |FILE  |DEFAULT_FILE becomes the default for File driver|
|BLOCK   |-- |FILE  |DEFAULT_FILE becomes the default for File driver|
|FILE    |BLOCK |-- |DEFAULT_BLOCK becomes the default for Block driver|
|BLOCK   |BLOCK |FILE  |DEFAULT_BLOCK becomes like any other non-default backend in multi-backend configuration for Block driver. DEFAULT_FILE becomes the default for File driver|
|FILE    |BLOCK |FILE |DEFAULT_FILE becomes like any other non-default backend in multi-backend configuration for File driver. DEFAULT_BLOCK becomes the default for Block driver|
|BLOCK   |FILE |--  |DEFAULT_BLOCK is not allowed to be configured for File driver. Plugin initialization fails in this case.|
|FILE   |-- |BLOCK  |DEFAULT_FILE is not allowed to be configured for Block driver. Plugin initialization fails in this case.|


Although HPE does not recommend it, but if the user configures multiple backends 
that are identical in terms of target array and CPG, then the default FPG 
created for such backends would not be the same – rather a different default 
FPG would be created for each backend.

## Creating file share <a name="createshare_cmd"></a>
```sh
$ docker volume create –d hpe --name <Share-name> <-o filePersona> 
[ -o size=<Share-size-in-GiB>  –o cpg=<CPG-name>  -o fpg=<FPG-name>  
  -o fsOwner=<userId:groupId>  -o fsMode=<Linux_style_permissions OR ACL-string> ]
```

**Where:**

- ***size:*** optional parameter which specifies the desired size of the share in GiB. By default it is 1024 GiB.  
- ***cpg:*** optional parameter which specifies the cpg to be used for the share. This parameter can be used with or without ‘fpg’ option. When used with ‘fpg’, the FPG is created with the specified name if it doesn’t exist. If it does exist, then share is created under it. When used without ‘fpg’ option, default FPG under the specified CPG is selected for share creation. If default FPG doesn’t exist, a new default FPG is created under which the share is created.
- ***fpg:*** optional parameter which specifies the FPG to be used for share creation. If the FPG does not exist, a new FPG with the specified name is created using either the CPG specified using ‘cpg’ option or specified in configuration file.
- ***fsOwner:*** optional parameter which specifies the user-id and group-id that should own the root directory of NFS file share in the form [userId:groupId]. Administrator must ensure that local user and local group with these IDs are present on 3PAR before trying to mount the share otherwise mount will fail.
- ***fsMode:*** optional parameter which specifies the permissions whose value is 1 to 4 octal digits 
                representing the file mode to be applied to the root directory of the file system. 
                Ex: fsMode="0754". Here 0 as the first digit is mandatory. This ensures specified user of 
                fsOwner will have rwx permissions, group will have r-x permissions and others will have 
                just the read permission.
                fsMode can also be an ACL string representing ACL permissions that are applied on the share 
                directory. It contains three ACEs delimited by comma with each ACE consisting of three 
                parts:

    1. type,
    2. flag and
    3. permissions

    These three parts are delimited by semi-colon.
    Out of the three ACEs in the ACL, the first ACE represents the ‘owner’, second one the ‘group’ and the 
    third one ‘everyone’ to be specified in the same order.

    E.g.: ``` A:fd:rwa,A:g:rwaxdnNcCoy,A:fdS:DtnNcy```

    * type field can take only one of these values [A,D,U,L]
    * flag field can take one or more of these values [f,d,p,i,S,F,g]
    * permissions field can take one or more of these values [r,w,a,x,d,D,t,T,n,N,c,C,o,y]  

    Please refer 3PAR CLI user guide more details on meaning of each flag.  
    **Note:** For fsMode values user can specify either of mode bits or ACL string. Both cannot be used 
    simultaneously. While using fsMode it is mandatory to specify fsOwner. If Only fsMode is used, user 
    will not be able to mount the share. 

### Creating default file share <a name="create_def_share"></a>
```  
docker volume create -d hpe --name <share_name> -o filePersona  
```  
This command creates share of default size 1TiB with name ‘share_name’ on 
default FPG. If default FPG is not present, then it is created on the CPG 
specified in configuration file hpe.conf. If ‘hpe3par_default_fpg_size’ is 
defined in hpe.conf, then FPG is created with the specified size. Otherwise, 
FPG is created with default size of 16TiB.  

Please note that FPG creation is a long operation which takes around 3 minutes
and hence it is done asynchronously on a child thread. User must keep inspecting
the status of the share which is in 'CREATING' state during this time. Once the
FPG, VFS and file store are created and quota is applied, the status of share is 
set to 'AVAILABLE' state. User is not allowed to do any operations while the
share is in 'CREATING' state.

If for some reason a failure is encountered, the status of the share is set 
to 'FAILED' state and the reason for failure can be seen by inspecting the share.

A share in 'FAILED' state can be removed.

**Note:** ‘size’ can be specified to override the default share size of 1TiB.  

  
### Creating file share using non-default CPG <a name="create_share_non_def_cpg"></a>
  
```  
docker volume create -d hpe --name <share_name> -o filePersona -o cpg=<cpg_name>  
```  
This command creates share of default size 1TiB on the default FPG whose parent CPG is ‘cpg_name’. If 
default FPG is not present, it is created on CPG ‘cpg_name’ with size ‘hpe3par_default_fpg_size’ if it 
is defined in hpe.conf. Else its size defaults to 16TiB.

**Note:** ‘size’ can be specified to override the default share size of 1TiB.  

  
### Creating file share using non-default or legacy FPG  <a name="create_share_non_def_or_leg_fpg"></a>
```  
docker volume create -d hpe --name <share_name> -o filePersona -o fpg=<fpg_name>  
```  
This command creates a share of default size of 1TiB on the specified FPG ‘fpg_name’. 
The specified FPG 'fpg_name' may or may not exist.

When this command is executed the plugin does the following:
1. If the FPG 'fpg_name' exists and is Docker managed, share is created under
   it provided that enough space is available on the FPG to accommodate the 
   share.
2. If the FPG 'fpg_name' exists and is a legacy FPG, share is created under it
   provided that enough space is available on the FPG to accommodate the share
3. If the FPG 'fpg_name' does not exist, it is created with size 
   'hpe3par_default_fpg_size' configured in hpe.conf provided none of the 3PAR
    limits are hit. Post FPG creation, share is created under it.

If enough space is not there or any 3PAR limit is hit, the status of share is 
set to 'FAILED' along with appropriate error message which can be seen while 
inspecting the share details.

**Note:** ‘size’ can be specified to override the default share size of 1TiB.  
  
### Creating HPE 3PAR file share on a non-default FPG and CPG  <a name="create_share_non_def_fpg_and_cpg"></a>
```  
docker volume create -d hpe --name <share_name> -o filePersona -o fpg=<fpg_name> -o cpg=<cpg_name>  
```  
This command creates a share of default size of 1TiB on the specified FPG ‘fpg_name’. 
The specified FPG 'fpg_name' may or may not exist.

When this command is executed the plugin does the following:
1. If the FPG 'fpg_name' exists and it is Docker managed and the specified 
   CPG 'cpg_name' matches with parent CPG of FPG 'fpg_name', share is created 
   under it provided that enough space is available on the FPG to accommodate 
   the share. If specified CPG 'cpg_name' does not match, share creation fails
   with appropriate error.
2. If the FPG 'fpg_name' exists and it is a legacy FPG and the specified CPG
   'cpg_name' matches with the parent CPG of FPG 'fpg_name', share is created 
   under it provided that enough space is available on the FPG to accommodate
   the share. If specified CPG 'cpg_name' does not match, share creation fails
   with appropriate error.
3. If the FPG 'fpg_name' does not exist, it is created with size 
   'hpe3par_default_fpg_size' configured in hpe.conf provided none of the 3PAR
    limits are hit. Post FPG creation, share is created under it.

If enough space is not there or any 3PAR limit is hit, the status of share is 
set to 'FAILED' along with appropriate error message which can be seen while 
inspecting the share details.

**Note:** 
1. ‘size’ can be specified to override the default share size of 1TiB.  
2. The FPG must have enough capacity to accommodate the share.

### Mounting file share <a name="mount_share"></a>
```
docker run -it --rm  --mount src=<share-name>,dst=</mount-dir>,volume-driver=hpe --name <container-name> alpine /bin/sh
```

This command allows mounting of share 'share-name' inside the container 'container-name' on mount 
directory 'mount-dir' using alpine image. A share can be mounted multiple times
on the same host or different hosts that have access to the share. A share that
is mounted multiple times on a host is unmounted only after the last container 
mounting it is exited or stopped.

Permissions if present are applied after mounting the share.

**Note:** VFS IPs must be reachable from Docker host for share to be mounted successfully.

### Un-mounting file share <a name="unmount_share"></a>
If container shell prompt is there, simply type 'exit' to unmount the share.
If container is in detached mode, then retrieve container ID using 
```docker ps -a``` and simply type:
```
docker stop <container-id>
```

### Inspecting file share <a name="inspect_share"></a>
```
docker volume inspect <share-name>
```
Displays details of the share being inspected

### Listing file share <a name="list_share"></a>
```
docker volume ls
```
Lists all the shares. If volumes are also present, those also get
displayed as part of the output.

### Removing a share <a name="remove_share"></a>
```
docker volume rm <share-name>
```
This command allows removing a share. If the share being removed happens to be
the last share under its parent FPG, then the parent FPG is also removed which
happens asynchronously on a child thread.

**Note:** Any user data present on the share will be lost post this operation.

### Displaying file share help <a name="show_help"></a>
```  
docker volume create -d hpe -o filePersona –o help  
```  
This command displays help content of the file command with possible options that 
can be used with it.

### Displaying file share backend initialization status <a name="show_status"></a>
```  
docker volume create -d hpe -o filePersona –o help=backends
```  
This command displays the initialization status of all the backends that have 
been configured for file driver.

## Usage of the HPE 3PAR Volume Plug-in for Docker in Kubernetes/OpenShift<a name="k8_usage"></a>

The following section will cover different operations and commands that can be used to familiarize yourself and verify the installation of the HPE 3PAR Volume Plug-in for Docker by provisioning storage using Kubernetes/OpenShift resources like **PersistentVolume**, **PersistentVolumeClaim**, **StorageClass**, **Pods**, etc.

* [Kubernetes/OpenShift Terms](#k8_terms)
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

**Dynamic volume provisioning** allows storage volumes to be created 
on-demand. To enable dynamic provisioning, a cluster administrator 
needs to pre-create one or more **StorageClass** objects for users. 
The **StorageClass** object defines the storage provisioner (in our 
case the **HPE 3PAR Volume Plug-in for Docker**) and parameters to be 
used when requesting persistent storage within a Kubernetes/Openshift 
environment. The **StorageClass** acts like a "storage profile" and 
gives the storage admin control over the types and characteristics of 
the volumes that can be provisioned within the Kubernetes/OpenShift 
environment. For example, the storage admin can create multiple 
**StorageClass** profiles that have size restrictions, if they are 
enabled with ACLs, if a CPG other than the configured one needs to be 
used etc.

### StorageClass Example<a name="sc"></a>

The following creates a **StorageClass "sc1"** that provisions a 
default file share with the help of HPE 3PAR Docker Volume Plugin.

**Note:** In order to use file share feature, it is mandatory to specify
'filePersona' option with empty string as value.

```yaml
$ sudo kubectl create -f - << EOF
---
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: sc1
provisioner: hpe.com/hpe
parameters:
  filePersona: ""
EOF
```

#### Supported StorageClass parameters<a name="sc_parameters"></a>

| StorageClass Options | Type    | Parameters                                 | Example                          |
|----------------------|---------|--------------------------------------------|----------------------------------|
| size                 | integer | Size of share in GiB                       | size: "10"                       |
| cpg                  | String  | Name of the CPG                            | cpg: SomeCpg             |
| fpg                  | String  | Existing FPG name including legacy FPG     | fpg: SomeFpg           |
| fsMode               | String | Unix style permissions or ACL string        | fsMode: "A:fd:rwa,A:g:rwaxdnNcCoy,A:fdS:DtnNcy" |
| fsOwner              | String | User Id and Group Id that should own the mounted directory      | fsOwner: "1000:1000"         

### Persistent Volume Claim Example<a name="pvc"></a>

Now let’s create a claim **PersistentVolumeClaim** (**PVC**). Here we 
specify the **PVC** name as **pvc1** and reference the **StorageClass 
"sc1"** that was created in the previous step.

```yaml
$ sudo kubectl create -f - << EOF
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pvc1
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
  storageClassName: sc1
EOF
```

At this point, after creating the **SC** and **PVC** definitions, the 
NFS volume is in the process of creation. User must inspect the NFS volume
and wait till it moves to AVAILABLE state. At this time, user can create
Pod as mentioned below.

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
    securityContext:
      privileged: true
      capabilities:
        add: ["SYS_ADMIN"]
      allowPrivilegeEscalation: true
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

When the pod gets created and a mount request is made, the volume is 
now available and can be seen using the following command:

```
$ docker volume ls
DRIVER   VOLUME NAME
hpe      export
```
On the Kubernetes/OpenShift side, it should now look something like 
this:
```
$ kubectl get pv,pvc,pod -o wide
NAME       CAPACITY   ACCESSMODES   RECLAIMPOLICY   STATUS    CLAIM            STORAGECLASS   REASON   AGE
pv/pv1     20Gi       RWX           Retain          Bound     default/pvc1                             11m

NAME         STATUS    VOLUME    CAPACITY   ACCESSMODES   STORAGECLASS   AGE
pvc/pvc1     Bound     pv100     20Gi       RWX                          11m

NAME                          READY     STATUS    RESTARTS   AGE       IP             NODE
po/pod1                       1/1       Running   0          11m       10.128.1.53    cld6b16
```

**Static provisioning** is a feature that is native to Kubernetes and 
that allows cluster admins to make existing storage devices available 
to a cluster. As a cluster admin, you must know the details of the 
storage device, its supported configurations, and mount options.
To make existing storage available to a cluster user, you must manually 
create the storage device, a PV,PVC and POD.
Below is an example yaml specification to create Persistent Volumes 
using the HPE 3PAR FlexVolume driver. 

```
Note: If you have OpenShift installed, kubectl create and oc create commands can be used interchangeably when creating PVs, PVCs, and PODs.
```

Persistent volume Example
The following creates a Persistent volume "pv-first" with the help of 
HPE 3PAR Docker Volume Plugin.

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
    - ReadWriteMany
    flexVolume:
      driver: hpe.com/hpe
      options: 
        filePersona: ""
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
    - ReadWriteMany
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
    securityContext:
      privileged: true
      capabilities:
        add: ["SYS_ADMIN"]
      allowPrivilegeEscalation: true
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
Now the **pod** can be deleted to unmount the Docker volume. Deleting 
a **Docker volume** does not require manual clean-up because the dynamic 
provisioner provides automatic clean-up. You can delete the 
**PersistentVolumeClaim** and see the **PersistentVolume** and 
**Docker volume** automatically deleted.


Congratulations, you have completed all validation steps and have a 
working **Kubernetes/OpenShift** environment.

### Restarting the Containerized plugin<a name="restart"></a>

If you need to restart the containerized plugin used in Kubernetes/OpenShift environments, run the following command:

```
$ docker stop <container_id_of_plugin>
```

>Note: The /run/docker/plugins/hpe.sock and /run/docker/plugins/hpe.sock.lock files are not automatically removed when you stop the container. Therefore, these files will need to be removed manually between each run of the plugin.

```
$ docker start <container_id_of_plugin>
```

## Limitations / Known Issues
1. There can be a maximum of 256 NFS volumes that can be created using 
   Docker volume plugin due to the limit imposed by 3PAR
2. All the operations must be performed sequentially. E.g. concurrent creation 
   of multiple shares can lead to ETCD lock failures.
3. When block related configuration parameters are used inadvertently in file 
   driver configuration or vice-versa, it does not result in any error - the
   plugin simply ignores it. Eg: snapcpg, a block configuration parameter, 
   when used in file driver configuration, it is ignored.
4. When two backend sections are identically defined, even then each backend 
   is treated differently and results in having their individual default FPGs
   when default share creation is done using both the backends.
5. While using dynamic provisioning with Kubernetes, after creating SC
   and PVC, it is recommended that the user inspects the NFS volume for
   it to become AVAILABLE. It's only after this, POD creation should be
   initiated. Otherwise, POD describe may show warning messages indicating
   that mount has failed.
6. While using static provisioning with Kubernetes, actual NFS volume 
   does not get created on 3PAR immediately after creating PV and PVC.
   It is when the user initiates POD creation that the NFS volume
   creation happens at the backend. During this creation process, the
   NFS volume is in CREATING state and hence there is a delay before
   POD moves to running state. Describing the POD would reveal this 
