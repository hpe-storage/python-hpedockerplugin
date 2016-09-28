#Running the hpedockerplugin with Docker Compose:

You can now start the hpedockerplugin using docker compose. Just do one of the following:

##Build and run the container image from source
1. git clone git@github.com:hpe-storage/python-hpedockerplugin.git
2. cd python-hpedockerplugin/quick-start
3. run ./containerize.sh
4. tag the image (e.g. docker tag <image-id> myhpedockerplugin:latest
5. Create an hpe.conf file and place it in the directory /etc/hpedockerplugin
6. copy and edit the docker-compose.yml.example as appropriate to your env
7. docker-compose up -d

##Run the container using a already created image
1. Create an hpe.conf file and place it in the directory /etc/hpedockerplugin
2. copy and edit the docker-compose.yml.example as appropriate to your env (with appropriate image name)
3. docker-compose up -d

You should now have a containerized version of the hpedockerplugin running.

##Restarting the plugin
IMPORTANT NOTE: The /run/docker/plugins/hpe/hpe.sock and /run/docker/plugins/hpe/hpe.sock.lock files are not automatically removed when you stop the container. Therefore, these files will need to be removed between each run of the plugin.

#Running the hpedockerplugin on different linux distros:

Make sure to set **MountFlags=shared** in the docker.service. This is required to ensure the hpedockerplugin can write to /hpeplugin

1. CentOS/RHEL: You now need to bind mount /etc/iscsi/initiatorname.iscsi in the docker compose file. The Alpine linux based version of the container does not come with an iscsi initiator. Therefore, you must bind mount an iscsi initiator for the plugin to work properly. 

2. CoreOS: make sure to also bind mount /lib/modules. Otherwise, you'll get the following error in the hpedockerpluin logs:

iscsiadm: initiator reported error (12 - iSCSI driver not found. Please make sure it is loaded, and retry the operation)

