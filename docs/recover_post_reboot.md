# Recovering PODs post reboot
Post reboot, following anomalies are possible:
1.	Some PODs are stuck in *ContainerCreating* state
2.	All PODs are in *Running* state except that some or all PODs ending up in using single path device

#### Case 1: Some PODs are stuck in *ContainerCreating* state
Following steps can be tried out on the rebooted node to recover PODs:

a.	Restart multipath daemon
systemctl restart multipathd

b.	Do a rescan of SCSI devices using:
rescan-scsi-bus.sh

*Note:* If the script rescan-scsi-bus.sh is not present on your system, please install scsi-tools package.

c.	If the above two steps don't help, reboot the system and repeat the above two steps if required

d.	As a result of first two steps or after the third one, it is possible hit the anomaly *#2* which is described below.

#### Case 2: All PODs *Running* but some or all PODs using single-path device
In this case, we suggest that the PODs using single-path be deleted after cordoning the rebooted node.

To find out if one or more PODs are using single-path device(s), we need to check how many multipath devices got formed post reboot.
Multipath devices are the devices that have a prefix "dm-" followed by a number. "/dev/mapper" is the directory which contains mapping of a volume WWN to a multipath device with WWNs being symbolic link to multipath devices. 
Execute the below command on the rebooted node:
```sh
$ ls -lrth /dev/mapper/
…
lrwxrwxrwx. 1 root root 7 Nov 21 12:25 360002ac00000000001008b03000187b7 -> ../dm-3
lrwxrwxrwx. 1 root root 7 Nov 21 12:25 360002ac00000000001008b04000187b7 -> ../dm-4
…
```

The following command displays how many multipath devices are present (3600 is the common prefix for volume WWN) on rebooted node:

```sh
$  ls -l /dev/mapper | grep 3600 | wc -l
14
```

For the anomaly in discussion, the number displayed by the command above would be less than the actual number of PODs despite all the PODs being in RUNNING state. This confirms that some of the PODs ended up using single-path.
In such a case, following needs to be done:
1.	Find out the PODs that are using single-path devices 

   In order to find out what all single devices got mounted, execute the below command on rebooted node:

```sh
   $  mount | grep "/opt/hpe/data/" | grep -v 3600
   /dev/sdb on /opt/hpe/data/hpedocker-ip-15.212.195.241:3260-iscsi-iqn.2000-05.com.3pardata:20020002ac0187b7-lun-0 type ext4 (rw,relatime,seclabel,stripe=4096)
   /dev/sdj on /opt/hpe/data/hpedocker-ip-15.212.195.241:3260-iscsi-iqn.2000-05.com.3pardata:20020002ac0187b7-lun-4 type ext4 (rw,relatime,seclabel,stripe=4096)
```

2.	Get the volume WWN

Execute the following command on the rebooted node:
```sh
   $ ls -l /dev/disk/by-id/ |  grep sdj
   lrwxrwxrwx. 1 root root  9 Nov 22 15:24 scsi-360002ac00000000001008b5b000187b7 -> ../../sdj
   lrwxrwxrwx. 1 root root  9 Nov 22 15:24 wwn-0x60002ac00000000001008b5b000187b7 -> ../../sdj
```
   Volume WWN is the part beyond “scsi-3” or “wwn-0x” displayed above    

3.	Get the Docker volume name using WWN

Get the Docker volume name by executing the below command on any node
that can ssh into the array:

```sh
   $ ssh 3paradm@15.212.195.246 "showvv -showcols Comment" |grep -i 60002ac00000000001008b5b000187b7
   3paradm@15.212.195.246's password:
   {"volume_id": "b954a505-d6df-47fd-b8c0-7194608ae3c0", "name": "b954a505-d6df-47fd-b8c0-7194608ae3c0", "type": "Docker", "display_name": "3par-1-987c772f-6d71-401d-95b5-0bf0ad7b50aa"}
```
   The display_name above is the Docker volume name.

4. Get corresponding PVC name

Now using the Docker volume name, get the corresponding PVC by 
executing the below command on the master node:
```sh
   $ kubectl get pvc -o wide | grep 3par-1-987c772f-6d71-401d-95b5-0bf0ad7b50aa
```

5. Find out the POD corresponding to PVC name

On the master node execute the following command:
```sh
   $ kubectl describe pvc <pvc_name>
```
Sample response would look something like:
```sh
Name:          test-pvc
Namespace:     default
StorageClass:  test-sc
Status:        Bound
Volume:        test-pv
Labels:        <none>
Annotations:   <none>
Finalizers:    [kubernetes.io/pvc-protection]
Capacity:      1Gi
Access Modes:  RWO
Events:        <none>
Mounted By:    test-pod
```
The *"Mounted By"* field in the ouput of above command displays the POD name
In case your version of Kubernetes doesn't show POD name then you would need
to describe the PODs one by one and find the one with matching PVC name.

6. Cordon the rebooted node

On the master node execute the following command:
```sh
$ kubectl cordon <node_name>
```

7. Delete the POD found in step 5 above

On the master node execute the following command:
```sh
$ kubectl delete pods <pod_name> --grace-period=0 --force
```