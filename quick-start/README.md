# Deploying the HPE Docker Volume Plugin as a Docker Container

## Single node etcd setup - Install etcd
These steps are for a single node setup only. If you plan to run a container orchestration service (such as Docker UCP or Kubernetes) in a cluster of systems then refer to the etcd cluster setup below. These orchestration services typically already have setup instructions for an etcd cluster, so there is no need to create a separate etcd cluster in these cases. The plugin can safely share access to the same etcd cluster being used by the orchestration technology.

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
For more information on setting up an etcd cluster see:

https://coreos.com/etcd/docs/latest/v2/docker_guide.html - instructions for etcd under Docker

Note: The etcd version used here is v2.2.0. Versions of etcd beyond v2.x require changes to the above command.

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


## Building the container image
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

- On Ubuntu systems - copy the file https://github.com/hpe-storage/python-hpedockerplugin/blob/plugin_v2/quick-start/docker-compose.yml.example as docker-compose.yml 
- On RHEL/CentOS  system - copy the file https://github.com/hpe-storage/python-hpedockerplugin/blob/plugin_v2/quick-start/docker-compose.yml.rhel.example as docker-compose.yml
- Substitute the  `image: <image>` in docker-compose.yml with the name of the built image. `container_name: <container_name>` can be substituted by any user defined name.

- Sample docker-compose.yml 
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

```

- You should be able to do `docker volume` operations like `docker volume create -d hpe --name sample_vol -o size=1`

##Restarting the plugin

IMPORTANT NOTE: The /run/docker/plugins/hpe/hpe.sock and /run/docker/plugins/hpe/hpe.sock.lock files are not automatically removed when you stop the container. Therefore, these files will need to be removed between each run of the plugin.

