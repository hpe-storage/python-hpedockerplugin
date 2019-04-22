## Steps to upgrade to the latest HPE 3PAR Managed Volume plugin

1.	The current installation of the volume plugin with old version (e.g store/hpestorage/hpedockervolumeplugin:1.1) is assumed to be from docker store (https://store.docker.com/plugins/hpe-3par-docker-volume-plugin).
2.	It is assumed that all volumes are mounted and I/O operations are in-progress.
3.	Stop I/O operations and unmount all volumes.
4.	Disable the plugin forcefully using below command:

>*$ docker plugin disable --force PLUGIN*

5.	Upgrade HPE 3PAR managed volume plugin which is available on docker store (https://store.docker.com/plugins/hpe-3par-docker-volume-plugin). 
6.	Execute the below command to upgrade the plugin to the latest version.

>*$ docker plugin upgrade PLUGIN [REMOTE]*

>*For example, $ docker plugin upgrade store/hpestorage/hpedockervolumeplugin:1.1 store/hpestorage/hpedockervolumeplugin:2.0*
> Note: Here you will be able to switch between FC (Fibre Channel) , 
> iSCSI Driver in hpe.conf starting from 2.0 release of the plugin


7. Enable the plugin using below command:

>*$ docker plugin enable PLUGIN*

8. Mount all the volumes and resume all I/O operations.

> NOTE:  
> If one or more volumes are still mounted where Step 3 is not followed, the upgrade process would not be successful. If any volume is unmounted after performing the upgrade, the resulting container would be in DEAD state and volume plugin would be highly unusable subsequently. The only workaround is to reboot the docker container host and start etcd daemon again. This is a known issue in docker engine: https://github.com/moby/moby/issues/27381



