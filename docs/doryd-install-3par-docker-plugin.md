### prebuilt dory/doryd binaries
```
wget https://github.com/hpe-storage/python-hpedockerplugin/raw/master/dory_installer
chmod u+x ./dory_installer
sudo ./dory_installer

# Confirm if the binaries are installed properly in this location

[docker@csimbe06-b12 tmp]$ ls -l /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/
total 52360
-rwxr-xr-x. 1 docker docker 47046107 Apr 20 06:11 doryd
-rwxr-xr-x. 1 docker docker  6561963 Apr 20 06:11 hpe
-rw-r--r--. 1 docker docker      237 Apr 20 06:11 hpe.json

```
### Build the dory/doryd binaries from source (Optional)

- Refer [build](https://github.com/hpe-storage/dory/blob/master/docs/dory/README.md#building) instructions

```
cd /usr/libexec/kubernetes/kubelet-plugins/volume/exec/
mkdir dev.hpe.com~hpe
cd dev.hpe.com~hpe
cp <path>/dory hpe
# create a file called hpe.json in this folder
```

### Contents of hpe.json (default configuration installed by dory_installer)
```
{
    "dockerVolumePluginSocketPath": "/run/docker/plugins/hpe.sock",
    "logDebug": true,
    "supportsCapabilities": true,
    "stripK8sFromOptions": true,
    "createVolumes": true,
    "listOfStorageResourceOptions": ["size"]
}
```

### Installing the doryd 


```
sudo /usr/libexec/kubernetes/kubelet-plugins/volume/exec/hpe.com~hpe/doryd  /etc/kubernetes/admin.conf hpe.com
```

More details refer this [blog](https://developer.hpe.com/blog/doryd-a-dynamic-provisioner-for-docker-volume-plugins)
Note: Please start from section "Kubekuddle this!" , since other pre-requisites are taken care of already.

### Reload the kubelet service (applicable only for plain Kubernetes environment)
```
systemctl daemon-reload
systemctl restart kubelet
```
### Confirming if the flexvolume driver started successfully.
```
tail -f /var/log/dory.log
```

```
Info : 2018/01/04 23:42:05 dory.go:52: [19723] entry  : Driver=hpe Version=1.0.0-4adcc622 Socket=/run/docker/plugins/hpe.sock Overridden=true
Info : 2018/01/04 23:42:05 dory.go:55: [19723] request: init []
Info : 2018/01/04 23:42:05 dory.go:58: [19723] reply  : init []: {"status":"Success"}
Info : 2018/01/04 23:42:12 dory.go:52: [19788] entry  : Driver=hpe Version=1.0.0-4adcc622 Socket=/run/docker/plugins/hpe.sock Overridden=true
```

### Create a StorageClass with the flexvolumedriver
Create a file (sc-example.yml) containing the StorageClass definition 
```
---
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
 name: transactionaldb
provisioner: hpe.com/hpe
parameters:
  size: "16"
  provisioning: "thin"
```
```
kubectl create -f sc-example.yml
```
### Create a PersistentVolumeClaim for the above StorageClass
Create a file (pvc-example.yml) containing reference to the StorageClass 
created above.
```
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: example-claim1
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 16Gi
  storageClassName: transactionaldb
```
```
kubectl create -f pvc-example.yml
```

### Confirmation on the docker volume plugin
Confirm the volume name in the pvc claim with that of the `docker volume ls` listing.

```
[root@csimbe13-b05 examples]# docker volume ls
DRIVER              VOLUME NAME
hpe                 eric
hpe                 test_vol1
hpe                 transactionaldb-484f3213-1559-11e8-acd9-ecb1d7a4aa90
[root@csimbe13-b05 examples]# kubectl get pvc
NAME             STATUS    VOLUME                                                 CAPACITY   ACCESSMODES   STORAGECLASS      AGE
example-claim1   Bound     transactionaldb-484f3213-1559-11e8-acd9-ecb1d7a4aa90   16Gi       RWO           transactionaldb   3h
```
