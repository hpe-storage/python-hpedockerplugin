## Manual Install Guide for Integration of HPE 3PAR Containerized Plugin with Rancher Kubernetes (ADVANCED)

* [Introduction](#introduction)
* [Before you begin](#before)
* [Deploying the HPE 3PAR Volume Plug-in in Kubernetes](#deploying)
  * [Configuring etcd](#etcd)
  * [Installing the HPE 3PAR Volume Plug-in](#installing)
* [Usage](#usage)
---

### Introduction <a name="introduction"></a>
This document details the installation steps in order to get up and running quickly with the HPE 3PAR Volume Plug-in for Docker within a Rancher Kubernetes environment on SLES.

## Before you begin <a name="before"></a>
* You need to have a basic knowledge of containers

**NOTE**
  * Managed Plugin is not supported for Kubernetes

## Deploying the HPE 3PAR Volume Plug-in in Kubernetes <a name="deploying"></a>

Below is the order and steps that will be followed to deploy the **HPE 3PAR Volume Plug-in for Docker (Containerized Plug-in) within a Kubernetes** environment.

Let's get started.

For this installation process, login in as **root**:

```bash
$ sudo su -
```

### Configuring etcd <a name="etcd"></a>

**Note:** For this quick start quide, we will be creating a single-node **etcd** deployment, as shown in the example below, but for production, it is **recommended** to deploy a High Availability **etcd** cluster.

For more information on etcd and how to setup an **etcd** cluster for High Availability, please refer:
[/docs/advanced/etcd_cluster_setup.md](/docs/advanced/etcd_cluster_setup.md)

1. Export the Kubernetes/OpenShift `Master` node IP address
```
$ export HostIP="<Master node IP>"
```

2. Run the following to create the `etcd` container.


>**NOTE:** This etcd instance is separate from the **etcd** deployed by Kubernetes/OpenShift and is **required** for managing the **HPE 3PAR Volume Plug-in for Docker**. We need to modify the default ports (**2379, 4001, 2380**) of the **new etcd** instance to prevent conflicts. This allows two instances of **etcd** to safely run in the environment.`

```yaml
sudo docker run -d -v /usr/share/ca-certificates/:/etc/ssl/certs -p 40010:40010 \
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

### Installing the HPE 3PAR Volume Plug-in <a name="installing"></a>

1. Rebuild the initrd, otherwise the system may not boot anymore

```
$ dracut --force --add multipath
```

2. Configure /etc/multipath.conf

```
$ multipath -t > /etc/multipath.conf
```

3. Enable the multipathd services

```
$ systemctl enable multipathd
$ systemctl start multipathd
```

4. Setup the Docker plugin configuration file

```
$ mkdir –p /etc/hpedockerplugin/
$ cd /etc/hpedockerplugin
$ vi hpe.conf
```

>Copy the contents from the sample hpe.conf file, based on your storage configuration for either iSCSI or Fiber Channel:

>##### HPE 3PAR iSCSI:
>
>[/docs/config_examples/hpe.conf.sample.3parISCSI](/docs/config_examples/hpe.conf.sample.3parISCSI)


>##### HPE 3PAR Fiber Channel:
>
>[/docs/config_examples/hpe.conf.sample.3parFC](/docs/config_examples/hpe.conf.sample.3parFC)

> Note: Also add mount_prefix in hpe.conf to /var/lib/rancher/
```
mount_prefix = /var/lib/rancher/
```

5. Use Docker Compose to deploy the HPE 3PAR Volume Plug-In for Docker (Containerized Plug-in) from the pre-built image available on Docker Hub:

```
$ cd ~
$ vi docker-compose.yml
```

> Copy the content below into the `docker-compose.yml` file

```
hpedockerplugin:
  image: hpestorage/legacyvolumeplugin:3.1
  container_name: plugin_container
  net: host
  restart: always
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
     - /var/lib/rancher:/var/lib/rancher:rshared
     - /usr/lib64:/usr/lib64
```

>Save and exit

> **NOTE:** Before we start the HPE 3PAR Volume Plug-in container, make sure etcd is running.
>
>Use the Docker command: `docker ps -a | grep -i etcd_hpe`

6. Start the HPE 3PAR Volume Plug-in for Docker (Containerized Plug-in)

>Make sure you are in the location of the `docker-compose.yml` filed

```
$ docker-compose up -d
```

>**NOTE:** In case you are missing `docker-compose`, https://docs.docker.com/compose/install/#install-compose
>
```
$ curl -x 16.85.88.10:8080 -L https://github.com/docker/compose/releases/download/1.21.0/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
$ sudo chmod +x /usr/local/bin/docker-compose
```
>
>Visit https://docs.docker.com/compose/install/#install-compose for latest curl details
>
>Test the installation:
```
$ docker-compose --version
docker-compose version 1.21.0, build 1719ceb
```
> Re-run step 6

7. Success, you should now be able to test docker volume operations like:

```
$ docker volume create -d hpe --name sample_vol -o size=
```

8. Start Rancher Server

```
$ docker run -d --restart=unless-stopped  -p 8080:80 -p 8443:443  rancher/rancher:v2.1.6
```
> Launch browser and open https://<HostIP>:8443/ and set the password
	
9. Create a cluster with option "From my own existing nodes"

> Wait for the cluster to become active

10. Create a file ~/.kube/config. Navigate to **Cluster -> Kubeconfig file** and copy file content to add into ~/.kube/config

```
$ vi ~/.kube/config
```

11. Add kubectl binary on the host to run kubectl commands

```
$ docker ps | grep rancher-agent 
$ docker cp <racher-agent cont id>:/usr/bin/kubectl /tmp
$ cp /tmp/kubectl /usr/bin/ 
$ chmod +x /usr/bin/kubectl
```
> SLES doesn't have a kubectl binary be default to install/execute. To verify whether kubectl is installed correctly, run command
```
$ kubectl version
```
> This must show correct output with client and server versions. Same can be verified from **Cluster -> Launch kubectl* -> kubectl version*

12. Install the HPE 3PAR FlexVolume driver

```
$ wget https://github.com/hpe-storage/python-hpedockerplugin/raw/master/dory_installer
$ chmod u+x ./dory_installer
$ sudo ./dory_installer
```

13. Confirm HPE 3PAR FlexVolume driver installed correctly

```
$ ls -l /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/
-rwxr-xr-x. 1 docker docker 47046107 Apr 20 06:11 doryd
-rwxr-xr-x. 1 docker docker  6561963 Apr 20 06:11 hpe
-rw-r--r--. 1 docker docker      237 Apr 20 06:11 hpe.json
```

14. Copy the HPE 3PAR FlexVolume dynamic provisioner to volume plugin directory being used by kubelet container in Rancher

```
$ cp -R /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/ /var/lib/kubelet/volumeplugins/
```

>For more information on the HPE FlexVolume driver, please visit this link:
>
>https://github.com/hpe-storage/dory/

15. Repeat steps 1-14 on all worker nodes. **Steps 8, 9 and 11 only needs to be ran on the Master node.**

>**Upon successful completion of the above steps, you should have a working installation of Rancher-Kubernetes integrated with HPE 3PAR Volume Plug-in for Docker on SLES**

## Usage <a name="usage"></a>

For usage go to:

[Usage](/docs/usage.md)
