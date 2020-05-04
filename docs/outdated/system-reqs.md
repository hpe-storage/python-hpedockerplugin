## System Requirements

The v1.0 or later version of HPE 3PAR and HPE Primera Volume plugin of Docker Engine Managed plugin system is supported and available now on Docker store (https://store.docker.com/plugins/hpe-3par-docker-volume-plugin/).
Versions starting at v1.0 have been tested and are supported on the following Linux distributions:

* Ubuntu 16.04
* RHEL 7.x
* CentOS 7.x
* SLES 12 SP3

**Supported Openshift/Kubernetes Versions**
* Openshift 3.9, 3.10, 3.11
* Kubernetes 1.11, 1.12, 1.13, 1.14 and 1.15

>**NOTE:** 
 - Although the plugin software is supported on the listed Linux distributions, you should consult the Hewlett Packard Enterprise Single Point of Connectivity Knowledge (SPOCK) for HPE Storage Products for specific details about which operating systems are supported by HPE 3PAR and HPE Primera (https://www.hpe.com/storage/spock).
 - Although other Linux distributions have not been tested, the containerized version of the plugin should work as well.
 - Also, ensure the docker engine version should not exceed 19.03.4.

**Supported software versions:**

* Docker EE/CE version from 17.03 to 19.03.4 is supported
* Python 2.7
* etcd 2.x

**Supported HPE 3PAR storage arrays:**

* OS version support for 3PAR OS 3.2.1 MU2, MU4, 3.3.1 MU1, MU2 and HPE Primera OS 4.0.0
