# Source Availability
- Source for the entire HPE 3PAR Volume Plugin for Docker is present in plugin_v2 branch of this repository.
- Source for paramiko is present under https://github.com/hpe-storage/python-hpedockerplugin/tree/master/paramiko_src 

# Steps for Deploying the Managed Plugin (HPE 3PAR Volume Plug-in for Docker) 

HPE 3PAR Docker Volume Plugin for Docker is tested against: 

- Docker EE release version 17.03 and 17.06
- Ubuntu 16.04 (Xenial), RHEL 7.4 and CentOS 7.3

#### Feature Matrix for Managed plugin / HPE 3PAR Volume Plug-in for Docker :

store/hpestorage/hpedockervolumeplugin:2.1
- ```
   Support for creating volumes of type thin, dedup, full, compressed volumes, snapshots, clones, 
   QoS, snapshot mount, mount_conflict_delay, and multiple container access for a volume on same node.
   Plugin supports both iscsi and FC drivers.
   ```

#### **Prerequisite packages to be installed on host OS:**
```
   on Ubuntu 16.04:
   
   sudo apt-get install -y open-iscsi multipath-tools
   $ systemctl daemon-reload
   $ systemctl restart open-iscsi multipath-tools docker
   
   on RHEL 7.4 and CentOS 7.3:
   
   yum install -y iscsi-initiator-utils device-mapper-multipath
   # configure /etc/multipath.conf and run below commands
   create /etc/multipath.conf based on instructions in: https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/multipath-managed-plugin.md
   Configure the docker system service 
   - set the value of Mount Flags 
      MountFlags=shared (default is slave) in file  /usr/lib/systemd/system/docker.service (in case of RHEL)
   - restart the docker daemon using
      $ systemctl daemon-reload
      $ systemctl restart docker.service
   
      $ systemctl enable iscsid multipathd
      $ systemctl start iscsid multipathd
   
```
#### Steps:

- These are the prerequisite packages to be installed on host OS:
https://github.com/hpe-storage/python-hpedockerplugin/blob/master/quick-start/README.md#prerequisite-packages-to-be-installed-on-host-os


- Run etcd container

   Setup etcd in a host following this instructions https://github.com/hpe-storage/python-hpedockerplugin/tree/master/quick-start#run-etcd-container-or-cluster

  **Note: This etcd container can run in the same host where the HPE Docker Volume plugin is installed.**

- Configure hpe.conf for Managed plugin.

For 3PAR iSCSI plugin, use this template https://github.com/hpe-storage/python-hpedockerplugin/blob/master/config/hpe.conf.sample.3parISCSI and create a file called hpe.conf in /etc/hpedockerplugin/hpe.conf

For 3PAR FC plugin, use this template https://github.com/hpe-storage/python-hpedockerplugin/blob/master/config/hpe.conf.sample.3parFC and create a file called hpe.conf in /etc/hpedockerplugin/hpe.conf

**Note: Template has different place holders for the storage system to be configured. In hpe.conf , parameter host_etcd_ip_address = <ip_address> needs to be replaced with the ip_address of the host where the etcd is started.**

**Note: Before enabling the plugin user needs to make sure that**
- etcd container is in running state.
- Host and 3PAR array has proper iSCSI connectivity if plugin's iscsi driver needs to be used.
- FC plugin requires proper zoning between the docker host(s) and the 3PAR Array. 

**Execute below commands to install the plugin on Ubuntu 16.04**

```

$ docker plugin install store/hpestorage/hpedockervolumeplugin:<version>  --disable --alias hpe
# certs.source should be set to the folder where the certificates for secure etcd is configured , otherwise
# please default the setting to a valid folder in the system.
$ docker plugin set hpe certs.source=/tmp
$ docker plugin enable hpe

```

**Execute below commands to install the plugin on RHEL 7.4 and CentOS 7.3**

```

$ docker plugin install store/hpestorage/hpedockervolumeplugin:<version> –-disable –-alias hpe 

# certs.source should be set to the folder where the certificates for secure etcd is configured , otherwise
# please default the setting to a valid folder in the system.
# For unsecure etcd, any valid folder in the docker host can be given for certs.source

$ docker plugin set hpe glibc_libs.source=/lib64 certs.source=/tmp
$ docker plugin enable hpe

```

**Confirm the plugin is successfully installed by**

`$ docker plugin ls`


## Examples of using the HPE 3PAR Volume Plug-in for Docker

To Create a volume
```
$ docker volume create -d hpe --name db_vol -o size=10
```

To List Volumes 
```
$ docker volume ls
```

To Create a snapshot or virtualCopy
```
$ docker volume create -d hpe --name db_vol_snap -o virtualCopyOf=db_vol
```

To Manage a volume or snapshot
```
$ docker volume create -d hpe --name db_vol_snap -o importVol=<3par_vol|3par_snap>
```

To Create a Clone
```
$ docker volume create -d hpe --name db_vol_clone -o cloneOf=db_vol
```

