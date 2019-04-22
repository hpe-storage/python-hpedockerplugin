### Steps to migrate volumes from containerized plugin to Managed plugin

1.	The current installation of the volume plugin (deployed as a container) is assumed to be from this link: https://github.com/hpe-storage/python-hpedockerplugin/

2.	It is assumed that all volumes are mounted and I/O operations are in-progress.

3.	Stop I/O operations and unmount all volumes.

4.	Delete the volume entries from etcd using
```
curl command: curl -L -X DELETE http://`<Docker Host IP address>`:2379/v2/keys/volumes/`<volume-id>`
```

5.	Remove etcd daemon which is running as a container.

6.	Stop the legacy plugin which is deployed as a container.

7.	Uninstall docker service.

8.	Delete all docker related folders of legacy volume plugin (folders are expected in paths: **/usr/bin/docker**, **/etc/docker**, **/usr/share/../../**).

9. Reboot the system if it is possible.

10.	Reinstall the docker service.

>*Note: If steps 7-10 are not followed, then volume with managed plugin will not be created.*

11.	Start **etcd** daemon as a container and install managed V2 plugin from docker store (https://store.docker.com/plugins/hpe-3par-docker-volume-plugin).

12.	Create a new volume.

13.	Navigate to 3par array CLI and migrate the data from old volume to new volume using following commands:
```
$ setvv -snp_cpg `<CPG name>` `<name of old volumes with prefix dcv- followed by UUID>`
```

```
$ createvvcopy -p `<name of old volume with prefix dcv- followed by UUID>` `<name of new volume created at step 12 with prefix dcv- followed by UUID>`
```

```
Copy was started. child = `<old_volume>`, parent = `<new_volume>`, task ID = `<id>`
```  

```
$ showtask
```

14.	Monitor the copy task with task id and wait for the completion.

15.	Navigate to Docker host and mount this new volume, and verify the data is available in healthy state.

16. Repeat Steps 12-15 for all the volumes from steps 2 and 3.
