hpedockerplugin:
  image: <plugin-image-name:tag>
  container_name: <container-name>
  net: host
  privileged: true
  volumes:
     - /dev:/dev
     - /var/run/docker/plugins:/var/run/docker/plugins:rw
     - /lib/modules:/lib/modules
     - /var/lib/docker/:/var/lib/docker
     - /etc/hpedockerplugin/data:/etc/hpedockerplugin/data:shared
     - /etc/iscsi/initiatorname.iscsi:/etc/iscsi/initiatorname.iscsi
     - /etc/hpedockerplugin:/etc/hpedockerplugin
     - /var/run/docker.sock:/var/run/docker.sock
