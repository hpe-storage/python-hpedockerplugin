docker rmi -f hpestorage/legacyvolumeplugininstaller:3.1
docker rmi -f container
docker image build --build-arg http_proxy=http://web-proxy.in.hpecorp.net:8080 --build-arg https_proxy=http://web-proxy.in.hpecorp.net:8080 --no-cache -t container .
docker tag container hpestorage/legacyvolumeplugininstaller:3.1 hpestorage/legacyvolumeplugininstaller:latest
docker push hpestorage/legacyvolumeplugininstaller:3.1 hpestorage/legacyvolumeplugininstaller:latest
