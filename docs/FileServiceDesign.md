## File Service Design for HPE 3PAR Docker Volume Plugin
Design decision for implementing File Services for HPE 3PAR Docker Volume plugin is captured in this wiki.

### Objectives
1. Provide a way to present a file share (via NFS/CIFS -- which are currently supported on File Persona of HPE 3PAR) 
to containerized applications.
Our plugin currently supoorts NFS protocol.
  - To support share replication, we have model VFS as a docker volume object 
  - To support snapshot/quota we have to model FileStore to a docker volume object. We are currently moving to this model, since
  it will give an ideal balance between granurality on number of the share(s) vs. Capabilities which we need to support.

2. Creation of FPG and VFS to be transparent to the user. FPG (File Provisioning Group) requires CPG as input which will 
be supplied via the config file `/etc/hpedockerplugin/hpe_file.conf`. Creation of VFS requires virtual IP Address/subnet mask. And each VFS can have multiple IP's associated with it, and this pool of ip addresses will be supplied via the config file.

3. Provide a way to update the whitelisted IP's as part of ACL definition of File Store/Share.
(implicitly when a mount happens on a docker host) 
4. A share to be allowed to mount on multiple containers on one or more hosts. This is to support `accessModes: ReadWriteMany` 
option of kubernetes PVC

5. Document the Limitations.

### Mapping of a Docker Volume to a file persona object
- Due to some constraints on setting up of Quota/ACL (Access Control List) only applicable to File Store, and due 
features like Replication/Snapshot available only at either File Store/VFS (Virtual File Server) level, we have to map the docker volume
at either File Store/VFS level.

- But since there is a inherent limitations on the number of VFS which can be created on a 3PAR system (which is currently only 16), 
we can't define the granularity of the docker volume object to the File Store level, but instead we want to come down on the hierarchy of
file persona objects to the File store. 

- Our design approach currently will be based on mapping a docker volume object to a File Store only. This may be later extend to mapping
the docker volume object to VFS in later phases of development.


### Limitations
- Updating a quota via the `docker volume create` is not currently supported due to
  1. Docker volume plugin v2 specification does'nt directly provide an update primitive , updating quota on the File Store is not feasible
  2. Other approach of providing a separate binary file / utility would be a out-of-band operation on the file share created, and possibly
  the updates done by this utility/tool also will not be automatically replicated on the kubernetes object (like PVC).
  

## Below diagram represents how shares are mapped to CPG.
![3PAR persona hirarchy diagram](/docs/img/3PAR_FIlePersona_Share_Hierarchy.png)

---

## below are the default use cases and default behaviour with provided options

1. Create file share when only name of share is mentioned	
```
docker volume create -d hpe --name share_name
```
- User creates share under default CPG
- Default CPG is mentioned in hpe_file.conf file
- Default FPG OF 1TiB and Default store of size 64 GiB.
- To create a share under a specified fpg(FPG created via docker), user can specify -o size=x -o fpg=<fpg_name> where x is in GiB
  If Size is not specified it will always create a 64GiB store
- Here CPG, IP and mask will be picked from the conf file
- If IP and mask are not available then user need to supply it with -o
- ex. -o ipSubnet="192.168.68.38:255.255.192.0"
- If user wants to select 3 IPs from a pool to assign it to a vfs, user needs to provide this information
- with -o numOfInvolvedIps=2
- If these many ips are not available error will be thrown.

 2. Create file share on a particular cpg
 ```
 docker volume create -d hpe --name share_name -o cpg=CPG_name
 ```
 - User creates a share on non default CPG
 - Provided CPG will be used to create FPG or if FPG exist, available FPG will be used to create store and share
 - If FPG doesnt exist FPG will be created, with edfault value of FPG (1TiB)
 
 3. Create file share under particular FPG
 ```
 docker volume create -d hpe --name share_name -o fpg_name=FPG1
 ```
 - User want to use existing FPG created via docker
 - Here fpg_size store_name and size(Store Quota) will be created with default values unless mentioned.
 - If the fpg_name provided exist in 3PAR exception will be thrown
 - IF fpg is created via plugin and fpg_size is provided, exception will be thrown
 

