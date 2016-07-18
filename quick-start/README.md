##Running the hpedockerplugin with Docker Compose:

You can now start the hpedockerplugin using docker compose. Just do the following:

1. git clone git@github.com:hpe-storage/python-hpedockerplugin.git
2. git checkout containerize
3. cd python-hpedockerplugin/quick-start
4. Create an hpe.conf file and place it in the directory /etc/hpedockerplugin
5. docker-compose up -d

You should now have a containerized version of the hpedockerplugin running.

##Running the hpedockerplugin on different linux distros:

Make sure to set **MountFlags=shared** in the docker.service. This is required to ensure the hpedockerplugin can write to /hpeplugin

1. CentOS/RHEL: should not bind mount /etc/iscsi in the docker compose file. This results in "Failed to get D-Bus connection: Operation not permitted". 

2. CoreOS: make sure to also bind mount /lib/modules. Otherwise, you'll get the following error in the hpedockerpluin logs:

iscsiadm: initiator reported error (12 - iSCSI driver not found. Please make sure it is loaded, and retry the operation)

