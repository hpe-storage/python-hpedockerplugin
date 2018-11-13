# Automated Installer for 3PAR Docker Volume plugin (Ansible)

These are Ansible playbooks to automate the install of the HPE 3PAR Docker Volume Plug-in for Docker for use within standalone docker environment or Kubernetes/OpenShift environments.

>**NOTE:** The Ansible installer only supports Ubuntu/RHEL/CentOS. If you are using another distribution of Linux, you will need to modify the playbooks to support your application manager (apt, etc.) and the pre-requisite packages.

### Getting Started

These playbooks perform the following tasks on the Master/Worker nodes as defined in the Ansible [hosts](/ansible_3par_docker_plugin/hosts) file.
* Configure the Docker Services for the HPE 3PAR Docker Volume Plug-in
* Deploys the config files (iSCSI or FC) to support your environment
* Installs the HPE 3PAR Docker Volume Plug-in (Containerized version)
* For standalone docker environment,
  * Deploys an etcd cluster
* For Kubernetes/OpenShift, 
  * Deploys a 3-node Highly Available etcd cluster
  * Deploys the HPE FlexVolume Drivers

### Prerequisites:
  - Install Ansible 2.5 or above as per [Installation Guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

  - Login to 3PAR via SSH to create entry in /\<user>\/.ssh/known_hosts file
  > **Note:** Entries for the Master and Worker nodes should already exist within the /\<user>\/.ssh/known_hosts file from the OpenShift installation. If not, you will need to log into each of the Master and Worker nodes as well to prevent connection errors from Ansible.
  
  - Modify [plugin configuration properties](/ansible_3par_docker_plugin/properties/plugin_configuration_properties.yml) based on your HPE 3PAR Storage array configuration. Some of the properties are mandatory and must be specified in the properties file while others are optional. 
  
      | Property  | Mandatory | Default Value | Description |
      | ------------- | ------------- | ------------- | ------------- |
      | ```host_etcd_port_number```  | Yes  | No defualt value | Etcd port number |
      | ```hpedockerplugin_driver```  | Yes  | No defualt value  | ISCSI/FC driver  (hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver/hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver) |
      | ```hpe3par_ip```  | Yes  | No defualt value | IP address of 3PAR array |
      | ```hpe3par_username```  | Yes  | No defualt value | 3PAR username |
      | ```hpe3par_password```  | Yes  | No defualt value | 3PAR password |
      | ```hpe3par_cpg```  | Yes  | No defualt value | Primary user CPG |
      | ```volume_plugin```  | Yes  | No defualt value | Name of the docker volume image (only required with DEFAULT backend) |
      | ```encryptor_key```  | No  | No defualt value | Encryption key string for 3PAR password |
      | ```logging```  | No  | ```INFO``` | Log level |
      | ```hpe3par_debug```  | No  | No defualt value | 3PAR log level |
      | ```suppress_requests_ssl_warning```  | No  | ```True``` | Suppress request SSL warnings |
      | ```hpe3par_snapcpg```  | No  | ```hpe3par_cpg``` | Snapshot CPG |
      | ```hpe3par_iscsi_chap_enabled```  | No  | ```False``` | ISCSI chap toggle |
      | ```hpe3par_iscsi_ips```  | No  |No default value | Comma separated iscsi port IPs (only required if driver is ISCSI based) |
      | ```use_multipath```  | No  | ```False``` | Mutltipath toggle |
      | ```enforce_multipath```  | No  | ```False``` | Forcefully enforce multipath |
      | ```ssh_hosts_key_file```  | No  | ```~/.ssh/id_rsa.pub``` | Path to hosts key file |
      | ```quorum_witness_ip```  | No  | No default value | Quorum witness IP |
      | ```mount_prefix```  | No  | No default value | Alternate mount path prefix |
      | ```replication_device```  | No  | No default value | Replication backend properties |
    
  - It is recommended that the properties file is [encrypted using Ansible Vault](/ansible_3par_docker_plugin/encrypt_properties.md).

  - Modify [hosts](/ansible_3par_docker_plugin/hosts) file to define your Master/Worker nodes as well as where you want to deploy your etcd cluster

### Usage

Once the prerequisites are complete, run the following command:

- Installation on standalone docker environment:
```
$ ansible-playbook -i hosts install_standalone_hpe_3par_volume_driver.yml --ask-vault-pass
```

- Installation on Openshift/Kubernetes environment:
```
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml --ask-vault-pass
```
> **Note:** ```--ask-vault-pass``` is required only when the properties file is encrypted


Once complete you will be ready to start using the HPE 3PAR Docker Volume Plug-in.

Please refer to [Usage Guide](/docs/usage.md) on how to perform volume related actions on the standalone docker environment.

Please refer to the Kubernetes/OpenShift section in the [Usage Guide](/docs/usage.md#k8_usage) on how to create and deploy some sample SCs, PVCs, and Pods with persistent volumes using the HPE 3PAR Docker Volume Plug-in.


<br><br>
