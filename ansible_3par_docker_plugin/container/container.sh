docker rmi -f sgkasif/hpe3par_docker_volume_plugin_installer:1.0
docker rmi -f container
docker image build --no-cache -t container .
docker tag container sgkasif/hpe3par_docker_volume_plugin_installer:1.0
docker push sgkasif/hpe3par_docker_volume_plugin_installer:1.0
