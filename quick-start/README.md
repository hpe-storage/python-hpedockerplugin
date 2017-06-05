# Steps for Deploying the Managed Plugin 

HPE 3PAR/StoreVirtual Docker Volume Plugin is tested against 

- Docker 17.03 EE edition
- Ubuntu 16.04 (Xenial) and RHEL 7.3 

Setup etcd in a host following this instructions https://github.com/hpe-storage/python-hpedockerplugin/tree/master/quick-start#single-node-etcd-setup---install-etcd

This etcd container can run in the same host where the HPE Docker Volume plugin is installed.

Configure plugin for the appropriate storage system.

For 3PAR System , use this template https://github.com/hpe-storage/python-hpedockerplugin/blob/master/config/hpe.conf.sample.3par and create a file called hpe.conf in /etc/hpedockerplugin/hpe.conf

For StoreVirtual System, use this template https://github.com/hpe-storage/python-hpedockerplugin/blob/master/config/hpe.conf.sample.lefthand and create file called hpe.conf in /etc/hpedockerplugin/hpe.conf

Note: Template has different place holders for the storage system to be configured. In hpe.conf , parameter host_etcd_ip_address = <ip_address> needs to be replaced with the ip_address of the host where the etcd is started.

Install the plugin

On Ubuntu 16.04

``$ docker plugin install store/hpestorage/hpedockervolumeplugin:1.0 --alias hpe``

On RHEL 7.3
```
$ docker plugin install –-disable –-grant-all-permissions –-alias hpe store/hpestorage/hpedockervolumeplugin:1.0 
$ docker plugin set hpe glibc_libs.source=/lib64 
$ docker plugin enable hpe
```

Confirm the plugin is successfully installed by

`$ docker plugin ls`

## Examples of using the HPE Volume Plugin


To Create a volume
```
$ docker volume create -d hpe --name db_vol -o size=10

```

To List Volumes 
```
$ docker volume ls

```
To Mount a volume 

```
$ docker run -it -v <volume>:/data1 --rm busybox /bin/sh
```

To remove a volume

```
$ docker volume remove <vol_name>

```


## Logs for the plugin will be in system logs (eg. /var/log/syslog in Ubuntu).

On RHEL 7.3 issue ``journalctl -f -u docker.service`` to get the plugin logs.

On Ubuntu

grep for the `plugin id` in the logs , where the `plugin id` can be got by

``$ docker-runc list``



# Deploying the HPE Docker Volume Plugin as a Docker Container

Starting with release v1.1.0 the plugin can now be deployed as a Docker Container. 

NOTE: Manual deployment is NOT supported with releases v1.1.0 and beyond.

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

Sample configration files for 3PAR and StoreVirtual Lefthand are located in
the **config/hpe.conf.sample.xxx** files.

3PAR iSCSI: **config/hpe.conf.sample.3par**

StoreVirtual Lefthand: **config/hpe.conf.sample.lefthand**

```
<starting from plugin folder>
cd config
cp <sample_file> hpe.conf
<edit hpe.conf>
```

Copy the edited configs into **/etc/hpedockerplugin/hpe.conf**.


#Running the hpedockerplugin with Docker Compose:

You can now start the hpedockerplugin using docker compose. Just do one of the following:

##Build and run the container image from source
1. git clone git@github.com:hpe-storage/python-hpedockerplugin.git
2. cd python-hpedockerplugin
3. run ./containerize.sh
4. tag the image (e.g. docker tag <image-id> myhpedockerplugin:latest
5. Create an hpe.conf file and place it in the directory /etc/hpedockerplugin
6. copy and edit the docker-compose.yml.example as appropriate to your env
7. docker-compose up -d

##Run the container using an existing hpedockerplugin container image
1. Create an hpe.conf file and place it in the directory /etc/hpedockerplugin
2. copy and edit the docker-compose.yml.example as appropriate to your env (with appropriate image name)
3. docker-compose up -d

You should now have a containerized version of the hpedockerplugin running.

##Restarting the plugin
IMPORTANT NOTE: The /run/docker/plugins/hpe/hpe.sock and /run/docker/plugins/hpe/hpe.sock.lock files are not automatically removed when you stop the container. Therefore, these files will need to be removed between each run of the plugin.

#Running the hpedockerplugin on different linux distros:

Make sure to set **MountFlags=shared** in the docker.service. This is required to ensure the hpedockerplugin can write to /hpeplugin

1. CentOS/RHEL: You now need to bind mount /etc/iscsi/initiatorname.iscsi in the docker compose file. The Alpine linux based version of the container does not come with an iscsi initiator. Therefore, you must bind mount an iscsi initiator for the plugin to work properly. 

2. CoreOS: make sure to also bind mount /lib/modules. Otherwise, you'll get the following error in the hpedockerpluin logs:

iscsiadm: initiator reported error (12 - iSCSI driver not found. Please make sure it is loaded, and retry the operation)

