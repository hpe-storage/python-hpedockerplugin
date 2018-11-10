FROM alpine:3.8

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONPATH=${HOME}/python-hpedockerplugin:/root/python-hpedockerplugin

RUN apk add --no-cache python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

RUN apk add --no-cache --update \
    py-setuptools \
    sysfsutils \
    multipath-tools \
    device-mapper \
    util-linux \
    sg3_utils\
    eudev \
    libssl1.0 \
	sudo \
 && apk update \
 && apk upgrade \
 && apk add e2fsprogs ca-certificates \ 
 && pip install --upgrade pip \
    setuptools \
 && rm -rf /var/cache/apk/*

COPY . /python-hpedockerplugin
COPY ./iscsiadm /usr/bin/
COPY ./cleanup.sh /usr/bin


RUN apk add --virtual /tmp/.temp --no-cache --update \
    build-base \
    g++ \
    gcc \
    libffi-dev \
    linux-headers \
    make \
    libssl1.0 \
	openssh-client \
	openssl-dev \
    python3-dev \

# build and install hpedockerplugin
 && cd /python-hpedockerplugin \
 && python3 setup.py install \

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
RUN mkdir -p /opt/hpe/data
RUN chmod u+x /usr/bin/iscsiadm
RUN chmod u+x /usr/bin/cleanup.sh

# Patch the os_brick, twisted modules

COPY ./patch_os_bricks/linuxscsi.py /usr/lib/python3.6/site-packages/os_brick-1.13.1-py3.6.egg/os_brick/initiator/linuxscsi.py
COPY ./patch_os_bricks/rootwrap.py /usr/lib/python3.6/site-packages/os_brick-1.13.1-py3.6.egg/os_brick/privileged/rootwrap.py
COPY ./oslo/comm.py /usr/lib/python3.6/site-packages/oslo.privsep-1.29.0-py3.6.egg/oslo_privsep/comm.py
COPY ./patch_os_bricks/compat.py /usr/lib/python3.6/site-packages/Twisted-18.7.0rc1-py3.6-linux-x86_64.egg/twisted/python/compat.py


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

