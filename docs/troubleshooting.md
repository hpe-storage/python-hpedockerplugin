## Troubleshooting

This section contains solutions to common problems that may arise during the setup and usage of the plugin.

#### iSCSI Connection Errors
The HPE Docker Volume Plugin must run on the host netowrk in order for iSCSI connections to work properly. Otherwise, unexpected iSCSI errors will occur if you run the plugin on a non-host network.

NOTE: Create and Delete operations will work fine when running the plugin on a non-host network. However, subsequent iSCSI attach operations will fail on those volumes (if the plugin is not on the host network).

#### SSH Host Keys File

Make sure the file path used for the ssh_hosts_key_file exists. The suggested default is the known hosts file located at /home/stack/.ssh/known_hosts but that may not actually exist yet on a system. The easiest way to create this file is to do the following:

$ ssh <username>@<3PAR or LeftHand storage array IP>

Where username is the username for the 3PAR or LeftHand storage array that will be used by the plugin. The IP portion is the IP of the desired storage array. These values are typically defined later in the configuration file itself.

#### Client Certificates for Secured etcd

If a secured etcd cluster is not desired the host_etcd_client_cert and host_etcd_client_key properties can be commented out safely. In the case where a secured etcd cluster is desired the two properties must point to the respective certificate and key files.

#### Debug Logging

Sometimes it is useful to get more verbose output from the plugin. In order to do this one must change the logging property to be one of the following values: INFO, WARN, ERROR, DEBUG.
