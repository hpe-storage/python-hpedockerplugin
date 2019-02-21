docker rmi -f hpestorage/legacyvolumeplugininstaller:3.1
docker rmi -f container
docker image build --build-arg http_proxy=$1 --build-arg https_proxy=$2 --no-cache -t hpestorage/legacyvolumeplugininstaller:3.1 -t hpestorage/legacyvolumeplugininstaller:latest .
#docker tag container hpestorage/legacyvolumeplugininstaller:3.1 
docker push hpestorage/legacyvolumeplugininstaller:3.1
docker push hpestorage/legacyvolumeplugininstaller:latest
