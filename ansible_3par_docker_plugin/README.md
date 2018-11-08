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
  - Install Ansible 2.6 or above as per [Installation Guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)
  - Install sshpass on the ansible host
      - On RHEL/Centos
        ```
         yum install sshpass
        ```
      - On Ubuntu
        ```
         apt-get install sshpass
        ```
  - Login to 3PAR via SSH to create entry in /\<user>\/.ssh/known_hosts file
  > **Note:** Entries for the Master and Worker nodes should already exist within the /\<user>\/.ssh/known_hosts file from the OpenShift installation. If not, you will need to log into each of the Master and Worker nodes as well to prevent connection errors from Ansible.
  
  - Modify [plugin configuration properties](/ansible_3par_docker_plugin/properties/plugin_configuration_properties.yml) based on your HPE 3PAR Storage array configuration. Some of the properties are mandatory and must be specified in the properties file while others are optional. 
    - Mandatory properties
    ```
        host_etcd_port_number
        hpedockerplugin_driver
        hpe3par_ip
        hpe3par_username
        hpe3par_password
        hpe3par_cpg
        volume_plugin
    ```
    
    - Optional properties
    ```
        encryptor_key
        logging
        hpe3par_debug
        suppress_requests_ssl_warning
        hpe3par_snapcpg
        hpe3par_iscsi_chap_enabled
        use_multipath
        enforce_multipath
        ssh_hosts_key_file
    ```
    
  ```volume_plugin``` expects the docker volume pluginn image name
  ```encryptor_key``` expects an encryption key to encrypt the array passwords in hpe.conf file
    
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
