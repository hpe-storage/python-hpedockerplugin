As of 2.1 release of Docker Volume Plugin only one 3PAR array is supported. To support multi-arrays parallely, we are introducing support for more than 
one 3PAR Array via a concept called as "backend"

Each "backend" identifies a set of configuration details for a 3PAR Array
Currently till 2.1 release, there was a single default backend by name "DEFAULT"

With 2.2 release , we can have more than one backends like this as shown in the example.

This example configuration has 2 backends, one is the "DEFAULT", and other is "3par1". Each backend name is enclosed with square brackets

/etc/hpedockerplugin/hpe.conf
```
[DEFAULT]
ssh_hosts_key_file = /root/.ssh/known_hosts


host_etcd_ip_address = 192.168.68.40
host_etcd_port_number = 2379


# OSLO based Logging level for the plugin.
logging = DEBUG

# Enable 3PAR client debug messages
hpe3par_debug = False

# Suppress Requests Library SSL warnings
suppress_requests_ssl_warnings = True

hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver

hpe3par_api_url = https://15.212.192.252:8080/api/v1
hpe3par_username = 3paradm
hpe3par_password = 3pardata
san_ip = 15.212.192.252
san_login = 3paradm
san_password = 3pardata
hpe3par_cpg = FC_r1
hpe3par_iscsi_ips = 15.212.192.112
hpe3par_iscsi_chap_enabled = False

# iscsi_ip_address = 15.213.64.237

# hpe3par_iscsi_chap_enabled = False
use_multipath = True
enforce_multipath = True

[3par1]

ssh_hosts_key_file = /root/.ssh/known_hosts
hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver

hpe3par_api_url = https://192.168.67.7:8080/api/v1
hpe3par_username = 3paradm
hpe3par_password = 3pardata
san_ip = 192.168.67.7
san_login = 3paradm
san_password = 3pardata
hpe3par_cpg = docker_cpg
hpe3par_iscsi_ips = 192.168.68.201, 192.168.68.203
use_multipath = True
enforce_multipath = True

```

Following option called `-o backend=|backend_name|` is introduced now in 2.2 which will appended to the regular docker volume create CLI command
and -o importVol=, etc.

Eg. 
To create a volume named "db1_3par1" on backend identified by section "3par1" we can do this

`` docker volume create -d hpe --name db1_3par1 -o size=12 -o provisioning=thin -o backend=3par1 ``

Note: Ignoring the `-o backend=` option results in volume created on the DEFAULT backend.

When snapshot/clones are created, the original volume's backend is computed, and the snapshot/clone is created on that particular backend.

Similarly, `-o importVol=X`, with a `-o backend=|backend_name|`  imports the volume from a particular backend.

Only the `docker volume ls` will query all the volumes created on all backends

`docker volume rm <vol>` will query the backend automatically and remove that volume from the backend where it was created.

