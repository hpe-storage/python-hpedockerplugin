##### Update the array backends in Openshift/Kubernetes environment:
Modify the [plugin configuration properties - sample](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml) at properties/plugin_configuration_properties.yml based on the updated HPE 3PAR or HPE Primera Storage array configuration. Additional backends may be added or removed from the existing configuration. Individual attributes of the existing array configuration may also be modified.
Run the below command after updating the plugin configuration file.
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```

Note: It is not recommended to change the HPE Etcd information and array encryption password during the backend update process

#### Upgrade the HPE 3PAR and HPE Primera Volume Plug-in for Docker:
Modify the [plugin configuration properties - sample](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml) at properties/plugin_configuration_properties.yml and point it to the latest image from docker hub.
Run the below command after updating the plugin configuration file.
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```
Note:
1. Ensure that all the nodes in the cluster are present in the inventory hosts file.
2. The HPE 3PAR and HPE Primera Volume Plug-in for Docker will restart and the user will not be able to provision the volume during this process.
3. As per new approach, etcd is installed as a service. So, in case etcd is running as a container and plugin upgraded, then etcd will run as a service with appropriate data retention.
4. With encryption upgrade from version 3.1.1 to version 3.3.1 is supported .
5. Successful upgrade will remove the old plugin container and replace it with the new 	plugin container which is specified in the plugin properties file. 

Refer to [PostInstallation_checks](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/PostInstallation_checks.md) for validation of upgrade.

#### Install the HPE 3PAR and HPE Primera Volume Plug-in for Docker on additional nodes in the cluster:
Add the new nodes in the respective sections in the inventory hosts file.
Only new nodes IP or hostnames must be present in the hosts file.
Do not change the etcd hosts from the existing setup. Do not add or remove nodes in the etcd section.
Run the below command after updating the plugin configuration file.
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```
##### Uninstall the HPE 3PAR and HPE Primera Volume Plug-in for Docker on nodes of Openshift/Kubernetes environment:
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
$ ansible-playbook -i hosts uninstall/uninstall_hpe_3par_volume_driver.yml
```
##### Uninstall the HPE 3PAR and HPE Primera Volume Plug-in for Docker along with etcd on nodes of Openshift/Kubernetes environment:
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
$ ansible-playbook -i hosts uninstall/uninstall_hpe_3par_volume_driver_etcd.yml
```
Note: This process only adds or removes docker volume plugin and/or etcd in nodes in an existing cluster. It does not add or remove nodes in /Openshift cluster

On success after adding plugin on new nodes, the additional nodes will have a running HPE Volume Plugin for Docker.
On success after removing plugin from specified nodes, HPE Volume Plugin for Docker will be removed.
Uninstallation with etcd removes etcd_hpe service.
Please refer to the Kubernetes/OpenShift section in the [Usage Guide](https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/usage.md#k8_usage) on how to create and deploy some sample SCs, PVCs, and Pods with persistent volumes using the HPE Volume Plugin for Docker.
