Running the hpedockerplugin with Docker Compose:

You can now start the hpedockerplugin using docker compose. Just do the following:

1. git clone git@github.com:hpe-storage/python-hpedockerplugin.git
2. git checkout containerize
3. cd python-hpedockerplugin/quick-start
4. Create an hpe.conf file and place it in the directory /etc/hpedockerplugin
5. docker-compose up -d

You should now have a containerized version of the hpedockerplugin running.

IMPORTANT NOTE: when running this image on CentOS/RHEL you should not bind mount /etc/iscsi in the docker compose file. This results in "Failed to get D-Bus connection: Operation not permitted". 

