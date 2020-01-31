### Introduction to Containers & Orchestration
Originally developed by Google, Kubernetes is an open-source container orchestration platform designed to automate the deployment, scaling, and management of containerized applications.

OpenShift is a family of containerization software developed by Red Hat. Its flagship product is the OpenShift Container Platform—an on-premises platform as a service built around Docker containers orchestrated and managed by Kubernetes on a foundation of Red Hat Enterprise Linux.

### Overview of HPE Volume Plugin for Docker 
The following diagram illustrates the HPE Docker Volume Plugin configured on multiple hosts in a Docker cluster. The plugin is a part of Docker Engine Managed Plugin System.

![](https://github.com/sonawane-shashikant/python-hpedockerplugin/blob/master/docs/img/HPE-DockerVolumePlugin-Overview.png)
HPE Docker Volume plugin is being used in both Kubernetes and  OpenShift environment.

![](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/img/3PAR_k8_design_diagram_75.png)

This [SPOC](https://spock.corp.int.hpe.com/spock/utility/document.aspx?docurl=Shared%20Documents/hw/3par/3par_volume_plugin_for_docker.pdf) page shows the release-wise support matrix for HPE Docker Volume plugin.

### Automated Ansible Installer for HPE 3PAR and HPE Primera Volume Plug-in for Docker

* These are Ansible playbooks to automate the install of the HPE 3PAR Docker Volume Plug-in for Docker for use within standalone docker environment or Kubernetes/OpenShift environments.
```
NOTE: The Ansible installer only supports Ubuntu/RHEL/CentOS. 
If you are using another distribution of Linux, you will need to modify the 
playbooks to support your application manager (apt, etc.) and the pre-requisite packages.
```
These playbooks perform the following tasks on the Master/Worker nodes as defined in the Ansible [hosts](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/hosts) file.
* Configure the Docker Services for the HPE 3PAR Docker Volume Plug-in.
* Deploys the config files (iSCSI or FC) to support your environment.
* Installs the HPE 3PAR Docker Volume Plug-in (Containerized version).
* For standalone docker environment, deploys an HPE customized etcd cluster.
* For Kubernetes/OpenShift, deploys a Highly Available HPE etcd cluster used by the HPE 3PAR Docker Volume plugin.
* Supports single node (Use only for testing purposes) or multi-node deployment (HA) as defined in the Ansible hosts file.
* Deploys the HPE FlexVolume Driver.
* FlexVolume driver deployment for single master and multimaster will be as per the below table.

Cluster       | OS 3.9        | OS 3.10        | OS 3.11    | K8S 1.11      |  K8S 1.12     | K8S 1.13     | K8S 1.14     | K8S 1.15
------------- | ------------- | -------------  | -----------|------------   |-------------  |------------- |------------- | -------------
Single Master | System Process| System Process | Deployment | System Process| System Process| Deployment   | Deployment   | Deployment
Multimaster   | NA            | NA             |  Deployment| NA            | NA            | Deployment   | Deployment  | Deployment 
                
```
Note: Upgrade of existing Docker engine to higher version might break compatibility of HPE Docker Volume Plugin.
```
### Quick Start - Deploy a Production Ready HPE Volume Plugin for Docker on Kubernetes/OpenShift Cluster
#### Pre-requisites
                
1. Install Ansible v.2.5 to v.2.8 only. Follow the [Installation Guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html) for more details on ansible installation.

```
pip install ansible==2.7.12
OR
yum install ansible==2.7.12
```

```
Note: This installation is subject to availability of the mentioned packages in your yum repository.
```
Verify ansible version
```
[root@worker-node-1 ~]# ansible --version
ansible 2.7.12
  config file = None
  configured module search path = [u'/root/.ansible/plugins/modules', u'/usr/share/ansible/plugins/modules']
  ansible python module location = /usr/lib/python2.7/site-packages/ansible
  executable location = /usr/bin/ansible
  python version = 2.7.5 (default, Aug  7 2019, 00:51:29) [GCC 4.8.5 20150623 (Red Hat 4.8.5-39)]
```
```
Note: Ansible version should be between 2.5 to 2.8 only
```
For further information on the ansible installation refer the Installation guide at [Installation Guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

2. Make sure the path of kubectl or oc binary is available in $PATH env variable.
3. Kubernetes/Openshift should be up and running. Please check the following steps on the setup.
* Kubernetes/Openshift cluster should be up and all the nodes in Ready state
	                
```
[root@cssosbe01-196119 ansible_3par_docker_plugin]# kubectl get nodes -o wide
NAME              STATUS  ROLES   AGE  VERSION  INTERNAL-IP     EXTERNAL-IP  OS-IMAGE               KERNEL-VERSION              CONTAINER-RUNTIME
cssosbe01-196119  Ready   master  17d  v1.15.3  15.212.196.119  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7
cssosbe01-196120  Ready   master  17d  v1.15.3  15.212.196.120  <none>       CentOS Linux 7 (Core)  3.10.0-1062.4.1.el7.x86_64  docker://18.9.7
cssosbe01-196121  Ready   master  17d  v1.15.3  15.212.196.121  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7
cssosbe01-196150  Ready   <none>  17d  v1.15.3  15.212.196.150  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7
cssosbe01-196151  Ready   <none>  17d  v1.15.3  15.212.196.151  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7
```
```
Note: If any one node is in NotReady state follow the troubleshooting steps for the Creating Kubernetes/OpenShift cluster.
```
                
* Verify the cluster info

```
[root@cssosbe01-196119 ansible_3par_docker_plugin]# kubectl cluster-info
Kubernetes master is running at https://cssosbe01-196149.in.rdlabs.hpecorp.net:8443
coredns is running at https://cssosbe01-196149.in.rdlabs.hpecorp.net:8443/api/v1/namespaces/kube-system/services/coredns:dns/proxy
kubernetes-dashboard is running at https://cssosbe01-196149.in.rdlabs.hpecorp.net:8443/api/v1/namespaces/kube-system/services/https:kubernetes-dashboard:/proxy
```
To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.

4. Firewalld service should be off during Kubernetes setup.

```
systemctl status firewalld
```

5. Proxy Settings
Set the http_proxy, https_proxy and no_proxy environment variables.
```
export http_proxy=http://<proxy server name/IP>:port_number
export https_proxy=https:// <proxy server name/IP>:port_number
export no_proxy=localhost,localaddress,.localdomain.com,.hpecorp.net,.hp.com,.hpcloud.net, <3paripaddress>,<all master/worker node ip address>
```
6. Set SSH connection with 3PAR
Login to 3PAR via SSH to create entry in /<user>/.ssh/known_hosts file.
```
Note: Entries for the Master and Worker nodes should already exist within the /<user>/.ssh/known_hosts file from the OpenShift installation. If not, you will need to log into each of the Master and Worker nodes as well to prevent connection errors from Ansible.
```


#### Install HPE Volume Plugin for Docker on Kubernetes/OpenShift Cluster
+ Clone the python-hpedockerplugin repository on any of the masters.
```
$ cd ~
$ git clone https://github.com/hpe-storage/python-hpedockerplugin
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
```
+ Copy plugin configuration properties - sample at properties/plugin_configuration_properties.yml based on your HPE 3PAR Storage array configuration. Some of the properties are mandatory and must be specified in the properties file while others are optional.
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin/properties
$ cp plugin_configuration_properties_sample.yml plugin_configuration_properties.yml
```
+ Please refer to [sample](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml) file for plugin configuration properties yaml.
This [Example](https://github.com/sonawane-shashikant/python-hpedockerplugin/tree/master/docs/img/Example_Plugin_Configuration_yaml.png) image shows the example with expected parameters as per requirement.
+ Installer installs etcd as a service on the nodes which are mentioned under [etcd] section of hosts file to store the plugin data.
```
Note: Please ensure that the ports 23790 and 23800 are unoccupied before installation on all the nodes under [etcd] section. 
If the ports are not available on a particular node, etcd installation will fail.
If more than one node is mentioned under [etcd] section, then it will create the etcd cluster.
```
+ Modify [hosts](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/hosts) file to define your Master/Worker nodes as well as where you want to deploy your etcd cluster.
```
Note: For the multi-master setup, define all the master nodes under the [masters] section in hosts file and it should be active master from where the doryd deployment is executed. For more information on etcd and how-to setup an etcd cluster for High Availability.
The installer, in the current state does not have the capability to add or remove nodes in the etcd cluster. In case an etcd node is not responding or goes down, it is beyond the current scope to admit it back into the cluster. Please follow the etcd documentation to do so manually.
```
+ Please refer [etcd_cluster](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/advanced/etcd_cluster_setup.md) for more details.
+ It is recommended that the properties file is encrypted using Ansible Vault.
+ Set encryptor_key in properties/plugin_configuration_properties.yml for the backends to store encrypted passwords in /etc/hpedockerplugin/hpe.conf. This value shouldn't be set to empty string.
+ Run Installation
```
cd /root/python-hpedockerplugin/ansible_3par_docker_plugin
[root@cssosbe01-196119 ansible_3par_docker_plugin]ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```
[Post installation, validation checks](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/PostInstallation_checks.md)
+ In order to upgrade HPE Volume Plugin for Docker on Kubernetes/OpenShift Cluster refer to [Plugin Upgrade]
[Post upgrade, validation checks](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/PostInstallation_checks.md)

+ For Uninstalltion, Update and Upgrade, please refer to [Plugin Upgrade](https://github.com/sonawane-shashikant/python-hpedockerplugin/blob/master/Uninstall_Update_Upgade.md)
+ For Usage, Troubleshoots and Limitations, Please refer to this [link](https://github.com/sonawane-shashikant/python-hpedockerplugin/blob/master/docs/Usage_Troubleshoot_Limitations.md)
