## HPE Docker Volume Plugin

The HPE Docker Volume Plugin is open source software that provides persistent block storage for containerized applications. 

## HPE Docker Volume Plugin Overview
The following diagram illustrates the 


![HPE Docker Volume Plugin](docs/pics/HPE-DockerVolumePluginOverview.png "Storage Overview")

## System Requirements

The plugin is supported on Ubuntu 14.04 and 16.04.

Docker 1.11 and newer is supported.

Python 2.7 is supported.

etcd 2.x is supported.

Supported HPE 3PAR and StoreVirtual iSCSI storage arrays:

- OS version support for 3PAR (3.2.1 MU2 and beyond)
- OS version support for StoreVirtual (11.5 and beyond)

Supported HPE 3PAR and StoreVirtual clients:

- python-3parclient version 4.0.0 or newer
- python-lefthandclient version 2.0.0 or newer

## Features

HPE 3PAR capabilities(via Docker Volume opts):

- Size
- Flash cache
- Provisioning types (thin, full, dedup)

HPE StoreVirtual capabilities (via Docker Volume opts):

- Size
- Provisioning types (thin, full)

Support for iSCSI CHAP configuration

Support for secured etcd clusters

Support for Application Mobility across docker engine nodes

Support for Docker Compose and Docker Swarm

## Unsupported Operations

- Multiple attachments to the same volume is currently unsupported.

## Container-based Deployment steps

[See quickstart instructions](https://github.com/hpe-storage/python-hpedockerplugin/tree/alpine/quick-start)

## Manual Deployment Steps

NOTE: If you run the Container based deployment steps you do NOT need to run through the manual deployment steps below.

#### Install and upgrade needed packages

Run the following commands to install and update needed packages for
the plugin:

```
sudo apt-get install git build-essential libssl-dev libffi-dev python-dev python-pip open-iscsi
sudo pip install -U setuptools
sudo pip install --upgrade pip
```

#### Install Docker

Follow the steps listed here to install Docker:

https://docs.docker.com/engine/installation/linux/ubuntulinux/

If errors occur during the hello-word step a proxy needs to be added
to Docker.

If using Ubuntu 16.04 refer to the proxy section in the docker engine documentation at:

https://docs.docker.com/engine/admin/systemd/#http-proxy

If using Ubuntu 14.04 modify the **/etc/default/docker** file by adding
the following:

```
export http_proxy="http://<proxy>:<port>/"
```

Next, restart the Docker service:

```
sudo service docker restart
```

#### Install etcd

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

For more information on etcd:

https://github.com/coreos/etcd/releases/

Note: The etcd version used here is v2.2.0. Versions of etcd beyond v2.x require changes the the above command.

#### Install python-hpedockerplugin

Clone the python-hpedockerplugin using the following:

```
git clone https://github.com/hpe-storage/python-hpedockerplugin.git
```

Once cloned use pip to install the plugin:

```
cd python-hpedockerplugin
sudo python setup.py install
```

Use the following to remove the plugin:

```
sudo pip uninstall python-hpedockerplugin
```

#### Configure the plugin

Sample configration files for 3PAR and StoreVirtual Lefthand are located in
the **config/hpe.conf.sample.xxx** files.

3PAR iSCSI: **config/hpe.conf.sample.3par**

StoreVirtual Lefthand: **config/hpe.conf.sample.lefthand**

Copy one of the sample configs into **config/hpe.conf** and modify the
template with desired settings:

```
<starting from plugin folder>
cd config
cp <sample_file> hpe.conf
<edit hpe.conf>
```

## Starting the plugin

Start the HPE Native Docker Volume Plugin by running the following commands:

```
<starting from plugin folder>
cd hpedockerplugin
sudo twistd --python hpe_plugin_service.py
```

Currently you must use the following command to stop the service:

```
kill -9 <hpe plugin PID>
```

## Usage
The following are the currently supported actions that can be taken using the HPE Docker plugin.

#### Creating an HPE volume

```
sudo docker volume create -d hpe --name <vol_name>
```

There are several optional parameters that can be used during volume creation:

- size -- specifies the desired size in GB of the volume.
- provisioning -- specifies the type of provisioning to use (thin, full, dedup).
- flash-cache -- specifies whether flash cache should be used or not (True, False).

Note: Setting flash-cache to True does not gurantee flash-cache will be used. The backend system
must have the appropriate SSD setup configured, too.

The following is an example call creating a full provisioned, 50 GB volume:

```
sudo docker volume create -d hpe --name <vol_name> -o size=50 -o provisioning=full
```

Note -- The dedup provisioning and flash-cache options are only supported by the
3PAR StoreServ driver currently.

#### Deleting a volume

```
sudo docker volume rm <vol_name>
```

#### List volumes

```
sudo docker volume ls
```

#### Inspect a volume

```
sudo docker volume inspect <vol_name>
```

#### Mounting a volume

Use the following command to mount a volume and start a bash prompt:

```
sudo docker run -it -v <vol_name>:/<mount_point>/ --volume-driver hpe <image_name> bash
```

Note: If the volume does not exist it will be created.

The image used for mounting can be any image located on https://hub.docker.com/ or
the local filesystem. See https://docs.docker.com/v1.8/userguide/dockerimages/
for more details. 

#### Unmounting a volume

Exiting the bash prompt will cause the volume to unmount:

```
exit
```

The volume is still associated with a container at this point.

Run the following command to get the container ID associated with the volume:

```
sudo docker ps -a
```

Then stop the container:

```
sudo docker stop <container_id>
```

Next, delete the container:

```
sudo docker rm <container_id>
```

Finally, remove the volume:

```
sudo docker volume rm <vol_name>
```

## Troubleshooting

This section contains solutions to common problems that may arise during the setup and usage of the plugin.

#### SSH Host Keys File

Make sure the file path used for the ssh_hosts_key_file exists. The suggested default is the known hosts file located at /home/stack/.ssh/known_hosts but that may not actually exist yet on a system. The easiest way to create this file is to do the following:

$ ssh <username>@<3PAR or LeftHand storage array IP>

Where username is the username for the 3PAR or LeftHand storage array that will be used by the plugin. The IP portion is the IP of the desired storage array. These values are typically defined later in the configuration file itself.

#### Client Certificates for Secured etcd

If a secured etcd cluster is not desired the host_etcd_client_cert and host_etcd_client_key properties can be commented out safely. In the case where a secured etcd cluster is desired the two properties must point to the respective certificate and key files.

#### Debug Logging

Sometimes it is useful to get more verbose output from the plugin. In order to do this one must change the logging property to be one of the following values: INFO, WARN, ERROR, DEBUG.

## Contributors

This section describes steps that should be done when creating contributions for this plugin.

#### Running plugin unit tests

All contributions to the plugin must pass all unit and PEP8 tests.

Run the following commands to run the plugin unit tests:

```
cd test
sudo trial test_hpe_plugin.py
```

Use the following command to check for PEP8 violations in the plugin:

```
tox
```
