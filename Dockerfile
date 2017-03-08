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
# && wget https://pypi.python.org/packages/6a/cc/5878c5f2e5043a526653ca61885e65ee834847ed3933545e31a96ecaa40d/pyasn1-0.2.1.tar.gz#md5=9dfafed199b321d56bab9cd341b6dd01 \
 && wget https://pypi.python.org/packages/69/17/eec927b7604d2663fef82204578a0056e11e0fc08d485fdb3b6199d9b590/pyasn1-0.2.3.tar.gz#md5=79f98135071c8dd5c37b6c923c51be45 \
# && wget http://10.50.177.1:8088/tmp/pyasn1-0.1.9.tar.gz \
 && tar xvzf pyasn1-0.2.3.tar.gz \
 && cd pyasn1-0.2.3 \
 && python setup.py install \
 && rm -rf pyasn1-0.2.3 \

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

