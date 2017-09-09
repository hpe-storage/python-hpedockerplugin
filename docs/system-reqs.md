## System Requirements

The v1.0 or later version of 3PAR Volume plugin of Docker Engine Managed plugin system is supported and available now on Docker store (https://store.docker.com/plugins/hpe-3par-docker-volume-plugin/).
Versions starting at v1.0 have been tested and are supported on the following Linux distributions:

- Ubuntu 16.04
- RHEL 7.3
- CentOS 7.3

Although the plugin software is supported on these linux distributions, you should consult the Hewlett Packard Enterprise Single Point of Connectivity Knowledge (SPOCK) for HPE Storage Products for specific details about which operating systems are supported by HPE 3PAR StoreServ and StoreVirtual Storage products (https://www.hpe.com/storage/spock).

NOTE: Although other linux distributions have not been tested, the containerized version of the plugin should work as well.

Docker EE 17.03 or later is supported.

Python 2.7 is supported.

etcd 2.x is supported.

Supported HPE 3PAR storage arrays:

- OS version support for 3PAR (3.3.1 MU1)

Supported HPE 3PAR client:

- python-3parclient version 4.0.0 or newer
