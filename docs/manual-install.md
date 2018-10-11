## Manual Deployment Steps

Manual deployment is currently only supported with the v1.0.0 version of the plugin. Using these steps with versions starting at v1.1.0 is NOT supported.

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

This has to be followed by the below command so that whenever Docker service restarts, etcd is also restarted:
docker update --restart always etcd

It is highly recommended that existing etcd installations must also run the above update command to avoid manual restarts of etcd.

NOTE: If you want to save your etcd data you'll need to use the docker -v option to specify a local directory (or external volume) to save your data. In addition, if you are configuring an etcd cluster then you need to you "existing" instead of "new" if you want a specific node to rejoing an existing cluster.

For more information on setting up an etcd cluster see:

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
