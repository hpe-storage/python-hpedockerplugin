## Troubleshooting

This section contains solutions to common problems that may arise during the setup and usage of the plugin.

#### iSCSI Connection Errors
The HPE Docker Volume Plugin must run on the host network in order for iSCSI connections to work properly. Otherwise, unexpected iSCSI errors will occur if you run the plugin on a non-host network.

>**NOTE:** Create and Delete operations will work fine when running the plugin on a non-host network. However, subsequent iSCSI attach operations will fail on those volumes (if the plugin is not on the host network).

#### FC Connection Errors
One or more fibre channel ports of container host and HPE 3PAR StoreServ must be in same zone. Otherwise, only create and delete volume operation will work fine and volume mount operation will fail for all volumes.

If "create file system failed exception" error is seen during volume mount operation and all subsequent mount requests are failed, then stop/uninstall the etcd and docker services and start/install them again with use_multipath and enforce_multipath parameters enabled in hpe.conf

#### SSH Host Keys File

Make sure the file path used for the ssh_hosts_key_file exists. The suggested default is the known hosts file located at /home/stack/.ssh/known_hosts but that may not actually exist yet on a system. The easiest way to create this file is to do the following:
```
$ ssh <username>@<3PAR array IP>
```

Where username is the username for the 3PAR storage array that will be used by the plugin. The IP portion is the IP of the desired storage array. These values are typically defined later in the configuration file itself.

#### Client Certificates for Secured etcd

If a secured etcd cluster is not desired the **host_etcd_client_cert** and **host_etcd_client_key** properties can be commented out safely. In the case where a secured etcd cluster is desired, the two properties must point to the respective certificate and key files.

For setting up secured etcd cluster, refer this doc:
[etcd cluster setup](/docs/advanced/etcd_cluster_setup.md)

#### Debug Logging

Sometimes it is useful to get more verbose output from the plugin. In order to do this one must change the logging property to be one of the following values: INFO, WARN, ERROR, DEBUG.

To enable logging for REST calls made to 3PAR array from Volume Plugin use below flag
```
hpe3par_debug=True in /etc/hpedockerplugin/hpe.conf
```

#### Logs for the plugin

Logs of plugin provides useful information on troubleshooting issue/error further. On Ubuntu, grep for the `plugin id` in the logs , where the `plugin id` can be identified by:

`$ docker-runc list`

Plugin logs will be available in system logs (e.g. `/var/log/syslog` on Ubuntu).

On RHEL and CentOS, issue `journalctl -f -u docker.service` to get the plugin logs.

#### Removing Dangling LUN

If no volumes are in mounted state and `lsscsi` lists any 3PAR data volumes then user is recommended to run the following script to clean up the dangling LUN.

```
for i in `lsscsi | grep 3PARdata | awk '{print $6}'| grep -v "-"| cut -d"/" -f3`; do echo $i; echo 1 > /sys/block/$i/device/delete; done
rescan-scsi-bus.sh -r -f -m
```

If all the scsi devices for 3PAR volumes need to be removed, follow
- Unexport the volumes in 3PAR (using `removevlun -f` CLI)
- On the host , look for `mount| grep hpe` and do umount for each mounted folder
- rescan-scsi-bus.sh -r -f -m

### Collecting necessary Logs

if any issue found please do collect following logs from your Docker host

```
v3.1 onwards 
/etc/hpedockerplugin/3pardcv.log
```
#### Managed Plugin
for any older version below v3.1

```
/var/log/messages
```
#### Containerized Plugin 

```
$docker logs -f <container id of Plugin> 
Getting container id of plugin: docker ps -a | grep hpe 
```

 ## Capturing Logs in Kubernetes/OpenShift environments
 
 Collect above Containerized Plugin logs along with the following logs.
 
 ```
 /var/log/dory.log
 ```
 
 Note: From all the nodes in the Kubernetes/OpenShift Cluster.
 
 ### Dynamic Provisioner Hang 
 
 if you observe any doryd hang in your system, following command need to run to bring back online.
 
 ```
 systemctl restart doryd.service
 ```
 
## Debugging issue with StatefulSet pod stuck in "ContainerCreating" state after a node reboot

If you observe the `kubectl get pods -o wide` for the statefulset pod replicas stuck in "ContainerCreating" state forever on a worker node, please do the following steps to recover

`tail -f /etc/hpedockerplugin/3pardcv.log` reveals some stack like
```
2019-10-14 20:41:57,783 [DEBUG] paramiko.transport [140488068422376] Thread-12532 EOF in transport thread
2019-10-14 20:41:57,807 [DEBUG] paramiko.transport [140488064187112] Thread-12534 EOF in transport thread
2019-10-14 20:41:57,809 [DEBUG] paramiko.transport [140488063126248] Thread-12535 EOF in transport thread
2019-10-14 20:42:01,128 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 Checking to see if /dev/disk/by-id/dm-uuid-mpath-360002ac0000000000101af6e00019d52 exists yet.
2019-10-14 20:42:01,128 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 /dev/disk/by-id/dm-uuid-mpath-360002ac0000000000101af6e00019d52 doesn't exists yet.
2019-10-14 20:42:01,129 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Failed attempt 3
2019-10-14 20:42:01,129 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Have been at this for 6.019 seconds
2019-10-14 20:42:01,130 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 Checking to see if /dev/mapper/360002ac0000000000101af6e00019d52 exists yet.
2019-10-14 20:42:01,130 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 /dev/mapper/360002ac0000000000101af6e00019d52 doesn't exists yet.
2019-10-14 20:42:01,130 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Failed attempt 1
2019-10-14 20:42:01,131 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Have been at this for 0.001 seconds
2019-10-14 20:42:01,131 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Sleeping for 2 seconds
2019-10-14 20:42:03,133 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 Checking to see if /dev/mapper/360002ac0000000000101af6e00019d52 exists yet.
2019-10-14 20:42:03,134 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 /dev/mapper/360002ac0000000000101af6e00019d52 doesn't exists yet.
2019-10-14 20:42:03,134 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Failed attempt 2
2019-10-14 20:42:03,135 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Have been at this for 2.005 seconds
2019-10-14 20:42:03,135 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Sleeping for 4 seconds
2019-10-14 20:42:07,140 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 Checking to see if /dev/mapper/360002ac0000000000101af6e00019d52 exists yet.
2019-10-14 20:42:07,140 [DEBUG] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 /dev/mapper/360002ac0000000000101af6e00019d52 doesn't exists yet.
2019-10-14 20:42:07,141 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Failed attempt 3
2019-10-14 20:42:07,141 [DEBUG] os_brick.utils [140488076110568] PoolThread-twisted.internet.reactor-5 Have been at this for 6.011 seconds
2019-10-14 20:42:07,141 [WARNING] os_brick.initiator.linuxscsi [140488076110568] PoolThread-twisted.internet.reactor-5 couldn't find a valid multipath device path for 360002ac0000000000101af6e00019d52
```
- Get the node where the statefulset pod was scheduled using `kubectl get pods -o wide` and then, 
 - Login to the worker node where the stateful set pod is trying to start
 - Issue `systemctl restart multipathd`

#### Other workarounds 
 - `kubectl cordon <node>` before the node is shutdown (which has statefulset pods mounted) and `kubectl uncordon <node>` after the node reboots and the kubelet (or) atomic-openshift-node.service starts properly
 - Some case, `docker stop plugin_container` before node shutdown, and starting the volume plugin container after node reboots once the node reaches 'Ready' state in `kubectl get nodes` also recovers the pod in stuck state.
