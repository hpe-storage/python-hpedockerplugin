# Automated Installer for 3PAR Docker Volume plugin (Ansible)

These are Ansible playbooks to automate the install of the HPE 3PAR Docker Volume Plug-in for Docker for use within standalone docker environment or Kubernetes/OpenShift environments.

>**NOTE:** The Ansible installer only supports Ubuntu/RHEL/CentOS. If you are using another distribution of Linux, you will need to modify the playbooks to support your application manager (apt, etc.) and the pre-requisite packages.

### Getting Started

These playbooks perform the following tasks on the Master/Worker nodes as defined in the Ansible [hosts](/ansible_3par_docker_plugin/hosts) file.
* Configure the Docker Services for the HPE 3PAR Docker Volume Plug-in
* Deploys the config files (iSCSI or FC) to support your environment
* Installs the HPE 3PAR Docker Volume Plug-in (Containerized version)
* For standalone docker environment,
  * Deploys an HPE customized etcd cluster
* For Kubernetes/OpenShift, 
  * Deploys a Highly Available HPE etcd cluster used by the HPE 3PAR Docker Volume plugin 
    * Supports single node (Use only for testing purposes) or multi-node deployment (HA) as defined in the Ansible hosts file
  * Deploys the HPE FlexVolume Driver
  
     FlexVolume driver deployment for single master and multimaster will be as per the below table
	 
	 | Cluster | OS 3.9 | OS 3.10 | OS 3.11 | K8S 1.11 | K8S 1.12 | K8S 1.13 | K8S 1.14 | K8S 1.15 |
	 | --- | --- | --- | --- | --- | --- | --- | --- | --- |
	 | Single Master | System Process | System Process | Deployment | System Process | System Process | Deployment | Deployment | Deployment |
	 | Multimaster | NA | NA | Deployment | NA | NA | Deployment | Deployment | Deployment | Deployment |

>**NOTE:** System Process can be verified using systemctl commands whereas Deployment can be verified using **kubectl get pods** command. Please refer to [PostInstallation_checks](/docs/PostInstallation_checks.md) for more details. 	 

