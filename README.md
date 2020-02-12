### HPE 3PAR and HPE Primera Volume Plug-in for Docker
The HPE 3PAR and HPE Primera Volume Plug-in for Docker leverages HPE storage platforms to provide scalable and persistent storage for stateful applications. This Ansible playbook will deploy HPE 3PAR and HPE Primera Volume Plug-in for Docker and the HPE Dynamic Provisioner for Kubernetes.

Refer to the [SPOCK](https://spock.corp.int.hpe.com/spock/utility/document.aspx?docurl=Shared%20Documents/hw/3par/3par_volume_plugin_for_docker.pdf) page for the latest support matrix for HPE 3PAR and HPE Primera Volume Plug-in for Docker.

#### Prerequisites
                
1. Ensure that you have reviewed the [System Requirements](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/system-reqs.md).
		Ensure that Ansible (v2.5 to v2.8) is installed. For more information, see [Ansible Installation Guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html).
```
pip install ansible==2.7.12
OR
yum install ansible==2.7.12
```
   Verify Ansible version.
```
$ ansible --version
ansible 2.7.12
```
2. Ensure that the path of **kubectl** or **oc** binary is available in *$PATH* env variable.
3. Ensure that Kubernetes/Openshift cluster is up and running:              
```
$ kubectl get nodes -o wide
```
4. Ensure that you have an established SSH connection with 3PAR or Primera storage systems:
		Logon to 3PAR or Primera via SSH to create an entry in /<user>/.ssh/known_hosts file.

Note: Entries for the Kubernetes/OpenShift Master and Worker nodes must be 
present in the ~/.ssh/known_hosts file for Ansible to install the plugin correctly. 
If not, SSH into each node within the cluster to create entries in ~/.ssh/known_hosts.
### Installing HPE 3PAR and HPE Primera Volume Plug-in for Docker on Kubernetes/OpenShift Cluster
1. Clone the **hpe-storage/python-hpedockerplugin** Github repository on any of the masters.
```
$ cd ~
$ git clone https://github.com/hpe-storage/python-hpedockerplugin
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
```
2. Create the **properties/plugin_configuration_properties.yml** based on your HPE 3PAR/Primera Storage array configuration.
+ The [plugin_configuration_properties_simplified.yml](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/properties/plugin_configuration_properties_simplified.yml) shows a single backend setup example. 
+ Some of the properties are mandatory and must be specified in the properties file while others are optional.
+ Refer to this [sample](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml) file for additional configuration options.
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin/properties
$ cp plugin_configuration_properties_sample.yml plugin_configuration_properties.yml
```
3. Modify [hosts](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/hosts) file to define the Kubernetes/OpenShift Master and Worker nodes and to define the location to deploy the etcd cluster for storing the 3PAR/Primera Volume metadata..
```
$ cd ~/python-hpedockerplugin/
$ vi hosts
```
4. Run the Ansible playbook.
```
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```
5. Validate successful installation of the plugin. See [Post Installation Checks](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/PostInstallation_checks.md).

#### For supported features and usage of the HPE 3PAR and HPE Primera Volume Plug-in for Docker, see [Supported Features and Usage](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/Usage_Troubleshoot_Limitations.md#Supported-Features)
#### For updating the configuration of the HPE 3PAR and HPE Primera Volume Plug-in for Docker, see [updating an existing plugin installation ](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/Uninstall_Update_Upgade.md#update-the-array-backends-in-openshiftkubernetes-environment)
#### For installation of the HPE 3PAR and HPE Primera Volume Plug-in for Docker on additional nodes, see [installing the HPE 3PAR and HPE Primera Volume Plug-in for Docker on additional nodes](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/Uninstall_Update_Upgade.md#install-the-hpe-3par-and-hpe-primera-volume-plug-in-for-docker-on-additional-nodes-in-the-cluster)
#### For upgrade of the HPE 3PAR and HPE Primera Volume Plug-in for Docker, see [upgrading the plugin](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/Uninstall_Update_Upgade.md#upgrade-the-hpe-3par-and-hpe-primera-volume-plug-in-for-docker)
#### For uninstallation of the HPE 3PAR and Primera Volume Plug-in for Docker, see [uninstalling the plugin](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/Uninstall_Update_Upgade.md#uninstall-the-hpe-3par-and-hpe-primera-volume-plug-in-for-docker-on-nodes-of-openshiftkubernetes-environment)
#### For troubleshooting and known issues of the HPE 3PAR and Primera Volume Plug-in for Docker, see [Troubleshooting and Known Issues](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/Usage_Troubleshoot_Limitations.md#troubleshooting)
