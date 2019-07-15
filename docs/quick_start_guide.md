# Deployment methods for HPE 3PAR Volume Plugin-in 

## HPE 3PAR Docker volume Plugin can be deployed in following methods: 

* [Ansible playbook to deploy the HPE 3PAR Volume Plug-in for Docker (RECOMMENDED)](/ansible_3par_docker_plugin)
* [Quick Start Guide for Standalone Docker environments](#docker)
* [Quick Start Guide for Kubernetes/OpenShift environments](#k8)


---

## Source Availability
- Source for the entire HPE 3PAR Volume Plugin for Docker is present in plugin_v2 branch of this repository.
- Source for paramiko is present under [/source/paramiko_src](/source/paramiko_src)

## Quick Start Guide for Standalone Docker environments <a name="docker"></a>

Steps for Deploying the Managed Plugin (HPE 3PAR Volume Plug-in for Docker) in a Standalone Docker environment

### **Prerequisite packages to be installed on host OS:**

#### RHEL/CentOS 7.3 or later:

1. Install the iSCSI (optional if you aren't using iSCSI) and Multipath packages

```
$ yum install -y iscsi-initiator-utils device-mapper-multipath
```

2. Configure `/etc/multipath.conf`

```
$ vi /etc/multipath.conf
```

>Copy the following into `/etc/multipath.conf`

```
defaults {
    polling_interval 10
    max_fds 8192
}

devices {
    device {
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

#### SLES12 SP3 or later:

1. Rebuild the initrd, otherwise the system may not boot anymore

```
$ dracut --force --add multipath
```

2. Configure `/etc/multipath.conf`

```
$ multipath -t > /etc/multipath.conf
```

3. Enable the iscsid and multipathd services

```
$ systemctl enable multipathd iscsid
$ systemctl start multipathd iscsid
```

Now the systems are ready to setup the HPE 3PAR Volume Plug-in for Docker.


### Next Steps:

### ETCD config

1. Export the Master Node IP address

```
export HostIP="<Master node IP>"
```

2. Run the following Docker command to create the HPE etcd container
>**NOTE:** etcd stores the HPE 3PAR volume metadata and is required for the plugin to function properly. If you have multiple instances of etcd running on the same Docker node, you will need to modify the default etcd ports (2379, 2380, 4001) and make the adjustment in the **hpe.conf** as well.

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

### HPE 3PAR Volume `Managed Plug-in` config

1. Add HPE 3PAR into `~/.ssh/known_hosts`

```
$ ssh -l username <3PAR IP Address>
```

2. Configure `hpe.conf` for Managed plugin.

```
$ vi /etc/hpedockerplugin/hpe.conf
```

For 3PAR iSCSI plugin, use this hpe.conf template
[/docs/config_examples/hpe.conf.sample.3parISCSI](/docs/config_examples/hpe.conf.sample.3parISCSI)

For 3PAR FC plugin, use this hpe.conf template
[/docs/config_examples/hpe.conf.sample.3parFC](/docs/config_examples/hpe.conf.sample.3parFC)

>Note: The template has different place holders for the storage system to be configured. The parameter host_etcd_ip_address = <ip_address>, in **/etc/hpedockerplugin/hpe.conf**, needs to be replaced with the ip_address of the host where etcd is running.

---

**IMPORTANT**

Before enabling the plugin, validate the following:

* etcd container is in running state.
* The host and 3PAR array has proper iSCSI connectivity if iSCSI is used
* Proper zoning between the docker host(s) and the 3PAR Array.

---

3. Run the following commands to install the plugin:


**RHEL/CentOS**

>version=2.1

```
$ docker plugin install store/hpestorage/hpedockervolumeplugin:<version> –-disable –-alias hpe
$ docker plugin set hpe glibc_libs.source=/lib64 certs.source=/tmp
$ docker plugin enable hpe
```

4. Confirm the plugin is successfully installed by

```
$ docker plugin ls

```

## Quick Start Guide for Kubernetes/OpenShift environments <a name="k8"></a>

There are two methods for installing the HPE 3PAR Volume Plug-in for Docker for Kubernetes/OpenShift environments:

1. [Ansible playbook to deploy the HPE 3PAR Volume Plug-in for Docker (**RECOMMENDED**)](/ansible_3par_docker_plugin/README.md)


2. [Install Guide for HPE 3PAR Volume Plug-in for Docker](/docs/manual_install_guide_hpe_3par_plugin_with_openshift_kubernetes.md)


## Usage <a name="usage"></a>

For usage go to:

[Usage](/docs/usage.md)
