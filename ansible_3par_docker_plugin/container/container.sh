docker rmi -f sgkasif/hpe3par_docker_volume_plugin_installer:3.0
docker rmi -f container
docker image build --build-arg http_proxy=http://web-proxy.in.hpecorp.net:8080 --build-arg https_proxy=http://web-proxy.in.hpecorp.net:8080 --no-cache -t container .
docker tag container sgkasif/hpe3par_docker_volume_plugin_installer:3.0
docker push sgkasif/hpe3par_docker_volume_plugin_installer:3.0