### Prerequisites:
  - Basic knowledge of Ansible and ssh keys

  - Install Ansible v.2.5 to v.2.8 only. Follow the Installation Guide [Installation Guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

  - Login to 3PAR via SSH to create entry in /\<user>\/.ssh/known_hosts file
  > **Note:** Entries for the Master and Worker nodes should already exist within the /\<user>\/.ssh/known_hosts file from the OpenShift installation. If not, you will need to log into each of the Master and Worker nodes as well to prevent connection errors from Ansible.
  - Make sure the path of kubectl or oc binary is available in $PATH env variable
  - Clone the python-hpedockerplugin repository
    ```
    $ cd ~
    $ git clone https://github.com/hpe-storage/python-hpedockerplugin
    $ cd python-hpedockerplugin/ansible_3par_docker_plugin
    ```
  
  - Copy [plugin configuration properties - sample](/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml) at `properties/plugin_configuration_properties.yml` based on your HPE 3PAR Storage array configuration. Some of the properties are mandatory and must be specified in the properties file while others are optional. 
    ```
    $ cd ~
    $ cd python-hpedockerplugin/ansible_3par_docker_plugin/properties
    $ cp plugin_configuration_properties_sample.yml plugin_configuration_properties.yml
    ```
  
      | Property  | Mandatory | Default Value | Description |
      | ------------- | ------------- | ------------- | ------------- |
      | ```hpedockerplugin_driver```  | Yes  | No default value  | ISCSI/FC driver  (hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver/hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver) |
      | ```hpe3par_ip```  | Yes  | No default value | IP address of 3PAR array |
      | ```hpe3par_username```  | Yes  | No default value | 3PAR username |
      | ```hpe3par_password```  | Yes  | No default value | 3PAR password |
      | ```hpe3par_port```  | Yes  | 8080 | 3PAR HTTP_PORT port |
      | ```hpe3par_cpg```  | Yes  | No default value | Primary user CPG |
      | ```volume_plugin```  | Yes  | No default value | Name of the docker volume image (only required with DEFAULT backend) |
      | ```encryptor_key```  | No  | No default value | Encryption key string for 3PAR password |
      | ```logging```  | No  | ```INFO``` | Log level |
      | ```hpe3par_debug```  | No  | No default value | 3PAR log level |
      | ```suppress_requests_ssl_warning```  | No  | ```True``` | Suppress request SSL warnings |
      | ```hpe3par_snapcpg```  | No  | ```hpe3par_cpg``` | Snapshot CPG |
      | ```hpe3par_iscsi_chap_enabled```  | No  | ```False``` | ISCSI chap toggle |
      | ```hpe3par_iscsi_ips```  | No  |No default value | Comma separated iscsi port IPs (only required if driver is ISCSI based) |
      | ```use_multipath```  | No  | ```False``` | Mutltipath toggle |
      | ```enforce_multipath```  | No  | ```False``` | Forcefully enforce multipath |
      | ```ssh_hosts_key_file```  | No  | ```/root/.ssh/known_hosts``` | Path to hosts key file |
      | ```quorum_witness_ip```  | No  | No default value | Quorum witness IP |
      | ```mount_prefix```  | No  | No default value | Alternate mount path prefix |
      | ```hpe3par_iscsi_ips```  | No  | No default value | Comma separated iscsi IPs. If not provided, all iscsi IPs will be read from the array and populated in hpe.conf |
      | ```vlan_tag```  | No  | False | Populates the iscsi_ips which are vlan tagged, only applicable if ```hpe3par_iscsi_ips``` is not specified |
      | ```replication_device```  | No  | No default value | Replication backend properties |
      | ```dory_installer_version```  | No  | dory_installer_v32 | Required for Openshift/Kubernetes setup. Dory installer version, supported versions are dory_installer_v31, dory_installer_v32 |
      | ```hpe3par_server_ip_pool```  | Yes  | No default value | This parameter is specific to fileshare. It can be specified as a mix of range of IPs and individual IPs delimited by comma. Each range or individual IP must be followed by the corresponding subnet mask delimited by semi-colon E.g.: IP-Range:Subnet-Mask,Individual-IP:SubnetMask|
      | ```hpe3par_default_fpg_size```  | No  | No default value | This parameter is specific to fileshare. Default fpg size, It must be in the range 1TiB to 64TiB. If not specified here, it defaults to 16TiB |

  - Adding multiple backends in [plugin configuration properties - sample](/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml)
    Below is the table of available configurations along with the installer plugin behavior column for each combination:
    
    BLOCK points to the hpedockerplugin_driver, hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver OR hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver
    
    FILE points to the hpedockerplugin_driver, hpedockerplugin.hpe.hpe_3par_file.HPE3PARFileDriver

      |DEFAULT | DEFAULT_BLOCK | DEFAULT_FILE | INSTALLER BEHAVIOR        |
      |--------|---------------|--------------|-----------------|
      |BLOCK   |--             |--            | Plugin successfully installs.|
      |FILE    |--             |--            | Plugin successfully installs.|
      |--      |BLOCK |-- |DEFAULT backend is mandatory.Plugin installation fails in this case.|
      |--      |-- |FILE |DEFAULT backend is mandatory.Plugin installation fails in this case.|
      |BLOCK   |-- |FILE |Plugin successfully installs.|
      |FILE    |BLOCK |-- |Plugin successfully installs.|
      |BLOCK   |BLOCK |FILE |When we have DEFAULT backend with Block driver, then there should not be any DEFAULT_BLOCK backend in multibackend configuration.Plugin installation fails in this case.|
      |FILE    |BLOCK |FILE |When we have DEFAULT backend with File driver, then there should not be any DEFAULT_FILE backend in multibackend configuration.Plugin installation fails in this case.|
      |BLOCK   |FILE |--  |DEFAULT_BLOCK is not allowed to be configured for File driver. Plugin installation fails in this case.|
      |FILE   |-- |BLOCK  |DEFAULT_FILE is not allowed to be configured for Block driver. Plugin installation fails in this case.|
      |BLOCK   |BLOCK |-- |When we have DEFAULT backend with Block driver, then there should not be any DEFAULT_BLOCK backend in single backend configuration.Plugin installation fails in this case.|
      |FILE    |-- |FILE |When we have DEFAULT backend with File driver, then there should not be any DEFAULT_FILE backend in single backend configuration.Plugin installation fails in this case.|

  - Installer installs etcd as a service on all the nodes mentioned under [etcd] section of [hosts](/ansible_3par_docker_plugin/hosts)
    It uses ports 23800 and 23790.
      
    > **Note:** Please ensure that the ports specified above are unoccupied before installation. If the ports are not available on a particular node, etcd installation will fail.
    
    > **Limitation:** The installer, in the current state does not have the capability to add or remove nodes in the etcd cluster. In case an etcd node is not responding or goes down, it is beyond the current scope to admit it back into the cluster. Please follow the [etcd documentation](https://coreos.com/etcd/docs/latest/etcd-live-cluster-reconfiguration.html) to do so manually.
    
  - It is recommended that the properties file is [encrypted using Ansible Vault](/ansible_3par_docker_plugin/encrypt_properties.md).
   
  - Set **encryptor_key** in properties/plugin_configuration_properties.yml for the backends to store encrypted passwords in /etc/hpedockerplugin/hpe.conf. This value shouldn't be set to empty string.

  - Modify [hosts](/ansible_3par_docker_plugin/hosts) file to define your Master/Worker nodes as well as where you want to deploy your etcd cluster
   > **Note:** For the multimaster setup define all the master nodes under the [masters] section in [hosts](/ansible_3par_docker_plugin/hosts) file and it should be a active master from where the doryd deployment is executed.
    All the sections [masters/workers/etcd] in the hosts file should contain Ready/Active nodes entries only.
    For more information on etcd and how to setup an **etcd** cluster for High Availability, please refer:
    [/docs/advanced/etcd_cluster_setup.md](/docs/advanced/etcd_cluster_setup.md)
  
### Working with proxies:

Set `http_proxy` and `https_proxy` in the [inventory hosts file](/ansible_3par_docker_plugin/hosts) while installing plugin on Kubernetes/Openshift setup. For setting proxies in the standalone plugin installation, see [inventory hosts file for standalone plugin installation](/ansible_3par_docker_plugin/hosts_standalone_nodes)

### Usage

Once the prerequisites are complete, run the following command:

- ##### Fresh installation
  * Fresh installation on standalone docker environment(Non Openshift/Kubernetes):
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
$ ansible-playbook -i hosts_standalone_nodes install_standalone_hpe_3par_volume_driver.yml
```

  * Fresh installation on Openshift/Kubernetes environment:
```
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```
> **Note:** Add ```--ask-vault-pass``` to the end of the ansible-playbook command only when the properties file is encrypted


Once complete you will be ready to start using the HPE 3PAR Docker Volume Plug-in.
Please refer to [PostInstallation_checks](/docs/PostInstallation_checks.md) for validation of installation.

- ##### Update the array backends in Standalone/Openshift/Kubernetes environment:
  * Modify the [plugin configuration properties - sample](/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml) at `properties/plugin_configuration_properties.yml` based on the updated HPE 3PAR Storage array configuration. Additional backends may be added or removed from the existing configuration. Individual attributes of the existing array configuration may also be modified.

    * Update array backend on standalone docker environment:
    ```
    $ cd ~
    $ cd python-hpedockerplugin/ansible_3par_docker_plugin
    $ ansible-playbook -i hosts_standalone_nodes install_standalone_hpe_3par_volume_driver.yml
    ```

    * Update array backend on Openshift/Kubernetes environment:
    ```
    $ cd ~
    $ cd python-hpedockerplugin/ansible_3par_docker_plugin
    $ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
    ```
  > **Note:** It is not recommended to change the HPE Etcd information and array encryption password during the backend update process
 
- ##### Upgrade the docker volume plugin
  * Modify the `volume_plugin` in [plugin configuration properties - sample](/ansible_3par_docker_plugin/properties/plugin_configuration_properties_sample.yml) and point it to the latest image from docker hub
      * Update plugin on standalone docker environment:
      ```
      $ cd ~
      $ cd python-hpedockerplugin/ansible_3par_docker_plugin
      $ ansible-playbook -i hosts_standalone_nodes install_standalone_hpe_3par_volume_driver.yml
      ```
     * Update plugin on Openshift/Kubernetes environment:
     ```
     $ cd ~
     $ cd python-hpedockerplugin/ansible_3par_docker_plugin
     $ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
     ```
   > **Note:** 
     - Ensure that all the nodes in the cluster are present in the inventory [hosts](/ansible_3par_docker_plugin/hosts) file
     - The docker volume plugin will be restarted and the user will not be able to create the volume during the process
     - As per new approach, etcd is installed as a service. So, in case etcd is running as a container and plugin upgraded, then etcd will run as a service with appropriate data retention.
     - With encryption upgrade from version 3.1.1 to version 3.3.1 is supported .


   * Successful upgrade will remove the old plugin container and replace it with the new plugin container which is specified in the plugin properties file 
     Please refer to [PostInstallation_checks](/docs/PostInstallation_checks.md) for validation of upgrade.
      
- ##### Install docker volume plugin to additional nodes in the cluster
  * Add the new nodes in the respective sections in the inventory [hosts](/ansible_3par_docker_plugin/hosts) file
  * Only new nodes IP or hostnames must be present in the hosts file
  * Do not change the etcd hosts from the existing setup. Do not add or remove nodes in the etcd section
     
     * Install plugin on new nodes on Openshift/Kubernetes environment:
     ```
     $ cd ~
     $ cd python-hpedockerplugin/ansible_3par_docker_plugin
     $ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
     ```
- ##### Uninstallation docker volume plugin     
     * Uninstall plugin on nodes on Openshift/Kubernetes environment:
     ```
     $ cd ~
     $ cd python-hpedockerplugin/ansible_3par_docker_plugin
     $ ansible-playbook -i hosts uninstall/uninstall_hpe_3par_volume_driver.yml
     ```
     
     * Uninstall plugin along with etcd on nodes on Openshift/Kubernetes environment:
     ```
     $ cd ~
     $ cd python-hpedockerplugin/ansible_3par_docker_plugin
     $ ansible-playbook -i hosts uninstall/uninstall_hpe_3par_volume_driver_etcd.yml
     ```
    * Uninstall plugin on standalone environment:
     ```
     $ cd ~
     $ cd python-hpedockerplugin/ansible_3par_docker_plugin
     $ ansible-playbook -i hosts_standalone_nodes uninstall/uninstall_standalone_hpe_3par_volume_driver.yml
     ```
     
     * Uninstall plugin along with etcd standalone environment:
     ```
     $ cd ~
     $ cd python-hpedockerplugin/ansible_3par_docker_plugin
     $ ansible-playbook -i hosts_standalone_nodes uninstall/uninstall_standalone_hpe_3par_volume_driver_etcd.yml
     ```
     > **Note:** This process only adds or removes docker volume plugin and/or etcd in nodes in an existing cluster. It does not add or remove nodes in Kubernetes/Openshift cluster
   * On success after adding plugin on new nodes, the additional nodes will have a running docker volume plugin container
   * On success after removing plugin from specified nodes, docker volume plugin container will be removed
   * Uninstallation with etcd removes etcd_hpe service.

Please refer to [Usage Guide](/docs/usage.md) on how to perform volume related actions on the standalone docker environment.

Please refer to the Kubernetes/OpenShift section in the [Usage Guide](/docs/usage.md#k8_usage) on how to create and deploy some sample SCs, PVCs, and Pods with persistent volumes using the HPE 3PAR Docker Volume Plug-in.


<br><br>
