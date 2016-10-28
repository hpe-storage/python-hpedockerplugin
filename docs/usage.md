## Usage
The following are the currently supported actions that can be taken using the HPE Docker plugin.

#### Creating an HPE volume

```
sudo docker volume create -d hpe --name <vol_name>
```

There are several optional parameters that can be used during volume creation:

- size -- specifies the desired size in GB of the volume.
- provisioning -- specifies the type of provisioning to use (thin, full, dedup).
- flash-cache -- specifies whether flash cache should be used or not (True, False).

Note: Setting flash-cache to True does not gurantee flash-cache will be used. The backend system
must have the appropriate SSD setup configured, too.

The following is an example call creating a full provisioned, 50 GB volume:

```
sudo docker volume create -d hpe --name <vol_name> -o size=50 -o provisioning=full
```

Note -- The dedup provisioning and flash-cache options are only supported by the
3PAR StoreServ driver currently.

#### Deleting a volume

```
sudo docker volume rm <vol_name>
```

#### List volumes

```
sudo docker volume ls
```

#### Inspect a volume

```
sudo docker volume inspect <vol_name>
```

#### Mounting a volume

Use the following command to mount a volume and start a bash prompt:

```
sudo docker run -it -v <vol_name>:/<mount_point>/ --volume-driver hpe <image_name> bash
```

Note: If the volume does not exist it will be created.

The image used for mounting can be any image located on https://hub.docker.com/ or
the local filesystem. See https://docs.docker.com/v1.8/userguide/dockerimages/
for more details. 

#### Unmounting a volume

Exiting the bash prompt will cause the volume to unmount:

```
exit
```

The volume is still associated with a container at this point.

Run the following command to get the container ID associated with the volume:

```
sudo docker ps -a
```

Then stop the container:

```
sudo docker stop <container_id>
```

Next, delete the container:

```
sudo docker rm <container_id>
```

Finally, remove the volume:

```
sudo docker volume rm <vol_name>
```
