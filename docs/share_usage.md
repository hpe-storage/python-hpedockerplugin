# File Persona usage guide

The HPE 3PAR File Persona feature allows user to manage file 
shares on 3PAR arrays through Docker interface.

In order to use HPE 3PAR File Persona feature, user needs to 
configure a backend one for each target array as below:

#### Configuring backend for file share

```sh
[DEFAULT]

# ssh key file required for driver ssh communication with array
ssh_hosts_key_file = /root/.ssh/known_hosts

# IP Address and port number of the ETCD instance
# to be used for storing the share meta data
host_etcd_ip_address =  10.50.164.1
host_etcd_port_number = 2379

# Client certificate and key details for secured ETCD cluster
# host_etcd_client_cert = /root/plugin/certs/client.pem
# host_etcd_client_key = /root/plugin/certs/client-key.pem

# Logging level for the plugin logs
logging = DEBUG

# Logging level for 3PAR client logs
hpe3par_debug = True

# Suppress Requests Library SSL warnings
suppress_requests_ssl_warnings = True

# Set the driver to be File driver
hpedockerplugin_driver = hpedockerplugin.hpe.hpe_3par_file.HPE3PARFileDriver

hpe3par_api_url = https://10.50.3.24:8080/api/v1
hpe3par_username = 3paradm
hpe3par_password = 3pardata
hpe3par_san_ip = 10.50.3.24
hpe3par_san_login = 3paradm
hpe3par_san_password = 3pardata

# Server IP pool is mandatory and can be specified as a mix of range of IPs and
# individual IPs delimited by comma
# Each range or individual IP must be followed by the corresponding subnet mask
# delimited by semi-colon
# E.g.: IP-Range:Subnet-Mask,Individual-IP:SubnetMask…
hpe3par_server_ip_pool = 192.168.98.8-192.168.98.13:255.255.192.0

# Default size of FPG to be in the range 1TiB – 64TiB. If not specified here, it defaults to 64
hpe3par_default_fpg_size = 10 
```
User can define multiple backends in case more than one array needs to be managed by the plugin.

User can also define backends for block driver(s) along with file driver(s). 
However, a default backend is mandatory for both block and file drivers for the default use cases 
to work. Since ‘DEFAULT’ section can be consumed by either 
block or file driver but not both at the same time, the other driver
is left out without a default backend. In order to satisfy the need for the other 
driver to have default backend, HPE 3PAR Plugin introduces two new keywords to 
denote default backend names to be used in such a situation:
1. DEFAULT_FILE and
2. DEFAULT_BLOCK

In case where user already has ‘DEFAULT’ backend configured for 
block driver, and file driver also needs to be configured, then 
‘DEFAULT_FILE’ backend MUST be defined. In this case, if there 
is a non-default backend defined for file driver without 
'DEFAULT_FILE' backend defined, plugin won't get initialized 
properly.

Similarly, for the vice-versa case, where ‘DEFAULT’ is configured
 as file driver and the user wants to configure block driver now. 
 In this case, ‘DEFAULT_BLOCK’ MUST be configured for the plugin 
 to work correctly.

Below is that table of all possible default configurations along
with the behavior column for each combination:

|DEFAULT | DEFAULT_BLOCK | DEFAULT_FILE | BEHAVIOR        |
|--------|---------------|--------------|-----------------|
|BLOCK   |--             |--            | Okay            |
|FILE    |--             |--            | Okay            |
|--      |BLOCK |-- |DEFAULT_BLOCK becomes the default for Block driver|
|--      |-- |FILE  |DEFAULT_FILE becomes the default for File driver|
|BLOCK   |-- |FILE  |DEFAULT_FILE becomes the default for File driver|
|FILE    |BLOCK |-- |DEFAULT_BLOCK becomes the default for Block driver|
|BLOCK   |BLOCK |FILE  |DEFAULT_BLOCK becomes like any other non-default backend in multi-backend configuration for Block driver. DEFAULT_FILE becomes the default for File driver|
|FILE    |BLOCK |FILE |DEFAULT_FILE becomes like any other non-default backend in multi-backend configuration for File driver. DEFAULT_BLOCK becomes the default for Block driver|
|BLOCK   |FILE |--  |DEFAULT_BLOCK is not allowed to be configured for File driver. Plugin initialization fails in this case.|
|FILE   |-- |BLOCK  |DEFAULT_FILE is not allowed to be configured for Block driver. Plugin initialization fails in this case.|


Although HPE does not recommended it, but if the user configures multiple backends that are identical in terms of target array and CPG, then the default FPG created for such backends would not be the same – rather a different default FPG would be created for each backend.

