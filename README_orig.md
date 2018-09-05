## HPE Docker Volume Plugin

The HPE Docker Volume Plugin is open source software that provides persistent block storage for containerized applications using HPE 3PAR StoreServ Storage. 

## HPE Docker Volume Plugin Overview
The following diagram illustrates the HPE Docker Volume Plugin configured on multiple hosts in a Docker cluster. The plugin is a part of Docker Engine Managed Plugin System. See the [quick start instructions](/quick-start/README.md) for details on how to install the plugin.


![HPE Docker Volume Plugin](/docs/img/HPE-DockerVolumePlugin-Overview.png "Storage Overview")

## Install and Quick Start instructions

* Review the [System Requirements](/docs/system-reqs.md) before installing the plugin
* Deploying the plugin into Docker Engine Managed Plugin System [quick-start instructions](/quick-start/README.md)


## Supported Features by Release

* Release v1.0 - Initial Realease - iSCSI driver for 3PAR
* Release v1.1 - Support for multipath and key defect fixes around volume mount operations
* Release v2.0 - Support for secure / unsecure etcd cluster for fault tolerance - Fibre Channel Driver for 3PAR
* Release v2.1 - Support for creating volumes of type thin, dedup, full, compressed volumes, snapshots, clones, 
   QoS, snapshot mount, mount_conflict_delay, and multiple container access for a volume on same node.
   Plugin supports both iscsi and FC drivers.

## Usage

See the [usage instructions](/docs/usage.md) for details on the supported operations and usage of the plugin.

## Troubleshooting

Troubleshooting issues with the plugin can be performed using these [tips](/docs/troubleshooting.md) 

## Contributions

This section describes steps that should be done when creating contributions for this plugin.

Review the [Contribution instructions](/docs/contribute.md) 

