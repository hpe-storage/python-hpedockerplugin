## Multipath Support

This section describes steps that should be done to properly enable multipath support with the plugin

#### Multipath Settings

In order for multipathing to work properly on 3PAR, you must update the multipath.conf and iscsi.conf files appropriately. You can find details on how to properly configure these files in the [HPE 3PAR Red Hat Enterprise Linux and Oracle Linux Implementation Guide] (http://h20566.www2.hpe.com/hpsc/doc/public/display?docId=c04448818). These instructions apply to deployments on any of the supported Linux distros.

You should then simply bind mount these new files into the plugin. Here's an example of the changes to a docker-compose.yml file:

```
hpedockerplugin:
   image: <plugin-image-name>
   container_name: <container-name>
   net: host
   privileged: true
   volumes:
      - /dev:/dev
      - /root/.ssh:/root/.ssh
      - /run/docker/plugins:/run/docker/plugins
      - /lib/modules:/lib/modules
      - /var/lib/docker/:/var/lib/docker
      - /etc/hpedockerplugin/data:/etc/hpedockerplugin/data:shared
      - /etc/iscsi/initiatorname.iscsi:/etc/iscsi/initiatorname.iscsi
      - /etc/hpedockerplugin:/etc/hpedockerplugin
      - /var/run/docker.sock:/var/run/docker.sock
      - /etc/multipath.conf:/etc/multipath.conf
      - /etc/iscsi/iscsid.conf:/etc/iscsi/iscsid.conf
```