To apply existing QoS setting of VVSet on new volume being created
```
$ docker volume create -d hpe --name db_vol_new -o qos-name=<existing_vvsetname_in_3par>
```
Note: Here Volume and vvset should be in same domain

To Mount a volume 
```
$ docker run -it -v <volume>:/data1 --rm --volume-driver hpe busybox /bin/sh
```

To Mount a snapshot
```
$ docker run -it -v db_vol_snap:/data1 --rm --volume-driver hpe busybox /bin/sh
```

To remove a volume
```
$ docker volume rm db_vol
```

To remove a snapshot
```
$ docker volume rm db_vol_snap
```

To inspect a volume or snapshot
```
$ docker volume inspect <vol_name or snapshot_name>
```

## Logs for the plugin 

On Ubuntu, grep for the `plugin id` in the logs , where the `plugin id` can be identified by:

``$ docker-runc list``

Plugin logs will be available in system logs (eg. /var/log/syslog on Ubuntu).

On RHEL and CentOS, issue ``journalctl -f -u docker.service`` to get the plugin logs.
or `` /var/log/messages ``



## Known limitations
- List of issues around the containerized version of the plugin/Managed plugin is present in https://github.com/hpe-storage/python-hpedockerplugin/issues 

- ``$ docker volume prune`` is not supported for volume plugin, instead use ``$docker volume rm $(docker volume ls -q -f "dangling=true") `` to clean up orphaned volumes.

- Shared volume support is present for containers running on the same host.

- For upgrading the plugin from older version 2.0 or 2.0.2 to 2.1 user needs to unmount all the volumes and follow the standard
 upgrade procedure described in docker guide. 
 
- Volumes created using older plugins (2.0.2 or below) do not have snap_cpg associated with them, hence when the plugin is upgraded to      2.1 and user wants to perform clone/snapshot operations on these old volumes, he/she must set the snap_cpg for the
   corresponding volumes using 3par cli or any tool before performing clone/snapshot operations.

- While inspecting a snapshot, its provisioning field is set to that of parent volume's provisioning type. In 3PAR however, it is shown as 'snp'.

- Mounting a QoS enabled volume can take longer than a volume without QoS for both FC and iSCSI protocol.

- For a cloned volume with the same size as source volume, comment field won’t be populated on 3PAR.

- User not allowed to manage attached 3PAR legacy volume

- User needs to explicitly manage all the child snapshots, until which managed parent volume cannot be deleted

- User cannot manage already managed volume by other docker host(i.e. volume thats start with 'dcv-')

## Docker cli commands for various operations are listed in link
   https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/usage.md


```
   Note: 3PAR volumes can be created in docker environment using 2 approces 
   1. using plugin form (Managed Pugin) as shown in above steps or 
   2. using as a container image called as containerized plugin as shown below
   Managed plugin is supported only on docker 1.13 onwards, so to use the plugin on
   older releases of docker use this containerized plugin
```

# Steps for Deploying the Containerized Plugin(HPE 3PAR Volume Plug-in for Docker as Docker container) 

### For running the Containerized Plugin under Openshift 3.7 / Kubernetes 1.7 please follow these steps as documented in shared file
    https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/OpenShift_Kubernetes_documentation.docx
    
` Below are the steps for running etcd and Containerized Plugin. `

#### Steps:

- reload docker daemon after configuring MountFlags
```
Configure the docker system service 
- MountFlags=shared (default is slave) in file  /usr/lib/systemd/system/docker.service (in case of RHEL)
- restart the docker daemon using
      systemctl daemon-reload
      systemctl restart docker.service
```

-  These are prerequisite packages to be installed on host OS:
https://github.com/hpe-storage/python-hpedockerplugin/blob/master/quick-start/README.md#prerequisite-packages-to-be-installed-on-host-os


- run the etcd container/ cluster of containers https://github.com/hpe-storage/python-hpedockerplugin/blob/master/quick-start/README.md#run-etcd-container-or-cluster

- set up hpe.conf and have a proper connectivity setup from host to 3PAR array https://github.com/hpe-storage/python-hpedockerplugin/tree/master/quick-start#setup-the-plugin-configuration-file

- use docker-compose to run the containerized plugin https://github.com/hpe-storage/python-hpedockerplugin/tree/master/quick-start#there-are-2-ways-to-get-the-containerized-plugin-on-system


## Run etcd container OR cluster 
**If you plan to run a container orchestration service (such as Docker UCP or Kubernetes) in a cluster of systems then refer to the etcd cluster setup link given below.** These orchestration services typically already have setup instructions for an etcd cluster, so there is no need to create a separate etcd cluster in these cases. The plugin can safely share access to the same etcd cluster being used by the orchestration technology.

**Note:** For quick start purpose user can create a single node etcd setup as shown in below example but for the production use case user can go for creating etcd cluster or High Availability etcd cluster.

#### **These steps are for a single node setup only.:**

