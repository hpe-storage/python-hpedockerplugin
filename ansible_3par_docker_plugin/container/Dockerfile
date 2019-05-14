FROM alpine:3.8

MAINTAINER Farhan Nomani <nomani@hpe.com>

RUN echo "===> Installing sudo to emulate normal OS behavior..."  && \
    apk --update add sudo                                         && \
    \
    \
    echo "===> Adding Python runtime..."  && \
    apk --no-cache add ca-certificates && \
    apk --update add python py-pip openssl unzip && \
    apk --update add --virtual build-dependencies wget \
                openssh-keygen openssh-server openssh-client \
                python-dev libffi-dev openssl-dev build-base  && \
    pip install --upgrade pip pycrypto cffi                   && \
    \
    \
    echo "===> Installing Ansible..."  && \
    pip install ansible         && \
    \
    wget https://github.com/hpe-storage/python-hpedockerplugin/archive/master.zip

RUN unset http_proxy
RUN unset https_proxy
RUN unzip master.zip

RUN rm -f master.zip
RUN mv python-hpedockerplugin-master/ansible_3par_docker_plugin/ .
RUN rm -rf python-hpedockerplugin-master/
