
## Openshift Container Platform 3.10 installation

###Prerequisites

To install OpenShift Container Platform, you will need:

* At least two physical or virtual RHEL 7+ machines, with fully qualified domain names (either real world or within a network) and password-less SSH access to each other

### Instructions

* Modify the /etc/profile file by adding the following:
    ```
    export no_proxy="localhost,127.0.0.1,localaddress,.localdomain.com "
    export http_proxy= http://<proxy>:<port>/
    export https_proxy= http://<proxy>:<port>/
    ```

* Modify the /etc/rhsm/rhsm.conf file by adding the following:
    ```
    - an http proxy server to use (enter server FQDN)
    proxy_hostname = <proxy>
    - port for http proxy server
    proxy_port = <port>
    ```
* Modify the /etc/yum.conf file:
    ```
    proxy=http://<proxy>:<port>/
    ```
    
* Run the following before starting the server to make OpenShift Container Platform only run on one cor
    ```
    $ export GOMAXPROCS=1 
    ```

* As root on the target machines (both master and node), use subscription-manager to register the systems with Red Hat
 
     ```
    $ subscription-manager register 
    ```
  
* Pull the latest subscription data from RHSM:
    ```
    $ subscription-manager refresh 
    ```
* List the available subscriptions
    ```
    $ subscription-manager list --available 
    ```
* Find the pool ID that provides OpenShift Container Platform subscription and attach it. 
    ```
    $ subscription-manager attach --pool=<pool_id> 
    ```
* Replace the string <pool_id> with the pool ID of the pool that provides OpenShift Container Platform. The pool ID is a long alphanumeric string

* On both master and node, use subscription-manager to enable the repositories that are necessary in order to install OpenShift Container Platform
    ```
    $ subscription-manager repos \
    --enable="rhel-7-server-rpms" \
    --enable="rhel-7-server-extras-rpms" \
    --enable="rhel-7-server-ose-3.10-rpms" \
    --enable="rhel-7-server-ansible-2.4-rpms"
 
    ```

* The installer for OpenShift Container Platform is provided by the openshift-ansible package. Install it using yum on both the master and the node 
    ```
    $ yum -y install wget git net-tools bind-utils iptables-services bridge-utils bash-completion kexec-tools sos psacct
    $ yum -y update
    $ yum -y install openshift-ansible
    ```

* Also install the docker service on master and start it
    ```
    $ yum install docker-1.13.1
    $ systemctl status docker
    $ systemctl enable docker
    $ systemctl start docker 
    ``` 
* Set up password-less SSH access as this is required by the installer to gain access to the machines. On the master, run the following command.
    ```
    $ ssh-keygen
    ```
    Follow the prompts and just hit enter when asked for pass phrase.

    An easy way to distribute your SSH keys is by using a bash loop:
    
    ```
    $ for host in master.openshift.example.com \
      node.openshift.example.com; \
      do ssh-copy-id -i ~/.ssh/id_rsa.pub $host; \
      done
    ```
    
* Create the inventory file as shown in the below link
    
    [Inventory Link](https://docs.openshift.com/container-platform/3.10/install/example_inventories.html#install-config-example-inventories)
    
    Example host file - [hosts.txt](https://github.com/hpe-storage/python-hpedockerplugin/files/2745186/hosts.txt)
     
    Edit the example inventory to use your host names, then save it to a file (default location is /etc/ansible/hosts)

* Clone the openshift-ansible repository with release-3.10 branch checked out
    
    ```
    git clone https://github.com/openshift/openshift-ansible -b release-3.10
    ```

* Run the prerequisites.yml playbook using your inventory file: 
     ```
    $ ansible-playbook -i <inventory_file> /openshift-ansible/playbooks/prerequisites.yml
 
    ```
* Run the deploy_cluster.yml playbook using your inventory file:
    ```
    $ ansible-playbook -i <inventory_file> /openshift-ansible/playbooks/deploy_cluster.yml
    ```

