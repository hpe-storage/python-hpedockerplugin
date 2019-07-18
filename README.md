## HPE 3PAR Volume Plugin for Docker

HPE Docker Volume Plugin is an open source project that provides persistent storage and features for your containerized applications using HPE 3PAR StoreServ Storage arrays.
It supports both block and file (NFS shares) based features.

The HPE Docker Volume Plugin supports popular container platforms like Docker, Kubernetes, OpenShift 

## HPE Docker Volume Plugin Overview

### **Standalone Docker instance**

Here is an example of the HPE Docker Volume plugin being used in a standalone Docker instance:

![HPE Docker Volume Plugin](/docs/img/3PAR_docker_design_diagram_75.png)

---
### **Kubernetes/OpenShift environment**

Here is an example of the HPE Docker Volume plugin being used in an OpenShift environment:

![HPE Docker Volume Plugin with OpenShift](/docs/img/3PAR_k8_design_diagram_75.png)

## Install and Quick Start instructions

* Review the [System Requirements](/docs/system-reqs.md) before installing the plugin
* Check out the [Quick Start Guide](/docs/quick_start_guide.md) for deploying the **HPE Docker Volume Plugin** in [Docker](/docs/quick_start_guide.md#docker) or in [Kubernetes/OpenShift](/docs/quick_start_guide.md#k8) environments


## Supported Features

* Fibre Channel & iSCSI support for 3PAR
* Secure/Unsecure etcd cluster for fault tolerance
* Advanced volume features
  * thin
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
  * file share [CRD operations]

## Block operations usage

See the [block operations usage guide](/docs/usage.md) for details on the supported operations and usage of the plugin.

## File share operations usage

See the [file share operations usage guide](/docs/share_usage.md) for details on the supported operations and usage of the plugin.

## Troubleshooting

Troubleshooting issues with the plugin can be performed using these [tips](/docs/troubleshooting.md)


## SPOCK Link for HPE 3PAR Volume Plugin for Docker

* [SPOCK Link](https://spock.corp.int.hpe.com/spock/utility/document.aspx?docurl=Shared%20Documents/hw/3par/3par_volume_plugin_for_docker.pdf)

## Limitations
- List of issues around the containerized version of the plugin/Managed plugin is present in https://github.com/hpe-storage/python-hpedockerplugin/issues 

- ``$ docker volume prune`` is not supported for volume plugin, instead use ``$docker volume rm $(docker volume ls -q -f "dangling=true") `` to clean up orphaned volumes.

- Shared volume support is present for containers running on the same host.

- For upgrading the plugin from older version to the current released version, user needs to unmount all the volumes and follow the standard
 upgrade procedure described in docker guide. 
 
- Volumes created using older plugins (2.0.2 or below) do not have snap_cpg associated with them, hence when the plugin is upgraded to      2.1 and user wants to perform clone/snapshot operations on these old volumes, he/she must set the snap_cpg for the
   corresponding volumes using 3par cli or any tool before performing clone/snapshot operations.

- While inspecting a snapshot, its provisioning field is set to that of parent volume's provisioning type. In 3PAR however, it is shown as 'snp'.

- Mounting a QoS enabled volume can take longer than a volume without QoS for both FC and iSCSI protocol.

- For a cloned volume with the same size as source volume, comment field won’t be populated on 3PAR.

- User not allowed to import a 3PAR legacy volume when it is under use(Active VLUN).

- User needs to explicitly manage all the child snapshots, until which managed parent volume cannot be deleted

- User cannot manage already managed volume by other docker host(i.e. volume thats start with 'dcv-')

- It is recommended for a user to avoid importing legacy volume which has schedules associated with it. If this volume needs to be imported please remove existing schedule on 3PAR and import the legacy volume.

- "Snapshot schedule creation can take more time resulting into Docker CLI timeout. However, snapshot schedule may still get created in the background. User can follow below two steps in case of time out issue from docker daemon while creating snapshot schedule."

```Inspect the snapshot to verify if the snapshot schedule got created
docker volume inspect <snapshot_name>. This should display snapshot details with snapshot schedule information.

Verify if schedule got created on the array using 3PAR CLI command:
$ showsched
```

- If a mount fails due to dangling LUN use this section of troubleshooting guide [Removing Dangling LUN](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/troubleshooting.md#removing-dangling-lun)

- If two or more backends are defined with the same name then the last backend is picked up and rest ignored.

- after doing scsi rescan if the symlinks for the device are not populated in /dev/disk/by-path, Plugin will not function correctly during mount operation.

- For volume upper size limitation, please do refer 3PAR's documentation.

- The configuration parameter **mount_prefix**, is applicable for containerized plugin only. If used with the managed plugin, mount operation fails.