First create an export for your local IP:
```
export HostIP="<your host IP>"
```
Then run the following command to create an etcd container in Docker:
```
sudo docker run -d -v /usr/share/ca-certificates/:/etc/ssl/certs -p 4001:4001 \
-p 2380:2380 -p 2379:2379 \
--name etcd quay.io/coreos/etcd:v2.2.0 \
-name etcd0 \
-advertise-client-urls http://${HostIP}:2379,http://${HostIP}:4001 \
-listen-client-urls http://0.0.0.0:2379,http://0.0.0.0:4001 \
-initial-advertise-peer-urls http://${HostIP}:2380 \
-listen-peer-urls http://0.0.0.0:2380 \
-initial-cluster-token etcd-cluster-1 \
-initial-cluster etcd0=http://${HostIP}:2380 \
-initial-cluster-state new
```
#### **For more information on setting up an etcd cluster see:**

https://coreos.com/etcd/docs/latest/v2/docker_guide.html - instructions for etcd under Docker

Note: The etcd version used here is v2.2.0. Versions of etcd beyond v2.x require changes to the above command.

#### **Setting up Etcd cluster for High Availability see:**

Support for Etcd cluster with multiple Etcd hosts has been tested against Docker 17.06 EE on Ubuntu 16.04.

For setting up etcd client with cluster members, configure host_etcd_ip_address in hpe.conf in this below format where each member's ip:port is given with comma as delimiter. For example,
```
host_etcd_ip_address = 10.50.180.1:3379,10.50.164.1:3379,10.50.198.1:3379
```

In Docker Swarm mode, etcd cluster will be created between manager nodes and etcd clients will be workers nodes where volume plugin will be installed.

Example configuration for secure etcd setup is given in this link - https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/etcd_cluster_setup.md


## Setup the plugin Configuration file

Sample configuration files for 3PAR iSCSI and FC

3PAR iSCSI: https://github.com/hpe-storage/python-hpedockerplugin/blob/plugin_v2/config/hpe.conf.sample.3parISCSI

3PAR FC Template : https://github.com/hpe-storage/python-hpedockerplugin/blob/plugin_v2/config/hpe.conf.sample.3parFC

```
<starting from plugin folder>
cd config
cp <sample_file> hpe.conf
<edit hpe.conf>
```

Copy the edited configs into **/etc/hpedockerplugin/hpe.conf**.


## There are 2 ways to get the containerized plugin on system
1. Using the clone and building the image locally
```
git clone https://github.com/hpe-storage/python-hpedockerplugin.git ~/container_code
cd ~/container_code
git checkout plugin_v2
./containerizer.sh
```
Observe the built container image by `docker images` command

```
root@worker1:~/patch_201/python-hpedockerplugin# docker images
REPOSITORY                           TAG                 IMAGE ID            CREATED             SIZE
hpe-storage/python-hpedockerplugin   plugin_v2          9b540a18a9b2        4 weeks ago         239MB
```

2. Using prebuild images available on docker hub
```
In docker-compose.yml keep image: hpestorage/legacyvolumeplugin:2.1
```

- Sample docker-compose.yml file for Ubuntu:
On **Ubuntu systems** - copy the file https://github.com/hpe-storage/python-hpedockerplugin/blob/plugin_v2/quick-start/docker-compose.yml.example as docker-compose.yml 

- Substitute the  `image: <image>` in docker-compose.yml with the name of the built image. `container_name: <container_name>` can be substituted by any user defined name.

- Sample docker-compose.yml file for RHEL/CentOS:
On **RHEL/CentOS systems** docker-compose.yml for creating containerized image using cloned repository in above example will be as shown in below example
``` 
hpedockerplugin:
  image: hpe-storage/python-hpedockerplugin:plugin_v2
  container_name: plugin_container
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
     - /opt/hpe/data:/opt/hpe/data:rshared
  ```

- Start the plugin container by `docker-compose -f docker-compose.yml up`
- create 2 symbolic links by using these steps
```
mkdir -p /run/docker/plugins/hpe
cd /run/docker/plugins/hpe
ln -s ../hpe.sock.lock  hpe.sock.lock
ln -s ../hpe.sock  hpe.sock

Make sure you are in the location of the docker-compose.yml file
```	 
$ docker-compose up -d or
$ docker-compose up 2>&1 | tee /tmp/plugin_logs.txt
```
```
In case you are missing docker-compose, https://docs.docker.com/compose/install/#install-compose

$ curl -x -L https://github.com/docker/compose/releases/download/1.21.0/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
$ sudo chmod +x /usr/local/bin/docker-compose

# Test the installation
$ docker-compose --version
docker-compose version 1.21.0, build 1719ceb
```

- You should be able to do `docker volume` operations like `docker volume create -d hpe --name sample_vol -o size=1`

## Restarting the plugin
- docker stop <container_id_of_plugin>
- IMPORTANT NOTE: The /run/docker/plugins/hpe.sock and /run/docker/plugins/hpe.sock.lock files are not automatically removed when you stop the container. Therefore, these files will need to be removed manually between each run of the plugin.
- docker start <container_id_of_plugin>
