## Multipath Support

This section describes steps that should be performed to properly enable multipath support with the HPE 3PAR StoreServ and HPE Docker Volume Plugin. The below steps are only applicable if HPE 3PAR Docker Volume plugin is deployed as a container via Containerized Docker plugin system.

### Multipath Settings

When multipathing is required with the HPE 3PAR StoreServ, you must update the multipath.conf, iscsid.conf, docker-compose.yml, and hpe.conf files as outlined below.  The procedures below are only examples, please review the appropriate HPE 3PAR StoreServ Implementation Guide and the [Single Point of Connectivity Knowledge (SPOCK)] (https://www.hpe.com/storage/spock) website for updated support requirements.

> ##### Note
> Although the procedure below requires multipath.conf and iscsid.conf files to be created, neither multipath-tools or open-iscsi are should be installed on the container host.  If either exists, please uninstall them as they will cause unexpected behavior with both volume mount and unmount operations.

#### /etc/multipath.conf

You can find details on how to properly configure multipath.conf in the [HPE 3PAR Red Hat Enterprise Linux and Oracle Linux Implementation Guide] (http://h20565.www2.hpe.com/hpsc/doc/public/display?docId=c04448818).

Below is an example multipath.conf file. Please review the HPE 3PAR Red Hat Enterprise Linux and Oracle Linux Implementation Guide for any required updates.

```
defaults {
                polling_interval 10
                max_fds 8192
        }

        devices {
                device {
                        vendor                  "3PARdata"
                        product                 "VV"
                        no_path_retry           18
                        features                "0"
                        hardware_handler        "0"
                        path_grouping_policy    multibus
                        #getuid_callout         "/lib/udev/scsi_id --whitelisted --device=/dev/%n"
                        path_selector           "round-robin 0"
                        rr_weight               uniform
                        rr_min_io_rq            1
                        path_checker            tur
                        failback                immediate
                }
        }
```

#### /etc/iscsi/iscsid.conf

You can find details on how to properly configure multipath.conf in the [HPE 3PAR Red Hat Enterprise Linux and Oracle Linux Implementation Guide] (http://h20565.www2.hpe.com/hpsc/doc/public/display?docId=c04448818).

Change the following iSCSI parameters in /etc/iscsi/iscsid.conf.  Please review the HPE 3PAR Red Hat Enterprise Linux and Oracle Linux Implementation Guide for any required updates.

```
node.startup = automatic
node.conn[0].startup = automatic
node.session.timeo.replacement_timeout = 10
node.conn[0].timeo.noop_out_interval = 10
```

#### docker-compose.yml

The files previously modified need to be made available to the HPE Docker Volume Plugin container.  Below is an example docker-compose.yml file.  Notice the addition of /etc/iscsi/iscsid.conf and /etc/multipath.conf.

```
hpedockerplugin:
   image: hpe-storage/python-hpedockerplugin:<tag>
   container_name: hpeplugin
   net: host
   privileged: true
   volumes:
      - /dev:/dev
      - /run/docker/plugins:/run/docker/plugins
      - /lib/modules:/lib/modules
      - /var/lib/docker/:/var/lib/docker
      - /etc/hpedockerplugin/data:/etc/hpedockerplugin/data:shared
      - /etc/iscsi/initiatorname.iscsi:/etc/iscsi/initiatorname.iscsi
      - /etc/hpedockerplugin:/etc/hpedockerplugin
      - /var/run/docker.sock:/var/run/docker.sock
      - /home/docker/.ssh:/home/docker/.ssh
      - /etc/iscsi/iscsid.conf:/etc/iscsi/iscsid.conf
      - /etc/multipath.conf:/etc/multipath.conf
```

#### /etc/hpedockerplugin/hpe.conf

Lastly, make the following additions to the /etc/hpedockerplugin/hpe.conf file to enable multipathing.

 ```
use_multipath = True
enforce_multipath = True
```
