#!/bin/sh -e

VERSION=0.8
REPO=github.com:hpe-storage/python-hpedockerplugin.git
IMAGE_NAME=hpe/hpedockerplugin
TAG=$IMAGE_NAME:$VERSION
#HPEPLUGIN_TOKEN=ff6638ed5fd9cf300da04fd9b94b61e146ac4a82
BUILD_DATE=$(date -u)

#git clone https://$HPEPLUGIN_TOKEN:x-oauth-basic@$REPO
#git clone git@$REPO

docker build \
   --rm=true \
   --build-arg http_proxy=$http_proxy \
   --build-arg https_proxy=$https_proxy \
   --build-arg no_proxy=$no_proxy \
   --build-arg build_date="$BUILD_DATE" \
   --tag="$TAG" \
   --file Dockerfile.hpeplugin .

