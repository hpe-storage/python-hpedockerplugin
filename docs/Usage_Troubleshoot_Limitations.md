#### Automated Installer Features 
* These are Ansible playbooks to automate the installation of the HPE Volume Plugin for Docker for use within standalone docker environment or Kubernetes/OpenShift environments.
```
NOTE: 

1. The Ansible installer only supports Ubuntu/RHEL/CentOS. 
2. If you are using another distribution of Linux, you will need to modify the 
playbooks to support your application manager (apt, etc.) and the pre-requisite packages.
3. Upgrade of existing Docker engine to higher version might break compatibility of HPE Volume Plugin for Docker.

```
These playbooks perform the following tasks on the Master/Worker nodes as defined in the Ansible [hosts](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/hosts) file.
* Configure the Docker Services for the HPE 3PAR Docker Volume Plug-in.
* Deploys the config files (iSCSI or FC) to support your environment.
* Installs the HPE Volume Plugin for Docker (Containerized version).
* For standalone docker environment, deploys an HPE customized etcd cluster.
* For Kubernetes/OpenShift, deploys a Highly Available HPE etcd cluster used by the HPE Volume Plugin for Docker.
* Supports single node (Use only for testing purposes) or multi-node deployment (HA) as defined in the Ansible hosts file.
* Deploys the HPE FlexVolume Driver.
* FlexVolume driver deployment for single master and multimaster will be as per the below table.

Cluster       | OS 3.9        | OS 3.10        | OS 3.11    | K8S 1.11      |  K8S 1.12     | K8S 1.13     | K8S 1.14     | K8S 1.15
------------- | ------------- | -------------  | -----------|------------   |-------------  |------------- |------------- | -------------
Single Master | System Process| System Process | Deployment | System Process| System Process| Deployment   | Deployment   | Deployment
Multimaster   | NA            | NA             |  Deployment| NA            | NA            | Deployment   | Deployment  | Deployment 


**NOTE:** System Process can be verified using systemctl commands whereas Deployment can be verified using kubectl get pods command. Please refer to [PostInstallation_checks](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/PostInstallation_checks.md) for more details.

#### Supported Features
+ Fibre Channel & iSCSI support for 3PAR
+ Fibre Channel support for Primera
+ Secure/Unsecure etcd cluster for fault tolerance
+ Advanced volume features
	+ thin
	* dedup
	* full
	* compression
	* snapshots
	* clones
	* QoS
	* snapshot mount
	* mount_conflict_delay
	* concurrent volume access
	* replication
	* snapshot schedule
	* file system permissions and ownership
	* multiple backends
	* file share [CRD operations] only for 3PAR

#### Block operations usage
See the [block operations usage guide](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/usage.md) for details on the supported operations and usage of the plugin.

#### File share operations usage
See the [file share operations usage guide](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/share_usage.md) for details on the supported operations and usage of the plugin.

#### Troubleshooting
Troubleshooting issues with the plugin can be performed using these [tips](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/troubleshooting.md)

#### SPOCK Link for HPE 3PAR and HPE Primera Volume Plugin for Docker
[SPOCK Link](https://spock.corp.int.hpe.com/spock/utility/document.aspx?docurl=Shared%20Documents/hw/3par/3par_volume_plugin_for_docker.pdf)

#### Limitations
+ List of issues around the containerized version of the plugin/Managed plugin is present in https://github.com/hpe-storage/python-hpedockerplugin/issues

``` $ docker volume prune ``` is not supported for volume plugin, instead use ``` $docker volume rm $(docker volume ls -q -f "dangling=true") ``` to clean up orphaned volumes.

+ Shared volume support is present for containers running on the same host.

+ For upgrading the plugin from older version to the current released version, user needs to unmount all the volumes and follow the standard upgrade procedure described in docker guide.

+ Encryption of the 3PAR and Primera user password is supported on Volume Plug-in versions 3.1.1 & 3.3.1 and not supported on Volume Plug-in versions 3.2 & 3.3.

+ Volumes created using older plugins (2.0.2 or below) do not have snap_cpg associated with them, hence when the plugin is upgraded to 2.1 and user wants to perform clone/snapshot operations on these old volumes, he/she must set the snap_cpg for the corresponding volumes using 3par cli or any tool before performing clone/snapshot operations.

+ While inspecting a snapshot, its provisioning field is set to that of parent volume's provisioning type. In 3PAR however, it is shown as 'snp'.

+ Mounting a QoS enabled volume can take longer than a volume without QoS for both FC and iSCSI protocol.

+ For a cloned volume with the same size as source volume, comment field won’t be populated on 3PAR.

+ User not allowed to import a 3PAR legacy volume when it is under use(Active VLUN).

+ User needs to explicitly manage all the child snapshots, until which managed parent volume cannot be deleted

+ User cannot manage already managed volume by other docker host(i.e. volume thats start with 'dcv-')

+ It is recommended for a user to avoid importing legacy volume which has schedules associated with it. If this volume needs to be imported please remove existing schedule on 3PAR and import the legacy volume.

+ "Snapshot schedule creation can take more time resulting into Docker CLI timeout. However, snapshot schedule may still get created in the background. User can follow below two steps in case of time out issue from docker daemon while creating snapshot schedule."
```
docker volume inspect <snapshot_name>. This should display snapshot details with snapshot schedule information.

Verify if schedule got created on the array using 3PAR CLI command:
$ showsched
```
+ If a mount fails due to dangling LUN use this section of troubleshooting guide [Removing Dangling LUN](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/troubleshooting.md#removing-dangling-lun)

+ If two or more backends are defined with the same name then the last backend is picked up and rest ignored.

+ After doing scsi rescan if the symlinks for the device are not populated in /dev/disk/by-path, Plugin will not function correctly during mount operation.

+ For volume upper size limitation, please do refer 3PAR's documentation.

+ The configuration parameter **mount_prefix**, is applicable for containerized plugin only. If used with the managed plugin, mount operation fails.

+ For statefulset pod stuck in "ContainerCreating" state after a worker node reboot, the following manual procedure has to be done -- [Details](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/recover_post_reboot.md)

+ For Pod mount using File Persona, this flag **allowPrivilegeEscalation: true** under **securityContextis** mandantory for volume plugin to mount a file persona NFS share. eg.

```

kind: Pod
apiVersion: v1
metadata:
  name: podfiletestw4-uid-gid-nosecurity
spec:
  containers:
  - name: nginx
    securityContext:
#       runAsUser: 10500
#       runAsGroup: 10800
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
      claimName: sc-file-pvc-uid-gid

```

+ if the doryd systemctl daemon does'nt start, then you have edit vi /etc/systemd/system/doryd.service


```

[Unit]
Description=manage doryd service for HPE Volume Plugin for Docker

[Service]
Type=simple
ExecStart=/usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/doryd /etc/kubernetes/admin.conf hpe.com
Restart=on-abort

[Install]
WantedBy=multi-user.target

```

+ Updated **/etc/kubernetes/admin.conf** by **/etc/origin/master/admin.kubeconfig** and then do **systemctl daemon-reload** and **systemctl restart doryd**

+ Check out the [Quick Start Guide](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/quick_start_guide.md) for deploying the HPE Docker Volume Plugin on Plain Docker environment.