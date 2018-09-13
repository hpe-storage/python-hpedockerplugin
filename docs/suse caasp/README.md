**PRE-RELEASE: Not for Production Use.**

Introduction
============
This document details the installation steps in order to get up and
running quickly with the HPE 3PAR Volume Plug-in for Docker within a
SUSE CaaS 3.0 environment.

Before you begin:
=================

You need to have a **basic** knowledge of containers and Kubernetes.

You should have SUSE CaaS deployed within your environment. If you
want to learn how to deploy SUSE CaaS, please refer to the documents
below for more details.

**SUSE CaaS**

https://susedoc.github.io/doc-caasp/develop/caasp-deployment/single-html/

>**Note:**
>Managed Plugin is currently not supported.

###

Deploying the HPE 3PAR Volume Plug-in for Docker as a Docker Container (Containerized Plug-in) in Kubernetes/SUSE CaaS
======================================================================================================================

Below is the order and steps that will be followed to deploy the **HPE
3PAR Volume Plug-in for Docker (Containerized Plug-in)** within a **SUSE
CaaS 3.0** environment.

Let’s get started,

For this installation process, login in as **root**:

```bash
$ sudo su -
```
Configuring etcd
-----------------

> **Note:** For this quick start quide, we will be creating a
> single-node **etcd** deployment, as shown in the example below, but
> for production, it is **recommended** to deploy a **Highly
> Availability** **etcd** cluster.
>
> For more information on **etcd** and how to setup an **etcd** cluster
> for High Availability, please refer: 
>
> <https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/etcd_cluster_setup.md>

1.  **Export the** **Kubernetes/SUSE CaaS** **Master node IP address**
```bash
  $ export HostIP="<Master node IP>"
```
2.  **Run the following to create the etcd container.**

    **NOTE:** This **etcd** instance is separate from the **etcd**
    deployed by **Kubernetes/SUSE CaaS** and is *required* for managing
    the **HPE 3PAR Volume Plug-in for Docker**. We need to modify the
    default ports (**2379, 4001, 2380**) of the *new* **etcd** instance
    to prevent conflicts. This allows two instances of **etcd** to
    safely run in the environment.

```bash
  sudo docker run -d -v /home/share/ca-certificates/:/etc/ssl/certs -p 4002:4002 \
  -p 2381:2381 -p 2378:2378 \
  --name etcd quay.io/coreos/etcd:v2.2.0 \
  -name etcd0 \
  -advertise-client-urls http://${HostIP}:2378,http://${HostIP}:4002 \
  -listen-client-urls http://0.0.0.0:2378,http://0.0.0.0:4002 \
  -initial-advertise-peer-urls http://${HostIP}:2381 \
  -listen-peer-urls http://0.0.0.0:2381 \
  -initial-cluster-token etcd-cluster-1 \
  -initial-cluster etcd0=http://${HostIP}:2381 \
  -initial-cluster-state new
```


Installing the HPE 3PAR Volume Plug-in for Docker (Containerized Plug-in) for SUSE CaaS:
----------------------------------------------------------------------------------------

> **NOTE:** This section assumes that you already have **Kubernetes** or
> **SUSE CaaS** deployed in your environment, in order to run the
> following commands.

#####

1.  **Install the iSCSI and Multipath packages**
    ```bash
     $ transactional-update pkg install multipath-tools
     $ systemctl reboot
    ```
2.  **Configure /etc/multipath.conf**
    ```bash
     $ vi /etc/multipath.conf
    ```

    Copy the following into /etc/multipath.conf
    ```
    defaults {
                    polling_interval 10
                    max_fds 8192
            }

            devices {
                    device {
                            vendor                  "3PARdata"
                            product                 "VV"
                            no_path_retry           18
                            features                "0"
                            hardware_handler        "0"
                            path_grouping_policy    multibus
                            #getuid_callout         "/lib/udev/scsi_id --whitelisted --device=/dev/%n"
                            path_selector           "round-robin 0"
                            rr_weight               uniform
                            rr_min_io_rq            1
                            path_checker            tur
                            failback                immediate
                    }
            }
    ```

    Enable the **iscsid** and **multipathd** services
    ```bash
     $ systemctl enable iscsid multipathd
     $ systemctl start iscsid multipathd
    ```
