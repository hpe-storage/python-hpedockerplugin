## Configuring HPE 3PAR Docker Volume Plugin for Docker EE 2.0 UCP 3.0.5

### **Prerequisite packages to be installed on host OS:**

#### Install OS (RHEL, CentOs or Ubuntu) on all the nodes.


#### Ubuntu 16.04 or later:


1. Install the iSCSI (optional if you aren't using iSCSI) and Multipath packages
```
$ sudo apt-get install -y open-iscsi multipath-tools
```

2. Enable the **iscsid** and **multipathd** services
```
$ sudo systemctl daemon-reload
$ sudo systemctl restart open-iscsi multipath-tools docker
```



#### RHEL/CentOS 7.3 or later:

1. Install the iSCSI (optional if you aren't using iSCSI) and Multipath packages

```
$ sudo yum install -y iscsi-initiator-utils device-mapper-multipath
```

2. Configure `/etc/multipath.conf`

```
$ vi /etc/multipath.conf
```

>Copy the following into `/etc/multipath.conf`

```
defaults
{
    polling_interval 10
    max_fds 8192
}

devices
{
    device
	{
        vendor                  "3PARdata"
        product                 "VV"
        no_path_retry           18
        features                "0"
        hardware_handler        "0"
        path_grouping_policy    multibus
        #getuid_callout         "/lib/udev/scsi_id --whitelisted --device=/dev/%n"
        path_selector           "round-robin 0"
        rr_weight               uniform
        rr_min_io_rq            1
        path_checker            tur
        failback                immediate
    }
}
```

3. Enable the iscsid and multipathd services

```
$ sudo systemctl enable iscsid multipathd
$ sudo systemctl start iscsid multipathd
$ sudo systemctl daemon-reload
```

4. Docker EE installation on all hosts

```
$ export DOCKERURL="<Docker_EE_URL_from_dockerhub>"  
e.g. export DOCKERURL="https://storebits.docker.com/ee/m/sub-3352ca9f-2d4d-4859-957c-77838c9ecaf0/rhel"  

$ sudo -E sh -c 'echo "$DOCKERURL/rhel" > /etc/yum/vars/dockerurl'
$ sudo sh -c 'echo "7" > /etc/yum/vars/dockerosversion'
$ sudo yum install -y yum-utils \
   device-mapper-persistent-data \
   lvm2

$ sudo yum-config-manager --enable rhel-7-server-extras-rpms
$ sudo -E yum-config-manager \
  --add-repo \
  "$DOCKERURL/7.6/x86_64/stable-17.06" 

$ sudo yum -y install docker-ee docker-ee-cli containerd.io
```
**Note:- if getting error related with public key, then update /etc/yum.repos.d/storebits.docker.com file with "gpgcheck=0".**

```
$ sudo systemctl start docker
$ sudo docker run hello-world
```

5. Etcd installation on all hosts
```
$ export HostIP="Host_IP"

$ sudo docker run -d -v /usr/share/ca-certificates/:/etc/ssl/certs -p 40010:40010 \
  -p 23800:23800 -p 23790:23790 \
  --name etcd_hpe quay.io/coreos/etcd:v2.2.0 \
  -name etcd0 \
  -advertise-client-urls http://${HostIP}:23790,http://${HostIP}:40010 \
  -listen-client-urls http://0.0.0.0:23790,http://0.0.0.0:40010 \
  -initial-advertise-peer-urls http://${HostIP}:23800 \
  -listen-peer-urls http://0.0.0.0:23800 \
  -initial-cluster-token etcd-cluster-1 \
  -initial-cluster etcd0=http://${HostIP}:23800 \
  -initial-cluster-state new
```

6. Configure hpe.conf in all of the hosts
```
$ sudo mkdir /etc/hpedockerplugin

$ sudo vi /etc/hpedockerplugin/hpe.conf
[DEFAULT]
ssh_hosts_key_file = /root/.ssh/known_hosts
logging = DEBUG
hpe3par_debug = True
suppress_requests_ssl_warnings = False
host_etcd_ip_address = 192.168.68.37
host_etcd_port_number = 23790
hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver
hpe3par_api_url = https://192.168.67.7:8080/api/v1
hpe3par_username = 3paradm
hpe3par_password = 3pardata
san_ip = 192.168.67.7
san_login = 3paradm
san_password = 3pardata
hpe3par_cpg = virendra
hpe3par_snapcpg = virendra-snap
#hpe3par_iscsi_ips = 192.168.68.201, 192.168.68.203
mount_prefix = /var/lib/kubelet/plugins/hpe.com/3par/mounts/
#hpe3par_iscsi_chap_enabled = True
#use_multipath = True
#enforce_multipath = True
mount_conflict_delay = 30
```
**Note:- Update *"host_etcd_ip_address"* & *"host_etcd_port_number"* as per cluster you want to create, i.e. if installed etcd in more than one hosts then provide IP for those host in hpe.conf file and keep hpe.conf file same in all host across the cluster.**

7. Configure and create containerized plugin in all of the hosts.
```
$ vi docker-compose.yml

hpedockerplugin:
 container_name: legacy_plugin
 image: hpestorage/legacyvolumeplugin:3.1
 net: host
 privileged: true
 volumes:
    - /dev:/dev
    - /run/lock:/run/lock
    - /var/lib:/var/lib
    - /var/run/docker/plugins:/var/run/docker/plugins:rw
    - /etc:/etc
    - /root/.ssh:/root/.ssh
    - /sys:/sys
    - /root/plugin/certs:/root/plugin/certs
    - /sbin/iscsiadm:/sbin/ia
    - /lib/modules:/lib/modules
    - /lib64:/lib64
    - /var/run/docker.sock:/var/run/docker.sock
    - /var/lib/kubelet/plugins/hpe.com/3par/mounts/:/var/lib/kubelet/plugins/hpe.com/3par/mounts:rshared
```    

8. Run HPE volume plugin
```
$ docker-compose -f <path of docker-compose.yml> up -d
e.g. docker-compose -f /root/docker-compose.yml up -d
    
Note:- If docker-compose not isntalled then install it as per below steps.
    
$ curl -L https://github.com/docker/compose/releases/download/1.21.2/docker-compose-$(uname -s)-$(uname -m) --insecure -o /usr/local/bin/docker-compose
$ chmod +x /usr/local/bin/docker-compose
$ docker-compose --version
```
**Note:- Make sure etcd should be running before starting volume plugin.**
   
9. Install docker UCP 3.0.5 <on Master Host>
```
$ sudo docker image pull docker/ucp:3.0.5
$ sudo docker container run --rm -it --name ucp \
   -v /var/run/docker.sock:/var/run/docker.sock \
   docker/ucp:3.0.5 install \
   --host-address 192.168.68.37 --pod-cidr 192.167.0.0/16  \
   --interactive
   
In case of any error relataed with IP and port, please refer bottom down section of error and solution for the same.   
```
**Note:- Provide all details like username, password for UCP browser access and note login URL for UCP.**

10. Configuration for kubernetes <On Master Host>.
```
$ sudo mkdir -p /etc/kubernetes
$ cp /var/lib/docker/volumes/ucp-node-certs/_data/kubelet.conf /etc/kubernetes/admin.conf
Modify /etc/kubernetes/admin.conf with correct certificate-authority, server, client-certificate, client-key

(OPTIONAL if kubectl client is required).
   # Set the Kubernetes version as found in the UCP Dashboard or API
   export k8sversion=v1.8.11
   # Get the kubectl binary.
   curl -LO https://storage.googleapis.com/kubernetes-release/release/$k8sversion/bin/linux/amd64/kubectl
   # Make the kubectl binary executable.
   chmod +x ./kubectl
   # Move the kubectl executable to /usr/local/bin.
   sudo mv ./kubectl /usr/local/bin/kubectl

$ export KUBERNETES_SERVICE_HOST=<Master_Host>
$ export KUBERNETES_SERVICE_PORT=443
```

11. Dory installation on all hosts
```
$ sudo yum install wget
$ sudo yum intsall git
$ wget https://github.com/hpe-storage/python-hpedockerplugin/raw/master/dory_installer_v31
$ chmod u+x ./dory_installer
$ sudo ./dory_installer

Execute command in master host to run doryd.
$/usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/doryd  /etc/kubernetes/admin.conf hpe.com

To verify dory and doryd, below command can be used.
ls -l /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/        <to check dory installed necessary files>
/usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/hpe init      <to check connectivity status of dory>
/usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/hpe config    <to check doryd configurations>
```
**Note:- Once all setup completed then we can use login URL and credential received after UCP installation to access it from browser.** 



### Error & Solution

**Error-1:** FATA[0036] the following required ports are blocked on your host: 6443, 6444, 10250, 12376, 12378 - 12386.  Check your firewall settings

**Solution:**
```
$ for i in 179 443 2376 6443 6444 10250 12376 12378 12379 12380 12381 12382 12383 12384 12385 12386 12387 ; do
   echo adding $i to the firewall
   firewall-cmd --add-port=$i/tcp --permanent
done

$ firewall-cmd --reload
$ systemctl restart docker
```

**Error-2:**  Getting error related with "*.pem" file not found, while executing `export KUBECONFIG=/etc/kubernetes/admin.conf`.

**Solution:**
```
find required "*.pem" file in admin.conf and update correct path or move file to path, which is mentioned in admin.conf.
e.g.

mkdir -p /var/lib/docker/ucp/ucp-node-certs/                <<This path was mentioned in admin.conf but "*.pem" file was missing>>
cp /var/lib/docker/volumes/ucp-node-certs/_data/ca.pem /var/lib/docker/ucp/ucp-node-certs/ca.pem
cp /var/lib/docker/volumes/ucp-node-certs/_data/cert.pem /var/lib/docker/ucp/ucp-node-certs/cert.pem
cp  /var/lib/docker/volumes/ucp-node-certs/_data/key.pem /var/lib/docker/ucp/ucp-node-certs/key.pem
```

**Error-3:** Unable to see worker node in running state, after running join command on worker.

**Solution:**
```
Open port on worker:-
$ firewall-cmd --add-port=10250/tcp --permanent
$ firewall-cmd --reload

Open port on master:-
$ firewall-cmd --add-port=10250/tcp --permanent
$ firewall-cmd --add-port=10251/tcp --permanent
$ firewall-cmd --add-port=10252/tcp --permanent
$ firewall-cmd --reload

$ systemctl stop firewalld
$ systemctl start firewalld
```

**Error-4:** Pod getting stuck at "containerCreating" state with describe message as "-- MountVolume.SetUp succeeded for volume "default-token-phdh6"
Later goes in timeout."

**Solution:**
```
Possible solution can be others too but primary things to check is kubelet service of worker and master.
Since UCP have all services in container form, find and restart kubelet container on all nodes.
```

