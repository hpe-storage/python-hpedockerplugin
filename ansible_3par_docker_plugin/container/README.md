# Docker Volume Plugin Installer - Docker Image

This is an Alpine based image with Ansible and its dependency installed along with the latest HPE 3PAR docker volume plugin ansible installer tasks and playbooks.

Usage:

- Run the latest docker image from docker hub, the command below will run the pre built container and open shell
  - `docker run -it hpestorage/legacyvolumeplugininstaller /bin/sh`

- Set the proxy (if required)
  - `export http_proxy=<your-proxy>:<your-port>`
  - `export https_proxy=<your-proxy>:<your-port>`
  
- Follow [this link](/ansible_3par_docker_plugin/README.md) to set the node information, backend properties and run the installation playbook