3.  **Setup the Docker plugin configuration file**
    ```bash
     $ mkdir –p /etc/hpedockerplugin/
     $ vi /etc/hpedockerplugin/hpe.conf
    ```
    Copy the contents from the sample **hpe.conf** file, based on your
    storage configuration for either **iSCSI** or **Fiber Channel**:

    **HPE 3PAR iSCSI:**

    <https://github.com/hpe-storage/python-hpedockerplugin/blob/plugin_v2/config/hpe.conf.sample.3parISCSI>

    **HPE 3PAR Fiber Channel:**

    <https://github.com/hpe-storage/python-hpedockerplugin/blob/plugin_v2/config/hpe.conf.sample.3parFC>    

4. Either you can build the container image by following instructions in step 5 below, or use an pre-existing 2.1 image of the plugin container by substituting `image: hpestorage/legacyvolumeplugin:2.1` in docker-compose.yml given in step 6

5.  **Build the containerized image**
    ```bash
     $ git clone  https://github.com/hpe-storage/python-hpedockerplugin.git ~/container_code
     $ cd ~/container_code
     $ git checkout v210
     $ ./containerize.sh
    ```
    Observe the built container image by docker images command

    ```bash
    $ docker images
    REPOSITORY                           TAG                 IMAGE ID            CREATED             SIZE
    hpe-storage/python-hpedockerplugin   plugin_v2          9b540a18a9b2        4 weeks ago         239MB
    ```
6.  **Deploy the HPE 3PAR Volume Plug-In for Docker**

    ```bash
    $ cd ~
    $ vi docker-compose.yml
    ```

    Copy the content below into the **docker-compose.yml** file:
    ```yaml
    hpedockerplugin:
      image: hpe-storage/python-hpedockerplugin:plugin_v2
      container_name: volplugin
      net: host
      privileged: true
      volumes:
         - /dev:/dev
         - /run/lock:/run/lock
         - /var/lib:/var/lib
         - /var/run/docker/plugins:/var/run/docker/plugins:rw
         - /etc:/etc
         - /root/.ssh:/root/.ssh
         - /sys:/sys
         - /root/plugin/certs:/root/plugin/certs
         - /sbin/iscsiadm:/sbin/ia
         - /lib/modules:/lib/modules
         - /lib64:/lib64
         - /var/run/docker.sock:/var/run/docker.sock
         - /opt/hpe/data:/opt/hpe/data:shared
         - /usr/lib64:/usr/lib64
    ```

    **Save and Exit**

    > **Note: Please make sure etcd service in running state.**

