## Configuring HPE 3PAR Docker Volume Plugin for Docker EE 2.0

### Install OS (Ubuntu or CentOs) on all the nodes.

Follow the steps to install docker Engine (EE 2.0) on all the nodes.

### Install and enable containerized plugin on all the nodes.
    Use the latest hpe.conf file and docker-compose.yml (Sample docker-compose.yml below).

### Install UCP on master. (https://docs.docker.com/ee/ucp/admin/install/)
    a. Pull the latest version of UCP
       docker image pull docker/ucp:3.0.5
    b. Install UCP

```
docker container run --rm -it --name ucp \
  -v /var/run/docker.sock:/var/run/docker.sock \
  docker/ucp:3.0.5 install \
  --host-address <node-ip-address> --pod-cidr <    >\
  --interactive
```  
 
 Example:-
  
  `docker container run --rm -it --name ucp   -v /var/run/docker.sock:/var/run/docker.sock   docker/ucp:3.0.5 install   \
  --host-address  192.168.68.34   --pod-cidr 192.167.0.0/16 --interactive`

Admin Username:  {Set the user name}
Admin Password:  {Set the password}
  Confirm Admin Password: {Set the password}
  Additional aliases: {Press Enter OR specify additional aliases if required }
  Once the installation is complete ...It will display the login url 
  
- `mkdir -p /etc/kubernetes`
- `cp /var/lib/docker/volumes/ucp-node-certs/_data/kubelet.conf /etc/kubernetes/admin.conf`

- Modify /etc/kubernetes/admin.conf with correct certificate-authority, server, client-certificate, client-key
  
Follow all the steps to install dory/doryd on master node.

### OPTIONAL if kubectl client is required).
```
   # Set the Kubernetes version as found in the UCP Dashboard or API
   k8sversion=v1.8.11
   # Get the kubectl binary.
   curl -LO https://storage.googleapis.com/kubernetes-release/release/$k8sversion/bin/linux/amd64/kubectl
   # Make the kubectl binary executable.
   chmod +x ./kubectl
   # Move the kubectl executable to /usr/local/bin.
   sudo mv ./kubectl /usr/local/bin/kubectl

export KUBERNETES_SERVICE_HOST=192.168.68.41
export KUBERNETES_SERVICE_PORT=443
```

### Sample hpe.conf

```
[DEFAULT]
ssh_hosts_key_file = /root/.ssh/known_hosts
logging = DEBUG
hpe3par_debug = True
suppress_requests_ssl_warnings = False
host_etcd_ip_address = 192.168.68.41
host_etcd_port_number = 2379
hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver
hpe3par_api_url = https://192.168.67.7:8080/api/v1
hpe3par_username = 3paradm
hpe3par_password = 3pardata
san_login = 3paradm
san_ip = 192.168.67.7
san_password = 3pardata
hpe3par_cpg = FC_r6
hpe3par_snapcpg = FC_r6
hpe3par_iscsi_ips = 192.168.68.201, 192.168.68.203
mount_prefix = /var/lib/kubelet/plugins/hpe.com/3par/mounts/
hpe3par_iscsi_chap_enabled = True
#use_multipath = True
#enforce_multipath = True
mount_conflict_delay = 30
```


### Sample docker-compose.yml
```
hpedockerplugin:
 container_name: legacy_plugin
 image: dockerciuser/legacyvolumeplugin:plugin_v2
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
    - /lib/x86_64-linux-gnu:/lib64
    - /var/run/docker.sock:/var/run/docker.sock
    - /var/lib/kubelet/plugins/hpe.com/3par/mounts/:/var/lib/kubelet/plugins/hpe.com/3par/mounts:rshared
```
