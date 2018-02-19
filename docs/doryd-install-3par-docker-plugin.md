### Build the dory/doryd binaries

- Refer [build](https://github.com/hpe-storage/dory/blob/master/docs/dory/README.md#building) instructions

```
cd /usr/libexec/kubernetes/kubelet-plugins/volume/exec/
mkdir dev.hpe.com~hpe
cd dev.hpe.com~/hpe
cp <path>/dory .
# create a file called hpe.json in this folder
```

### Contents of hpe.json
```
{
    "dockerVolumePluginSocketPath": "/run/docker/plugins/hpe.sock",
    "logDebug": true,
    "enable1.6": true,
    "supportsCapabilities": false,
    "stripK8sFromOptions": true,
    "createVolumes": true,
    "listOfStorageResourceOptions": ["size"]
}
```

### Reload the kubelet service
```
systemctl daemon-reload
systemctl restart kubelet
```
