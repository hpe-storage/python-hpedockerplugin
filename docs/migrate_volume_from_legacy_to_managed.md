1.	I installed the latest legacy plugin with multipath.
2.	Created a volume.
3.	Mounted this volume and wrote data on this.
4.	Unmounted volume.
5.	Deleted the volume entries from etcd using curl command: curl -L -X DELETE http://10.50.9.20:2379/v2/keys/volumes/8dd4a8a4-4291-4529-b5d8-7af4aa2774d7
6.	Removed etcd daemon.
7.	Stopped legacy plugin.
8.	Uninstall docker service. 
9.	Deleted all docker related folders for legacy plugin.
10.	Intalled docker service again.

