1.	Slide#6 Introduction to Containers & Orchestration
a.	Kubernetes Cluster
b.	OpenShift Cluster
2.	Overview of HPE Volume Plugin for Docker 
<Paste the same image appearing on our github>
3.	Support Matrix
i.	Supported HPE 3PAR and HPE Primera OS - 
ii.	Supported Kubernetes and OpenShift verisons – 
iii.	Supported Linux distributions - 
iv.	Supported Ansible versions - 
v.	Supported Docker versions – 
<Use Specifics from Limitation section>
Note: Upgrade of existing Docker engine to higher version might break compatibility of HPE Docker Volume Plugin.

4.	Quick Start - Deploy a Production Ready HPE Volume Plugin for Docker on Kubernetes/OpenShift Cluster
a.	Pre-requisites
i.	Install Ansible v.2.5 to v.2.8 only. Follow the Installation Guide Installation Guide
ii.	Make sure the path of kubectl or oc binary is available in $PATH env variable
iii.	Kubernetes/Openshift should be up and running. Please check the following steps on the setup.
iv.	Kubernetes/Openshift cluster should be up and all the nodes in Ready state
b.	Validate Kubernetes cluster infrastructure
[root@cssosbe01-196119 ansible_3par_docker_plugin]# kubectl get nodes -o wide
NAME              STATUS  ROLES   AGE  VERSION  INTERNAL-IP     EXTERNAL-IP  OS-IMAGE               KERNEL-VERSION              CONTAINER-RUNTIME
cssosbe01-196119  Ready   master  17d  v1.15.3  15.212.196.119  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7
cssosbe01-196120  Ready   master  17d  v1.15.3  15.212.196.120  <none>       CentOS Linux 7 (Core)  3.10.0-1062.4.1.el7.x86_64  docker://18.9.7
cssosbe01-196121  Ready   master  17d  v1.15.3  15.212.196.121  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7
cssosbe01-196150  Ready   <none>  17d  v1.15.3  15.212.196.150  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7
cssosbe01-196151  Ready   <none>  17d  v1.15.3  15.212.196.151  <none>       CentOS Linux 7 (Core)  3.10.0-957.el7.x86_64       docker://18.9.7

Note: If any one node is in NotReady state follow the troubleshooting steps for the Creating Kubernetes cluster LINK

i.	VERIFY THE CLUSTER INFO

[root@cssosbe01-196119 ansible_3par_docker_plugin]# kubectl cluster-info
Kubernetes master is running at https://cssosbe01-196149.in.rdlabs.hpecorp.net:8443
coredns is running at https://cssosbe01-196149.in.rdlabs.hpecorp.net:8443/api/v1/namespaces/kube-system/services/coredns:dns/proxy
kubernetes-dashboard is running at https://cssosbe01-196149.in.rdlabs.hpecorp.net:8443/api/v1/namespaces/kube-system/services/https:kubernetes-dashboard:/proxy
To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.
       
c.	Set Environment Variables. 
1.	Make sure the path of kubectl or oc binary is available in $PATH env variable
firewalld service should be off during Kubernetes setup.

systemctl status firewalld

d.	Proxy Settings
Set the http_proxy, https_proxy and no_proxy environment variables.

export http_proxy=http://<proxy server name/IP>:port_number
export https_proxy=https:// <proxy server name/IP>:port_number
export no_proxy=localhost,localaddress,.localdomain.com,.hpecorp.net,.hp.com,.hpcloud.net, <3paripaddress>,<all master/worker node ip address>

e.	Set SSH connection with 3PAR
Login to 3PAR via SSH to create entry in /<user>/.ssh/known_hosts file
<>
Note: Entries for the Master and Worker nodes should already exist within the /<user>/.ssh/known_hosts file from the OpenShift installation. If not, you will need to log into each of the Master and Worker nodes as well to prevent connection errors from Ansible.

f.	ANSIBLE INSTALLATION

pip install ansible==2.7.12

OR

yum install ansible==2.7.12  (This installation is subject to availability of the mentioned packages in your yum repository)

[root@worker-node-1 ~]# ansible --version
ansible 2.7.12
  config file = None
  configured module search path = [u'/root/.ansible/plugins/modules', u'/usr/share/ansible/plugins/modules']
  ansible python module location = /usr/lib/python2.7/site-packages/ansible
  executable location = /usr/bin/ansible
  python version = 2.7.5 (default, Aug  7 2019, 00:51:29) [GCC 4.8.5 20150623 (Red Hat 4.8.5-39)]

Note: Ansible version should be between 2.5 to 2.8 only

For further information on the ansible installation refer the Installation guide at Installation Guide
<Use Specifics from Limitation section>

5.	Install HPE Volume Plugin for Docker on Kubernetes/OpenShift Cluster
a.	Clone the python-hpedockerplugin repository

$ cd ~
$ git clone https://github.com/hpe-storage/python-hpedockerplugin
$ cd python-hpedockerplugin/ansible_3par_docker_plugin

b.	Copy plugin configuration properties - sample at properties/plugin_configuration_properties.yml based on your HPE 3PAR Storage array configuration. Some of the properties are mandatory and must be specified in the properties file while others are optional.
$ cd ~
$ cd python-hpedockerplugin/ansible_3par_docker_plugin/properties
$ cp plugin_configuration_properties_sample.yml plugin_configuration_properties.yml
