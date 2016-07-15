FROM ubuntu:14.04.4
#FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV FTP_PROXY=http://proxy.houston.hpecorp.net:8080/
ENV HTTPS_PROXY=http://proxy.houston.hpecorp.net:8080/
ENV https_proxy=http://proxy.houston.hpecorp.net:8080/
ENV no_proxy=localhost,127.0.0.1,10.0.0.0/16,169.254.169.254,10.50.0.0/16
ENV HTTP_PROXY=http://proxy.houston.hpecorp.net:8080/
ENV ftp_PROXY=http://proxy.houston.hpecorp.net:8080/
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
