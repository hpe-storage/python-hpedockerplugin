docker rmi -f sgkasif/test:1.0
docker rmi -f container
docker image build --no-cache -t container .
docker tag container sgkasif/test:1.0
docker push sgkasif/test:1.0
