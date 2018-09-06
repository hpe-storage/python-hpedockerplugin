## HPE Docker Volume Plugin for HPE 3PAR StoreServ

HPE Docker Volume Plugin is an open source project that provides persistent storage and features for your containerized applications using HPE 3PAR StoreServ Storage arrays.

The HPE Docker Volume Plugin supports popular container platforms like Docker, Kubernetes, OpenShift and soon SuSE CaaS/CAP (coming in v3.0)

## Getting Started

Before we get started, you need to make a choice on how you will be using the plugin.

#### Standalone Docker instance

Here is an example of the plugin being used in a standalone Docker instance:

![HPE Docker Volume Plugin](https://github.com/budhac/python-hpedockerplugin/blob/master/docs/img/3PAR_docker_design_diagram.png)


## HPE Docker Volume Plugin Overview
The following diagram illustrates the HPE Docker Volume Plugin configured on multiple hosts in a Docker cluster. The plugin is a part of Docker Engine Managed Plugin System. See the [quick start instructions](/quick-start/README.md) for details on how to install the plugin.


![HPE Docker Volume Plugin](/docs/img/HPE-DockerVolumePlugin-Overview.png "Storage Overview")

## Install and Quick Start instructions

* Review the [System Requirements](/docs/system-reqs.md) before installing the plugin
* Deploying the plugin into Docker Engine Managed Plugin System [quick-start instructions](/quick-start/README.md)


## Supported Features

* Fibre Channel & iSCSI support for 3PAR
* Secure/Unsecure etcd cluster for fault tolerance
* Advanced volume features
  * thin
  * dedup
  * full
  * compression
  * snapshots
  * clones
  * QoS
  * snapshot mount
  * mount_conflict_delay
  * concurrent volume access

## Usage

See the [usage instructions](/docs/usage.md) for details on the supported operations and usage of the plugin.

## Troubleshooting

Troubleshooting issues with the plugin can be performed using these [tips](/docs/troubleshooting.md)

## Contributions

This section describes steps that should be done when creating contributions for this plugin.

Review the [Contribution instructions](/docs/contribute.md)