7.  **Start the HPE 3PAR Volume Plug-in for Docker
    (Containerized Plug-in)**

    Make sure you are in the location of the **docker-compose.yml** file

    ```bash
    $ docker-compose –f docker-compose.yml up  or
    $ docker-compose –f docker-compose.yml up 2>&1 | tee /tmp/plugin_logs.txt
    ```
    > **Note:** In case you are missing **docker-compose**, run the
    > following commands:
    ```bash
   
    $ curl -L https://github.com/docker/compose/releases/download/1.21.2/docker-compose-$(uname -s)-$(uname -m) --insecure -o     /root/bin/docker-compose
    $ transactional-update shell
    $ cp /root/bin/docker-compose /usr/local/bin/
    $ chmod +x /usr/local/bin/docker-compose
    $ exit
    $ systemctl reboot
    ```
    > **Test the installation**
    ```bash
    $ docker-compose --version
    docker-compose version 1.21.2, build a133471
    ```
    > **Re-run the above commands.**
    >
    > For more information on Docker Compose, go to
    > [https://docs.docker.com/compose/install/\#install-compose](https://docs.docker.com/compose/install/%23install-compose)

7.  **Success, you should now be able to test docker volume operations
    like:**

    ```bash
    $ docker volume create -d hpe --name sample_vol -o size=1
    ```

8.  **Install the HPE 3PAR FlexVolume driver:**
    ```bash
    $ mkdir downloads && cd downloads

    $ wget https://github.com/hpe-storage/python-hpedockerplugin/raw/plugin_v2/docs/suse%20caasp/bin/hpe-bin-sles12.tgz
    $ wget https://raw.githubusercontent.com/hpe-storage/python-hpedockerplugin/plugin_v2/docs/suse%20caasp/bin/hpe.json $ tar –xvzf hpe-bin-sles12.tgz

    $ transactional-update shell
    $ mkdir –p /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/
    $ mv ~/downloads/hpe /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/
    $ mv ~/downloads/hpe.json /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe
    $ chmod u+s /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/hpe
    ```

9.  **Confirm HPE 3PAR FlexVolume driver installed correctly:**
    ```bash
    $ ls -l /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/

    total 6572
    -rwsr-sr-x 1 root root 6724533 Jun 15 04:38 hpe
    -rw-r--r-- 1 root root     317 Jun 15 04:38 hpe.json

    $ exit
    $ systemctl reboot
    ```

10.  **Deploying the HPE 3PAR FlexVolume dynamic provisioner (doryd):**

     > The dynamic provisioner needs to run only on the **master** node.
     > Below we will explain how to deply it as a daemonset. So execute the
     > following commands on the **master** node.

     ```bash
     $ mkdir doryd && cd doryd
     $ wget https://github.com/hpe-storage/python-hpedockerplugin/raw/plugin_v2/docs/suse%20caasp/bin/doryd-bin-sles12.tgz
     $ tar –xvzf doryd-bin-sles12.tgz
     $ wget https://raw.githubusercontent.com/hpe-storage/python-hpedockerplugin/plugin_v2/docs/suse%20caasp/doryd/Dockerfile
     $ docker build –t doryd .
     ```

     **Note: Building the image is needed for now, since we have not published
     the latest image to the Docker public registry. Once we publish the
     image, this is no longer necessary.**

     Once the image has been successfully built, execute the following
     command to deploy the doryd daemonset:
     ```bash
     $ kubectl create –f https://raw.githubusercontent.com/hpe-storage/python-hpedockerplugin/plugin_v2/docs/suse%20caasp/doryd/ds-doryd.yml
     ```

     Confirm that the doryd daemonset is running successfully

     ```bash
     $ kubectl get ds --namespace=kube-system
     NAME           DESIRED   CURRENT   READY     UP-TO-DATE   AVAILABLE   NODE SELECTOR                     AGE
     doryd          1         1         1         1            1           node-role.kubernetes.io/master=   7d
     kube-flannel   4         4         4         4            4           beta.kubernetes.io/arch=amd64     8d
     ```

11.  **Repeat steps 1-9 on all worker nodes. Step 10 needs to be executed only on the Master node.**

**Upon successful completion of the above steps, you should have a
working installation of SUSE CaaS integrated with HPE 3PAR Volume
Plug-in for Docker**

##### Known Issues:

All the known issues regarding plugin can be found at the link
below:<https://github.com/hpe-storage/python-hpedockerplugin/issues>

**Right now the containerized plugin on SUSE CaaS platform is qualified on Fibre Channel Driver only.**
On iSCSI Driver, there is still an outstanding open issue -- https://github.com/hpe-storage/python-hpedockerplugin/issues/198


Usage of the HPE 3PAR Volume Plug-in for Docker in Kubernetes/SUSE CaaS
=======================================================================

The following section will cover different operations and commands that
can be used to familiarize yourself and verify the installation of the
**HPE 3PAR Volume Plug-in for Docker** by provisioning storage using
**Kubernetes/SUSE CaaS** resources like **PersistentVolume**,
**PersistentVolumeClaim**, **StorageClass**, **Pods**, etc.

To learn more about **Persistent Volume Storage** and Kubernetes/SUSE
CaaS, go to:

<https://kubernetes.io/docs/tasks/configure-pod-container/configure-persistent-volume-storage/>

**Key Kubernetes Terms:**

-   **kubectl** – command line interface for running commands
    against Kubernetes clusters

-   **PV** – Persistent Volume is a piece of storage in the cluster that
    has been provisioned by an administrator.

-   **PVC** – Persistent Volume Claim is a request for storage by
    a user.

-   **SC** – Storage Class provides a way for administrators to describe
    the “classes” of storage they offer.

Below is an example **yaml** specification to create
**PersistentVolume** (PV) using the **HPE 3PAR FlexVolume driver**.

**Dynamic volume provisioning** allows storage volumes to be created
on-demand. To enable dynamic provisioning, a cluster administrator needs
to pre-create one or more **StorageClass** objects for users.
**StorageClass** object defines the **storage provisioner** and
parameters to be used during dynamic storage provisioning requests made
within a **Kubernetes**/**SUSE CaaS** environment. This provisioner is a
simple daemon that listens for **PVCs** and satisfies those claims based
on the defined **StorageClass** .

The following creates a **StorageClass** **sc1** which provisions a
compressed volume with the help of **HPE 3PAR Docker Volume Plugin**.
```yaml
$ sudo kubectl create -f - << EOF
---
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
 name: sc1
provisioner: hpe.com/hpe
parameters:
  size: "16"
  compression: "true"
EOF
```
Now let’s create a claim **PersistentVolumeClaim** (PVC):
```yaml
$ sudo kubectl create -f - << EOF
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pvc1
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: sc1
EOF

```
Looking at the **yaml** file, under **flexVolume** spec and in the
**driver** attribute, we specify the **hpe** FlexVolume driver to be
used. We can also specify the **docker volume provisioner** specs
(**name**, **size**, **compression**, etc.) under **options**.
```yaml
$ sudo kubectl create -f - << EOF
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pv1
spec:
    capacity:
      storage: 20Gi
    accessModes:
    - ReadWriteOnce
    flexVolume:
      driver: hpe.com/hpe
      options:
        name: hpe_volume
        size: "20"
EOF
```
At this point after creating the **SC** and **PVC** definitions, the
volume hasn’t been created yet. The actual volume gets created
on-the-fly during the pod deployment and volume mount phase.

So let’s create a **pod** using the **nginx** container along with some
persistent storage:
```yaml
$ sudo kubectl create -f - << EOF
---
apiVersion: v1
kind: Pod
metadata:
  name: pod1
spec:
  containers:
  - name: nginx
    image: nginx
    volumeMounts:
    - name: export
      mountPath: /export
  restartPolicy: Always
  volumes:
  - name: export
    persistentVolumeClaim:
      claimName: pvc1
EOF
```
When the **pod** gets created and a mount request is made, the volume is
now available and can be seen using the following command:
```
$ docker volume ls

DRIVER              VOLUME NAME
hpe                 export
```
On the Kubernetes/SUSE CaaS side it should now look something like this:
```bash
$ kubectl get pv,pvc,pod -o wide
NAME       CAPACITY   ACCESSMODES   RECLAIMPOLICY   STATUS    CLAIM            STORAGECLASS   REASON   AGE
pv/pv1     20Gi       RWO           Retain          Bound     default/pvc1                             11m


NAME         STATUS    VOLUME    CAPACITY   ACCESSMODES   STORAGECLASS   AGE
pvc/pvc1     Bound     pv100     20Gi       RWO                          11m


NAME                          READY     STATUS    RESTARTS   AGE       IP             NODE
po/pod1                       1/1       Running   0          11m       10.128.1.53    cld6b16

```
Now the **pod** can be deleted to **unmount** the **docker volume**.
Deleting a **docker volume** does not require manual clean-up because
the **dynamic provisioner** provides automatic clean-up. You can delete
the **PersistentVolumeClaim** and see the **PersistentVolume** and
**docker volume** automatically deleted.

**Congratulations**, you have completed all validation steps and have a
working Kubernetes/SUSE CaaS environment.


Appendix
========

### Restarting the plugin
```bash
$ docker stop <container_id_of_plugin>
```


```bash
$ docker start <container_id_of_plugin>
```
### Usage 

For more details on HPE 3PAR Volume Plugin-in for Docker usage and its
features refer:

<https://github.com/hpe-storage/python-hpedockerplugin/blob/master/docs/usage.md>



Learn more visit
-----------------

[https://www.hpe.com/storage](https://www.hpe.com/storage%20)

<https://developer.hpe.com/platform/hpe-3par/home>


