## System Requirements

The v1.0.0 version of the plugin is supported on Ubuntu 14.04 and 16.04.
Versions starting at v1.1.0 have been tested and are supported on the following Linux distributions:

- Ubuntu 14.04 and 16.04
- RHEL 7.x and beyond
- CoreOS 1122.3.0 and beyond
- CentOS 7 and beyond

Although the plugin software is supported on these linux distributions, you should consult the Hewlett Packard Enterprise Single Point of Connectivity Knowledge (SPOCK) for HPE Storage Products for specific details about which operating systems are supported by HPE 3PAR StoreServ and StoreVirtual Storage products (https://www.hpe.com/storage/spock).

NOTE: Although other linux distributions have not been tested, the containerized version of the plugin should work as well.

Docker 1.11 and 1.12

Python 2.7 is supported.

etcd 2.x is supported.

Supported HPE 3PAR and StoreVirtual iSCSI storage arrays:

- OS version support for 3PAR (3.2.1 MU2, 3.2.2 upto MU3)
- OS version support for StoreVirtual (11.5, 12.6)

NOTE: 3PAR FC support is currently not available.
      Docker Swarm support is currently not avialable

Supported HPE 3PAR and StoreVirtual clients:

- python-3parclient version 4.0.0 or newer
- python-lefthandclient version 2.0.0 or newer

NOTE: Client support only applies when using the manual install instructions.
