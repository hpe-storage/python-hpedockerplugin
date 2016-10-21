FROM alpine:3.4

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH=${HOME}/python-hpedockerplugin:/root/python-hpedockerplugin


RUN apk add --no-cache --update \
	iscsi-scst \
    multipath-tools \
    open-iscsi \
    py-pip \
    py-setuptools \
    python \
    sysfsutils \
    util-linux \
    eudev \
	sudo \
 && apk update \
 && apk upgrade \
 && apk add e2fsprogs ca-certificates wget \ 
 && pip install --upgrade pip \
    setuptools \
 && rm -rf /var/cache/apk/*

COPY . /python-hpedockerplugin

RUN apk add --virtual /tmp/.temp --no-cache --update \
    build-base \
    g++ \
    gcc \
    libffi-dev \
    linux-headers \
    make \
    openssl \
	openssh-client \
	openssl-dev \
    python-dev \

# Need different version of pyasn1 for iscsi to work properly
 && wget https://pypi.python.org/packages/f7/83/377e3dd2e95f9020dbd0dfd3c47aaa7deebe3c68d3857a4e51917146ae8b/pyasn1-0.1.9.tar.gz \
# && wget http://10.50.177.1:8088/tmp/pyasn1-0.1.9.tar.gz \
 && tar xvzf pyasn1-0.1.9.tar.gz \
 && cd pyasn1-0.1.9 \
 && python setup.py install \
 && rm -rf pyasn1-0.1.9 \

# build and install hpedockerplugin
 && cd /python-hpedockerplugin \
 && pip install --upgrade . \
 && python setup.py install \

# apk Cleanups
 && apk del /tmp/.temp \
 && rm -rf /var/cache/apk/*

# We need to have a link to mkfs so that our fileutil module does not error when 
# importing mkfs from the sh module. e2fsprogs does not this by default.
# TODO: Should be a way to fix in our python module
#RUN ln -s /sbin/mkfs.ext4 /sbin/mkfs

# create known_hosts file for ssh
RUN mkdir -p /root/.ssh
RUN touch /root/.ssh/known_hosts
RUN chown -R root:root /root/.ssh
RUN chmod 0600 /root/.ssh/known_hosts

WORKDIR /python-hpedockerplugin
ENTRYPOINT ["/bin/sh", "-c", "./plugin-start"]

# Update version.py
ARG TAG
ARG GIT_SHA
ARG BUILD_DATE
RUN sed -i \
    -e "s|{TAG}|$TAG|" \
    -e "s/{GIT_SHA}/$GIT_SHA/" \
    -e "s/{BUILD_DATE}/$BUILD_DATE/" \
    /python-hpedockerplugin/hpedockerplugin/version.py

ENV TAG $TAG
ENV GIT_SHA $GIT_SHA
ENV BUILD_DATE $BUILD_DATE

