## Steps to switch from HPE 3PAR iSCSI volume plugin to HPE 3PAR FC Volume plugin

1.	The current installation of the HPE 3PAR iSCSI volume plugin (v2.0 and later) is assumed to be from docker store (https://store.docker.com/plugins/hpe-3par-docker-volume-plugin).
2.	It is assumed that all volumes are mounted and I/O operations are in-progress.
3.	Stop I/O operations and unmount all volumes.
4.	Disable the plugin forcefully using below command:

>*$ docker plugin disable --force PLUGIN*

5.	Update hpe.conf to disable iSCSI plugin and enable FC plugin.

Remove below entries from hpe.conf to disable iSCSI plugin: 

> *#hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_iscsi.HPE3PARISCSIDriver*   
> *#iscsi_ip_address = `<iSCSI IP address>`*   
> *#hpe3par_iscsi_ips = `<iSCSI IP addresses separated by comma>`*  
> *#hpe3par_iscsi_chap_enabled = `<True or False>`* 

Add below entries to hpe.conf to enable FC plugin:   

> *hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_fc.HPE3PARFCDriver*   
> *use_multipath = True*   
> *enforce_multipath = True*   

6. Enable the plugin using below command:

>*$ docker plugin enable PLUGIN*

7. Mount all the volumes and resume all I/O operations.

> NOTE:  
> 1) If one or more volumes are still mounted where Step 3 is not followed, the switching process would not be successful and volume mount and unmount operations would result in unexpected behaviour or errors.  
> 2) If any of volume mount operation fails which is a very rare scenario, restarting docker service and etcd daemon would help further for successful mount operation.
