# ansible_3par_docker_plugin

These are Ansible playbooks to automate the install of the HPE 3PAR Docker Volume Plug-in for Docker for use within Kubernetes/OpenShift environments.

If you are not using Kubernetes or OpenShift, we recommend you take a look at the [Quick Start guide](https://github.com/budhac/python-hpedockerplugin/blob/master/docs/quick_start_guide.md) for using the HPE 3PAR Docker Volume Plug-in in a standalone Docker environment.

### Getting Started

These playbooks perform the following tasks on the Master/Slave nodes as defined in the Ansible hosts file.
* Configure the Docker Services for the HPE 3PAR Docker Volume Plug-in
* Deploys a 3-node Highly Available etcd cluster
* Deploys the config files (iSCSI or FC) to support your environment
* Installs the HPE 3PAR Docker Volume Plug-in (Containerized version) for Kubernetes/OpenShift
* Deploys the HPE FlexVolume Drivers

### Prerequisites:

  - login to 3PAR to create known_hosts file
  - modify files/hpe.conf ([iSCSI](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/files/iSCSI_hpe.conf) or [FC](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/files/FC_hpe.conf)) based on your HPE 3PAR Storage array configuration. An example can be found here. [sample_hpe.conf](https://github.com/budhac/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/files/sample_hpe.conf)
  - modify hosts file to match your cluster setup

Run
```
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```

**Make sure proxy and no_proxy are configured correctly**

<br><br>


# Known Issues

Ansible on some Linux Distros (i.e. CentOS and Ubuntu) may throw an error about missing the `docker` module.

```
TASK [run etcd container] ******************************************************************************************************************************************
fatal: [192.168.1.35]: FAILED! => {"changed": false, "msg": "Failed to import docker-py - No module named docker. Try `pip install docker-py`"}
```

Run:

```
pip install docker
```

-----------------------------------------------------------------------------------

On Ansible 2.6 and later, per https://github.com/ansible/ansible/issues/42162, `docker-py` has been deprecated and when running the Ansible playbook, you may see the following error:

```
docker_container: create_host_config() got an unexpected keyword argument 'init'
```

`docker-py` is no longer supported and has been deprecated in favor of the `docker` module.

If `docker-py` is installed, run:

```
pip uninstall docker-py
```

Run:

```
pip install docker
```
