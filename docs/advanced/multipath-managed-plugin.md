## Multipath Support

This section describes steps that should be performed to properly enable multipath support with the HPE 3PAR StoreServ and HPE Docker Volume Plugin. Also, this is only applicable if HPE 3PAR Docker plugin is installed from Docker store via Docker Managed plugin system.

### Multipath Settings

When multipathing is required with the HPE 3PAR StoreServ, you must update the multipath.conf and hpe.conf files as outlined below.  The procedures below are only examples, please review the appropriate HPE 3PAR StoreServ Implementation Guide and the [Single Point of Connectivity Knowledge (SPOCK)] (https://www.hpe.com/storage/spock) website for updated support requirements.

> ##### Note
> 1. If 3PAR Fibre Channel plugin is configured for use, two or more fibre channel ports of container host and HPE 3PAR StoreServ must be in same zone.
> 2. "multipath-tools" and "open-iscsi" should be installed on container host.
> 3. Please make sure multipathd daemon is enabled and running correctly i.e. the output of commands like "multipath -ll" and "multipathd show status" should be valid.

#### /etc/multipath.conf

You can find details on how to properly configure multipath.conf in the [HPE 3PAR Red Hat Enterprise Linux and Oracle Linux Implementation Guide] (http://h20565.www2.hpe.com/hpsc/doc/public/display?docId=c04448818).

Below is an example multipath.conf file which works correctly in RHEL and CentOS platforms. Please review the HPE 3PAR Red Hat Enterprise Linux and Oracle Linux Implementation Guide for any required updates.

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


#### /etc/hpedockerplugin/hpe.conf

Lastly, make the following additions to the /etc/hpedockerplugin/hpe.conf file to enable multipathing for HPE 3PAR iSCSI volume plugin.

```
hpe3par_iscsi_ips = <iSCSI IP addresses separated by comma>
```
