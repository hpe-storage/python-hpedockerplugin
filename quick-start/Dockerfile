FROM ubuntu:14.04.4

ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH=${HOME}/python-hpedockerplugin:/root/python-hpedockerplugin

ADD id_rsa /root/.ssh/id_rsa
ADD apt.conf /etc/apt/apt.conf

RUN apt-get update && apt-get upgrade -y
#ADD pre-requisites
RUN apt-get install -y python-dev python-setuptools libffi-dev libssl-dev apt multipath-tools open-iscsi sysfsutils git
RUN easy_install pip
RUN pip install --upgrade pip
RUN pip install -U setuptools
RUN pip install pycrypto

#TODO: Enable git clone instead of manual copy of hpedockerplugin repo
#RUN git clone git@github.com:hpe-storage/python-hpedockerplugin.git 
COPY python-hpedockerplugin /python-hpedockerplugin

WORKDIR /python-hpedockerplugin
RUN pip install --upgrade .

RUN apt-get --yes install linux-image-extra-$(uname -r)
WORKDIR /python-hpedockerplugin
CMD ["/usr/local/bin/twistd", "--nodaemon", "hpe_plugin_service"]
