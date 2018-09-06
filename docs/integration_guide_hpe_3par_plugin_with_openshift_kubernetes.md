## Install Guide for Integration of HPE 3PAR Containerized Plugin with RedHat OpenShift / Kubernetes

## Table of contents
* [Introduction](#introduction)
* [Before you begin](#before)
* [Support Matrix for Kubernetes and Openshift 3.7](#support)
* [Deploying the HPE 3PAR Volume Plug-in in Kubernetes/OpenShift](#deploying)
  * [Configuring etcd](#etcd)
  * [Installing the HPE 3PAR Volume Plug-in](#installing)
* [Usage](#usage)
* [Appendix](#appendix)
  * [Restarting the Plugin](#restart)
  * [More information](#info)


### Introduction <a name="introduction"></a>
This document details the installation steps in order to get up and running quickly with the HPE 3PAR Volume Plug-in for Docker within a Kubernetes 1.7/Openshift 3.7 environment.

## Before you begin <a name="before"></a>
* You need to have a basic knowledge of containers

* You should have Kubernetes or OpenShift deployed within your environment. If you want to learn how to deploy Kubernetes or OpenShift, please refer to the documents below for more details.

  * Kubernetes https://kubernetes.io/docs/setup/independent/create-cluster-kubeadm/

  * OpenShift https://docs.openshift.org/3.7/install_config/install/planning.html

## Support Matrix for Kubernetes and Openshift 3.7 <a name="support"></a>

| platforms | Support for Containerized Plugin | Docker Engine Version | HPE 3PAR OS version |
|---------------------|---------------|--------|--------|--------|
|Kubernetes 1.6.13 | Yes | 1.12.6 |3.2.2 MU6+ P107 3.3.1 MU1, MU2 |
|Kubernetes 1.7.6 | Yes | 1.12.6 | 3.2.2 MU6+ P107 3.3.1 MU1, MU2 |
| Kubernetes 1.8.9 | Yes | 17.06 | 3.2.2 MU6+ P107 3.3.1 MU1, MU2 |
| Kubernetes 1.10.3 | Yes | 17.03 | 3.2.2 MU6+ P107 3.3.1 MU1, MU2 |
| OpenShift 3.7 RPM based installation (Kubernetes 1.7.6) | Yes | 1.12.6 | 3.2.2 MU6+ P107 3.3.1 MU1, MU2 |

**NOTE**
  * Managed Plugin is not supported for Kubernetes or Openshift 3.7

  * The install of OpenShift for this paper was done on RHEL 7.4. Other versions of Linux may not be supported.

## Deploying the HPE 3PAR Volume Plug-in in Kubernetes/OpenShift <a name="deploying"></a>

Below is the order and steps that will be followed to deploy the **HPE 3PAR Volume Plug-in for Docker (Containerized Plug-in) within a Kubernetes 1.7/OpenShift 3.7** environment.

Let's get started.

For this installation process, login in as **root**:

```bash
$ sudo su -
```

### Configuring etcd <a name="etcd"></a>

**Note:** For this quick start quide, we will be creating a single-node **etcd** deployment, as shown in the example below, but for production, it is **recommended** to deploy a High Availability **etcd** cluster.

For more information on etcd and how to setup an **etcd** cluster for High Availability, please refer:
https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/etcd_cluster_setup.md

1. Export the Kubernetes/OpenShift `Master` node IP address

```
$ export HostIP="<Master node IP>"
```

2. Run the following to create the `etcd` container.


>**NOTE:** This etcd instance is separate from the **etcd** deployed by Kubernetes/OpenShift and is **required** for managing the **HPE 3PAR Volume Plug-in for Docker**. We need to modify the default ports (**2379, 4001, 2380**) of the **new etcd** instance to prevent conflicts. This allows two instances of **etcd** to safely run in the environment.`

```yaml
sudo docker run -d -v /usr/share/ca-certificates/:/etc/ssl/certs -p 40010:40010 \
-p 23800:23800 -p 23790:23790 \
--name etcd quay.io/coreos/etcd:v2.2.0 \
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

> **NOTE:** This section assumes that you already have **Kubernetes** or **OpenShift** deployed in your environment, in order to run the following commands.

1. Install the iSCSI and Multipath packages

```
$ yum install -y iscsi-initiator-utils device-mapper-multipath
```

2. Configure /etc/multipath.conf

```
$ vi /etc/multipath.conf
```

>Copy the following into /etc/multipath.conf

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
$ systemctl enable iscsid multipathd
$ systemctl start iscsid multipathd
```

4. Configure `MountFlags` in the Docker service to allow shared access to Docker volumes

```
$ vi /usr/lib/systemd/system/docker.service
```

>Change **MountFlags=slave** to **MountFlags=shared** (default is slave)
>
>Save and exit

5. Restart the Docker daemon

```
$ systemctl daemon-reload
$ systemctl restart docker.service
```

6. Setup the Docker plugin configuration file

```
$ mkdir –p /etc/hpedockerplugin/
$ cd /etc/hpedockerplugin
$ vi hpe.conf
```

>Copy the contents from the sample hpe.conf file, based on your storage configuration for either iSCSI or Fiber Channel:


## Usage <a name="usage"></a>


## Appendix <a name="appendix"></a>


#### Restarting the Plugin <a name="restart"></a>


### More Information <a name="info"></a>  
