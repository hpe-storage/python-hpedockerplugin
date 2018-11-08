# Automated Installer for 3PAR Docker Volume plugin (Ansible)

These are Ansible playbooks to automate the install of the HPE 3PAR Docker Volume Plug-in for Docker for use within Kubernetes/OpenShift environments.

If you are not using Kubernetes or OpenShift, we recommend you take a look at the [Quick Start guide](/docs/quick_start_guide.md) for using the HPE 3PAR Docker Volume Plug-in in a standalone Docker environment.

>**NOTE:** The Ansible installer only supports RHEL/CentOS. If you are using another distribution of Linux, you will need to modify the playbooks to support your application manager (apt, etc.) and the pre-requisite packages.

### Getting Started

These playbooks perform the following tasks on the Master/Worker nodes as defined in the Ansible [hosts](/ansible_3par_docker_plugin/hosts) file.
* Configure the Docker Services for the HPE 3PAR Docker Volume Plug-in
* Deploys a 3-node Highly Available etcd cluster
* Deploys the config files (iSCSI or FC) to support your environment
* Installs the HPE 3PAR Docker Volume Plug-in (Containerized version) for Kubernetes/OpenShift
* Deploys the HPE FlexVolume Drivers

### Prerequisites:

  - Install Ansible 2.6 or above as per [Installation Guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)
  - Login to 3PAR via SSH to create entry in /\<user>\/.ssh/known_hosts file
  > **Note:** Entries for the Master and Worker nodes should already exist within the /\<user>\/.ssh/known_hosts file from the OpenShift installation. If not, you will need to log into each of the Master and Worker nodes as well to prevent connection errors from Ansible.

  - modify files/hpe.conf ([iSCSI](/ansible_3par_docker_plugin/files/iSCSI_hpe.conf) or [FC](/ansible_3par_docker_plugin/files/FC_hpe.conf)) based on your HPE 3PAR Storage array configuration. An example can be found here: [sample_hpe.conf](/ansible_3par_docker_plugin/files/sample_hpe.conf)

  - Modify [hosts](/ansible_3par_docker_plugin/hosts) file to define your Master/Worker nodes as well as where you want to deploy your etcd cluster

### Usage

Once the prerequisites are complete, run the following command:

- Installation on standalone docker environment:
```
$ ansible-playbook -i hosts install_standalone_hpe_3par_volume_driver.yml
```

- Installation on Openshift/Kubernetes environment:
```
$ ansible-playbook -i hosts install_hpe_3par_volume_driver.yml
```

Once complete you will be ready to start using the HPE 3PAR Docker Volume Plug-in.

Please refer to the Kubernetes/OpenShift section in the [Usage Guide](/docs/usage.md#k8_usage) on how to create and deploy some sample SCs, PVCs, and Pods with persistent volumes using the HPE 3PAR Docker Volume Plug-in.


<br><br>
