## File Permission and Ownership

This section describes the -o fsMode and -o fsOwner options used with volume creation in detail

### fsOwner option

To change the ownership of root directory of the filesystem, user needs to pass userId and groupID 
with this fsOwner option of docker volume create command.

#### Usage
-o fsOwner=X    X is the user id and group id that should own the root directory of the filesystem, in the form of [userId:groupId]

```
Example

# docker volume create -d hpe --name VOLUME -o size=1 -o fsOwner=1001:1001
VOLUME

# docker volume ls
DRIVER              VOLUME NAME
hpe:latest          VOLUME

# docker volume inspect VOLUME
[
    {
        "Driver": "hpe:latest",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/plugins/d669f6a28ed316f2cac5ef8c876fca66e7dafd63d5273366c7b5ab3638cd1a31/rootfs",
        "Name": "VOLUME",
        "Options": {
            "fsOwner": "1001:1001",
            "size": "1"
        },
        "Scope": "global",
        "Status": {
            "volume_detail": {
                "compression": null,
                "flash_cache": null,
                "fsMode": null,
                "fsOwner": "1001:1001",
                "mountConflictDelay": 30,
                "provisioning": "thin",
                "size": 1
            }
        }
    }
]

````
### fsMode Option

To change the mode of root directory of the filesystem, user needs to pass file mode in octal format 
with this fsMode option of docker volume create command.

#### Usage
-o fsMode=X    X is 1 to 4 octal digits that represent the file mode to be applied to the root directory of the filesystem.

````
Example

# docker volume create -d hpe --name VOLUME -o size=1 -o fsMode=0755
VOLUME

# docker volume ls
DRIVER              VOLUME NAME
hpe:latest          VOLUME

# docker volume inspect VOLUME
[
    {
        "Driver": "hpe:latest",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/plugins/d669f6a28ed316f2cac5ef8c876fca66e7dafd63d5273366c7b5ab3638cd1a31/rootfs",
        "Name": "VOLUME",
        "Options": {
            "fsMode": "0755",
            "size": "1"
        },
        "Scope": "global",
        "Status": {
            "volume_detail": {
                "compression": null,
                "flash_cache": null,
                "fsMode": "0755",
                "fsOwner": null,
                "mountConflictDelay": 30,
                "provisioning": "thin",
                "size": 1
            }
        }
    }
]

````
### Mounting a volume having ownership and permission.

In order to properly utilize the fsMode and fsowner options, user needs to mount the volume to a container using --user option.
By default container run as a root user, --user prvides the ability to run a container as a non-root user. 

#### Example
- Creating volume with fsMode and fsOwner
````
root@cld13b9:~/Secret_Management# docker volume create -d hpe --name VOLUME -o size=1 -o fsMode=0444 -o fsOwner=1001:1001
VOLUME
````
- Inspecting the volume created to verify the fsMode and fsOwner
````
root@cld13b9:~/Secret_Management# docker volume inspect VOLUME
[
    {
        "Driver": "hpe:latest",
        "Labels": {},
        "Mountpoint": "/var/lib/docker/plugins/d669f6a28ed316f2cac5ef8c876fca66e7dafd63d5273366c7b5ab3638cd1a31/rootfs",
        "Name": "VOLUME",
        "Options": {
            "fsMode": "0444",
            "fsOwner": "1001:1001",
            "size": "1"
        },
        "Scope": "global",
        "Status": {
            "volume_detail": {
                "compression": null,
                "flash_cache": null,
                "fsMode": "0444",
                "fsOwner": "1001:1001",
                "mountConflictDelay": 30,
                "provisioning": "thin",
                "size": 1
            }
        }
    }
]
````
- Mounting volume to  a container with uid:gid as 1002:1002 using --user option
````
# docker run -it -v VOLUME:/data1 --rm --user 1002:1002 --volume-driver hpe busybox /bin/sh
/ $ ls -lrth
total 40
drwxr-xr-x    2 root     root       12.0K May 22 17:00 bin
drwxr-xr-x    4 root     root        4.0K May 22 17:00 var
drwxr-xr-x    3 root     root        4.0K May 22 17:00 usr
drwxrwxrwt    2 root     root        4.0K May 22 17:00 tmp
drwx------    2 root     root        4.0K May 22 17:00 root
drwxr-xr-x    2 nobody   nogroup     4.0K May 22 17:00 home
dr--r--r--    2 1001     1001        4.0K Jul 30 09:59 data1
drwxr-xr-x    3 root     root        4.0K Jul 30 10:00 etc
dr-xr-xr-x  445 root     root           0 Jul 30 10:00 proc
dr-xr-xr-x   13 root     root           0 Jul 30 10:00 sys
drwxr-xr-x    5 root     root         360 Jul 30 10:00 dev
/ $ id
uid=1002 gid=1002
/ $
````
Here data1 is mountpoint. Permission of data1 can be seen as what we have provided while creating the volume and uid and gid 
of the container is 1002:1002 as provided in mount command.


**NOTE:** Snapshots and clones retain the same permissions as provided to the parent volume.

