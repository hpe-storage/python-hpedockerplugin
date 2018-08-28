# ansible_3par_docker_plugin

Ansible playbooks to install the HPE 3PAR Docker Volume plugin for use with Kubernetes/OpenShift environments

Requirements:

  - login to 3PAR to create known_hosts file
  - modify files/hpe.conf based on your environment configuration
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