### Command to create HPE share
```sh
$ docker volume create –d hpe --name <Share-name> <-o filePersona> 
[ -o size=<Share-size-in-GiB>  –o cpg=<CPG-name>  -o fpg=<FPG-name> ]
```

**Where:**

- ***size:*** specifies the desired size of the share in GiB. By default it is 1024 GiB.  
- ***cpg:*** specifies the cpg to be used for the share. This parameter can be used with or without ‘fpg’ option. When used with ‘fpg’, the FPG is created with the specified name if it doesn’t exist. If it does exist, then share is created under it. When used without ‘fpg’ option, default FPG under the specified CPG is selected for share creation. If default FPG doesn’t exist, a new default FPG is created under which the share is created.
- ***fpg:*** FPG to be used for share creation. If the FPG does not exist, a new FPG with the specified name is created using either the CPG specified using ‘cpg’ option or specified in configuration file.
- ***fsOwner:*** fsOwner is the user id and group id that should own the root directory of NFS file share in the form [userId:groupId]. Administrator must ensure that local user and local group with these IDs are present on 3PAR before trying to mount the share otherwise mount will fail.
- ***fsMode:*** the value of fsMode is 1 to 4 octal digits representing the file mode to be applied to the root directory of the file system. Ex: fsMode="0754". Here 0 as the first digit is mandatory. This ensures specified user of fsOwner will have rwx permissions, group will have r-x permissions and others will have just the read permission.
fsMode can also be an ACL string representing ACL permissions that are applied on the share directory. It contains three ACEs delimited by comma with each ACE consisting of three parts:

    1. type,
    2. flag and
    3. permissions

    These three parts are delimited by semi-colon.
    Out of the three ACEs in the ACL, the first ACE represents the ‘owner’, second one the ‘group’ and the third one ‘everyone’ to be specified in the same order.

    E.g.: ```sh A:fd:rwa,A:g:rwaxdnNcCoy,A:fdS:DtnNcy```

    * type field can take only one of these values [A,D,U,L]
    * flag field can take one or more of these values [f,d,p,i,S,F,g]
    * permissions field can take one or more of these values [r,w,a,x,d,D,t,T,n,N,c,C,o,y]  

    Please refer 3PAR CLI user guide more details on meaning of each flag.  
    **Note:** For fsMode values user can specify either of mode bits or ACL string. Both cannot be used simultaneously. While using fsMode it is mandatory to specify fsOwner. If Only fsMode is used, user will not be able to mount the share. 

##### Creating default HPE share  
```  
docker volume create -d hpe --name <share_name> -o filePersona  
```  
This command creates share of default size 1TiB with name ‘share_name’ on 
default FPG. If default FPG is not present, then it is created on the CPG 
specified in configuration file hpe.conf. If ‘hpe3par_default_fpg_size’ is 
defined in hpe.conf, then FPG is created with the specified size. Otherwise, 
FPG is created with default size of 16TiB.  

‘size’ can be specified to create a share of size other than default size of 1TiB.  

  
##### Creating a share using non-default CPG  
  
```  
docker volume create -d hpe --name <share_name> -o filePersona -o cpg=<cpg_name>  
```  
This command creates share of default size 1TiB on the default FPG whose parent CPG is ‘cpg_name’. If default FPG is not present, it is created on CPG ‘cpg_name’ with size ‘hpe3par_default_fpg_size’ if it is defined in hpe.conf. Else its size defaults to 16TiB.

‘size’ can be specified to create a share of size other than default size of 1TiB.  
  
##### Creating a share using non-default or legacy FPG  
```  
docker volume create -d hpe --name <share_name> -o filePersona -o fpg=<fpg_name>  
```  
This command creates share of size 1TiB by default on the specified FPG ‘fpg_name’. If the FPG ‘fpg_name’ does not exist, then it is created on the CPG specified in hpe.conf. Please note that the FPG can either be Docker managed FPG or a legacy FPG. In either case, the FPG must have enough capacity to accommodate the share.

‘size’ can be specified to create a share of size other than default size of 1TiB.  
  
##### Creating a share on a non-default FPG and CPG  
```  
docker volume create -d hpe --name <share_name> -o filePersona -o fpg=<fpg_name> -o cpg=<cpg_name>  
```  
This command creates share of default size 1TiB on the specified FPG ‘fpg_name’. If the FPG ‘fpg_name’ does not exist, then it is created on the specified CPG. Please note that the FPG can either be Docker managed FPG or a legacy FPG. However, in both these cases, the specified CPG must match the parent CPG of the FPG. Else, the operation results in error.

‘size’ can be specified to create a share of size other than default size of 1TiB.  

**Note**: The FPG must have enough capacity to accommodate the share.

##### Displaying help
```  
docker volume create -d hpe -o filePersona –o help  
```  
This command displays help content of the file command with possible options that can be used with it.
