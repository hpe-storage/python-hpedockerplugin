## System Requirements

The plugin is supported on Ubuntu 14.04 and 16.04.

Docker 1.11 and newer is supported.

Python 2.7 is supported.

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

## Setup

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

If using Ubuntu 14.04 modify the **/etc/docker/default** file by adding
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
--name etcd quay.io/coreos/etcd \
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

#### Install os-brick

Currently master os-brick is required for proper functioning of the plugin.

```
sudo pip install os-brick
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

#### Running plugin unit tests

Run the following commands to run the plugin unit tests:

```
cd test
sudo trial test_hpe_plugin.py
```

Use the following command to check for PEP8 violations in the plugin:

```
tox
```
