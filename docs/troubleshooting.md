## Troubleshooting

This section contains solutions to common problems that may arise during the setup and usage of the plugin.

#### iSCSI Connection Errors
The HPE Docker Volume Plugin must run on the host network in order for iSCSI connections to work properly. Otherwise, unexpected iSCSI errors will occur if you run the plugin on a non-host network.

>**NOTE:** Create and Delete operations will work fine when running the plugin on a non-host network. However, subsequent iSCSI attach operations will fail on those volumes (if the plugin is not on the host network).

#### FC Connection Errors
One or more fibre channel ports of container host and HPE 3PAR StoreServ must be in same zone. Otherwise, only create and delete volume operation will work fine and volume mount operation will fail for all volumes.

If "create file system failed exception" error is seen during volume mount operation and all subsequent mount requests are failed, then stop/uninstall the etcd and docker services and start/install them again with use_multipath and enforce_multipath parameters enabled in hpe.conf

#### SSH Host Keys File

Make sure the file path used for the ssh_hosts_key_file exists. The suggested default is the known hosts file located at /home/stack/.ssh/known_hosts but that may not actually exist yet on a system. The easiest way to create this file is to do the following:
```
$ ssh <username>@<3PAR array IP>
```

Where username is the username for the 3PAR storage array that will be used by the plugin. The IP portion is the IP of the desired storage array. These values are typically defined later in the configuration file itself.

#### Client Certificates for Secured etcd

If a secured etcd cluster is not desired the **host_etcd_client_cert** and **host_etcd_client_key** properties can be commented out safely. In the case where a secured etcd cluster is desired, the two properties must point to the respective certificate and key files.

For setting up secured etcd cluster, refer this doc:
[etcd cluster setup](/docs/advanced/etcd_cluster_setup.md)

#### Debug Logging

Sometimes it is useful to get more verbose output from the plugin. In order to do this one must change the logging property to be one of the following values: INFO, WARN, ERROR, DEBUG.

#### Logs for the plugin

Logs of plugin provides useful information on troubleshooting issue/error further. On Ubuntu, grep for the `plugin id` in the logs , where the `plugin id` can be identified by:

`$ docker-runc list`

Plugin logs will be available in system logs (e.g. `/var/log/syslog` on Ubuntu).

On RHEL and CentOS, issue `journalctl -f -u docker.service` to get the plugin logs.
