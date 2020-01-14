## POST INSTALL/UPGRADE CHECKS 
```
1.	Installer should not show any failures and PLAY RECAP should look like below

PLAY RECAP ***********************************************************************************************************************************************************************************
<Master1-IP>           : ok=85   changed=33   unreachable=0    failed=0
<Master2-IP>           : ok=76   changed=29   unreachable=0    failed=0
<Master3-IP>           : ok=76   changed=29   unreachable=0    failed=0
<Worker1-IP>           : ok=70   changed=27   unreachable=0    failed=0
<Worker2-IP>           : ok=70   changed=27   unreachable=0    failed=0
localhost              : ok=9    changed=3    unreachable=0    failed=0
```
```
2.	Verify plugin installtion on all nodes.

$ docker ps | grep plugin; ssh <Master2-IP> "docker ps | grep plugin";ssh <Master3-IP> "docker ps | grep plugin";ssh <Worker1-IP> "docker ps | grep plugin";ssh <Worker2-IP> "docker ps | grep plugin"
51b9d4b1d591        hpestorage/legacyvolumeplugin:3.3.1          "/bin/sh -c ./plugin…"   12 minutes ago      Up 12 minutes                           plugin_container
a43f6d8f5080        hpestorage/legacyvolumeplugin:3.3.1          "/bin/sh -c ./plugin…"   12 minutes ago      Up 12 minutes                           plugin_container
a88af9f46a0d        hpestorage/legacyvolumeplugin:3.3.1          "/bin/sh -c ./plugin…"   12 minutes ago      Up 12 minutes                           plugin_container
5b20f16ab3af        hpestorage/legacyvolumeplugin:3.3.1          "/bin/sh -c ./plugin…"   12 minutes ago      Up 12 minutes                           plugin_container
b0813a22cbd8        hpestorage/legacyvolumeplugin:3.3.1          "/bin/sh -c ./plugin…"   12 minutes ago      Up 12 minutes                           plugin_container

```
```
3.	Verify doryd is running.

$ kubectl get pods -n kube-system -o wide | grep doryd
kube-storage-controller-doryd-7dd487b446-xr6q2   1/1     Running   0          15m   10.233.67.18     cssosbe01-196150   <none>           <none>

Above command shows doryd deployment is started on cssosbe01-196150. SSH to cssosbe01-196150 to validate.

$ ssh cssosbe01-196150
Last login: Mon Dec 30 11:26:20 2019 from cssosbe01-196119.cluster.local
ABRT has detected 12 problem(s). For more info run: abrt-cli list --since 1576820211

[root@cssosbe01-196150 ~]# docker ps | grep doryd
6a4646a04d51        hpestorage/hpe3par_doryd_openshift         "doryd /dev/null hpe…"   19 minutes ago      Up 19 minutes                           k8s_kube-storage-controller_kube-storage-controller-doryd-7dd487b446-xr6q2_kube-system_7c1dcfbe-638b-484f-9367-eef34a3b95c7_0
a12e6dbdee54        gcr.io/google_containers/pause-amd64:3.1   "/pause"                 19 minutes ago      Up 19 minutes                           k8s_POD_kube-storage-controller-doryd-7dd487b446-xr6q2_kube-system_7c1dcfbe-638b-484f-9367-eef34a3b95c7_0
```

```
4.	Verify hpe.conf on all nodes.
$ cat /etc/hpedockerplugin/hpe.conf

[DEFAULT]
host_etcd_ip_address=<Master1-IP>:23790,<Master2-IP>:23790,<Master3-IP>:23790,<Worker1-IP>:23790,<Worker2-IP>:23790
hpe3par_username=3paradm
hpe3par_password=3pardata
hpe3par_cpg=FC_r1
hpedockerplugin_driver=hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver
host_etcd_port_number=23790
ssh_hosts_key_file=/root/.ssh/known_hosts
san_ip=15.212.xx.xx
san_login=3paradm
san_password=3pardata
hpe3par_api_url=https://15.212.xx.xx:8080/api/v1
hpe3par_iscsi_ips=15.212.xx.xx,15.212.xx.xx
```
```
5.	Verify backend initialization on all nodes. [DEFAULT] backend must be initialized appropriately.

$ docker volume create -d hpe -o help=backends
Error response from daemon: create f7a9d5efd202d6a2820ee9243a52b03865bc8df15f8fbdcc1ac894a73baa4b8a:
======================================================
NAME                                          STATUS
======================================================
DEFAULT                                        OK
```
```
6.	Verify etcd cluster service on all nodes.

$ systemctl status etcd_hpe
● etcd_hpe.service - etcd
   Loaded: loaded (/etc/systemd/system/etcd_hpe.service; enabled; vendor preset: disabled)
   Active: active (running) since Fri 2020-01-10 09:43:47 IST; 4 days ago
     Docs: https://github.com/coreos/etcd
 Main PID: 6978 (etcd_hpe)
    Tasks: 9
   Memory: 105.6M
   CGroup: /system.slice/etcd_hpe.service
           └─6978 /usr/bin/etcd_hpe --name <Master1-IP> --data-dir /root/etcd_hpe_data --initial-advertise-peer-urls http://<Master1-IP>:23800 --listen-peer-urls http://<Master1-IP>....

Jan 14 12:22:31 cssosbe01-196119 etcd_hpe[6978]: compacted raft log at 705071
Jan 14 12:22:51 cssosbe01-196119 etcd_hpe[6978]: purged file /root/etcd_hpe_data/member/snap/0000000000000017-00000000000a1262.snap successfully
Jan 14 13:45:51 cssosbe01-196119 etcd_hpe[6978]: start to snapshot (applied: 720072, lastsnap: 710071)
Jan 14 13:45:51 cssosbe01-196119 etcd_hpe[6978]: saved snapshot at index 720072
Jan 14 13:45:51 cssosbe01-196119 etcd_hpe[6978]: compacted raft log at 715072
Jan 14 13:46:21 cssosbe01-196119 etcd_hpe[6978]: purged file /root/etcd_hpe_data/member/snap/0000000000000017-00000000000a3973.snap successfully
Jan 14 15:09:12 cssosbe01-196119 etcd_hpe[6978]: start to snapshot (applied: 730073, lastsnap: 720072)
Jan 14 15:09:12 cssosbe01-196119 etcd_hpe[6978]: saved snapshot at index 730073
Jan 14 15:09:12 cssosbe01-196119 etcd_hpe[6978]: compacted raft log at 725073
Jan 14 15:09:21 cssosbe01-196119 etcd_hpe[6978]: purged file /root/etcd_hpe_data/member/snap/0000000000000017-00000000000a6084.snap successfully
```
```
7. Verify etcd members on all nodes.
$ /usr/bin/etcdctl --endpoints http://<Master1-IP>:23790 member list 
b70ca254f54dd23: name=<Worker2-IP> peerURLs=http://<Worker2-IP>:23800 clientURLs=http://<Worker2-IP>:23790 isLeader=true
236bf7d5cc7a32d4: name=<Worker1-IP> peerURLs=http://<Worker1-IP>:23800 clientURLs=http://<Worker1-IP>:23790 isLeader=false
445e80419ae8729b: name=<Master1-IP> peerURLs=http://<Master1-IP>:23800 clientURLs=http://<Master1-IP>:23790 isLeader=false
e340a5833e93861e: name=<Master3-IP> peerURLs=http://<Master3-IP>:23800 clientURLs=http://<Master3-IP>:23790 isLeader=false
f5b5599d719d376e: name=<Master2-IP> peerURLs=http://<Master2-IP>:23800 clientURLs=http://<Master2-IP>:23790 isLeader=false
```
