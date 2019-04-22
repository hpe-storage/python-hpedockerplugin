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

## Below are the default use cases and default behaviour with provided options

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
 - If the fpg_name provided exist in 3PAR and same is not available in docker we will proceed with creation of share under this fpg with 
 default values unless provided with -o option
 - IF fpg is created via plugin and fpg_size is provided, exception will be thrown
 

## Changes required to the configuration file
Following configuration parameters are required to support the above requirements:
1. **hpe3par_default_cpg:** Default CPG name to be used for FPG creation. User has the option to
override this value using the option **cpg**.
2. **hpe3par_default_fpg_size**: Default size to be used for FPG creation. If not specified in 
the configuration file, this value defaults to 1TB. User has the option override this using the
option **fpg_size**
3. **hpe3par_ip_pool**: List of IP addresses and corresponding subnet masks in the format:
*IP1:SubnetMask1,IP2:SubnetMask2,IP3:SubnetMask3...*


## Share Metadata
Efficient information lookup would be required for the following two cases:
1. Share lookup by name and
2. Available VFS lookup for hosting a new share

### Share lookup by name
This is required for retrieve, update, delete, mount and umount of a share.
To satisfy this requirement, we can continue to use *“/volumes/{id}”* ETCD key or have 
a new key as *“/shares/{id}”* under which below share metadata can be kept.
```
share_metadata = {
    # Backend name
    'backend': backend,
    
    # UUID of the share
    'id': <UUID>,
    
    # FPG name
    'fpg': <FPG>,
    
    # VFS name
    'vfs': <VFS>,
    
    # Dictionary having IP address as key and subnet-mask as value
    ‘vfsIPs': <Share-accessible-via-IPs>,
    
    # File store name with naming scheme as <shareName>_FSTORE
    'fstore': <FILE-STORE>,
    
    # Share name supplied by the user
    'shareName': <SHARE-NAME>,
    
    # Default is True
    'readonly': <True|False>,
    
    # Share size applied as quota on file store. Default value is 64GB.
    'size': <SHARE-QUOTA-LIMIT>,
    
    # NFS protocol options. If not supplied, 3PAR defaults will apply
    'protocolOpts': <NFS/SMB-PROTOCOL-OPTIONS>,
    
    # Placeholder for snapshot feature
    'snapshots': [],
    
    # Share description
    'comment': comment,
}
```

### Available VFS lookup for hosting a new share
Available VFS needs to be located when a new share is created with default parameters i.e. FPG
name is not specified on the Docker CLI.

To satisfy this requirement, the additional information needs to be maintained in ETCD under 
a new key called *“/file-persona/{backend}”*.

E.g. Below is a sample meta-data for a backend called *DEFAULT*, having two CPGs – CPG1 and CPG2,
to be stored under ETCD key *“/file-persona/DEFAULT”*:

```
{
    'cpg_fpg_map': {
        # Total numer of FPGs present on this backend
        'fpg_cnt': 3,
        
        # List of IPs currently in use by VFS on this backend
        'used_ips': ['ip1', 'ip2', 'ip3'],
        
        # Name of CPG (either supplied or default one picked up from configuration) 
        # as dictionary key
        'CPG1': {
            # Default current FPG under which a new share with default parameters to be created
            # This serves as an indexing key to the below 'fpgs' dictionary
            'default_current_fpg': 'DockerFPG-2'
            
            # FPGs dictionary
            'fpgs': {

                # Name of FPG (auto-generated) as dictionary key
                'DockerFPG-1': {
                    # FPG size in TB (Min=1TB, Max=64TB). Defaults to 1TB
                    'fpg_size': 3,
                    
                    # VFS name
                    'vfs': DockerVFS-1',

                    # Dictionary of IPs and corresponding subnet mask being used by
                    # VFS "DockerVFS-1"
                    'ips": {'ip1': 'subnet_mask1'},

                    # Total number of shares created under this FPG by the plugin
                    'share_cnt': 16,

                    # Flag indicating whether the maximum number of shares have been
                    # created under this FPG or not. This is needed in case the user
                    # supplies legacy FPG name during share creation and the FPG happens
                    # to already have some shares under it. In this case, 'share_cnt' will
                    # not be able to tell us if maximum limit has been reached and hence,
                    # this flag has been introduced.
                    'reached_full_capacity': True,
                },
                # Another FPG dictionary
                'DockerFPG-2': {
                    'fpg_size': 1,
                    'vfa': 'DockerVFS-2'
                    'ips': {'ip2': 'subnet_mask2'},
                    'share_cnt': 7,
                    'reached_full_capacity': False,
                }
            }
        },
        # Another CPG
        'CPG2': {
            'current_fpg': 'DockerFPG-3'
		   'fpg_cnt': 2,
            'fpgs': {
                'DockerFPG-3': {
                    'fpg_size': 4,
                    'vfs': DockerVFS-3'
                    'ips': {'ip3': 'subnet_mask3'},
                    'share_cnt': 11,
                    'reached_full_capacity': True,
                }	
            }
        }
    }
}
```
