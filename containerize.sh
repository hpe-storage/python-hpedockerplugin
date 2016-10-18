#!/bin/sh -e

publish () {

  # Not doing a publish on pull_request
  if [ -n $PUBLISH ] && [ "${PUBLISH}" = "true" ] && [ "${DRONE_EVENT}" != "pull_request" ] ; then

    if [ -d /build_output/docker ] ; then
      mkdir -p /build_output/docker/$REPO/ > /dev/null
      OUT="$(mktemp)"
      docker save $REPO:$1 | gzip > $OUT
      chmod +r $OUT > /dev/null
      mv $OUT /build_output/docker/$REPO/$1.tar.gz > /dev/null
    fi

    docker tag $REPO:$1 $REGISTRY/$REPO:$1 > /dev/null
    docker push $REGISTRY/$REPO:$1 > /dev/null
    docker rmi $REGISTRY/$REPO:$1 > /dev/null
  fi
}

sanitize() {
    echo $1 | sed -e 's/(//g' -e 's/#/__/g' -e 's/ /--/g' | tr '[:upper:]' '[:lower:]' | xargs
}

#env | sort 1>&2
REGISTRY=$REGISTRY
if [ -z $REGISTRY ] ; then
  REGISTRY="localhost:5000"
fi

# lowercase goodness
REPO=$(echo $DRONE_REPO | tr '[:upper:]' '[:lower:]' | xargs)
if [ -z $REPO ] ; then
  REPO=$(git config --local remote.origin.url | sed -e 's/\.git$//' -e 's,//[^/]*/,,g' -e 's,.*:,,' | tr '[:upper:]' '[:lower:]')
fi
if [ -n $REPO ] ; then
  top=$(git rev-parse --show-toplevel)
  if [ "$PWD" != "$top" ] ; then
    REPO="$REPO-$(basename $PWD)"
  fi
fi
if [ -z $REPO ] ; then
  REPO="$(basename $PWD)"
fi
REPO=$(sanitize $REPO )

VERSION=$(echo $DRONE_TAG | xargs)
if [ -z $VERSION ] && [ -n $DRONE_BRANCH ] ; then
  VERSION=$(echo $DRONE_BRANCH | xargs)
fi
if [ -z $VERSION ] ; then
  VERSION=$(git branch | grep '\*' | awk '{print $2}')
fi
if [ -z $VERSION ] ; then
  VERSION="unknown"
fi
VERSION=$(sanitize $VERSION | sed -e 's/\//_/g')

TAG=$REPO:$VERSION
BUILD_DATE=$(date -u)
GIT_SHA=$(git describe --dirty --tags --long --abbrev=40 2>/dev/null || echo "not-a-repo")

if [ "$#" -gt 0 ]
then
  if [ "$1" = "-q" ] || [ "$1" = "--quiet" ]
  then
      echo $TAG
      exit 0
  fi
fi

docker build \
  --rm=true \
  --build-arg http_proxy=$http_proxy \
  --build-arg https_proxy=$https_proxy \
  --build-arg no_proxy=$no_proxy \
  --build-arg TAG="$TAG" \
  --build-arg BUILD_DATE="$BUILD_DATE" \
  --build-arg GIT_SHA=$GIT_SHA \
  --tag=$TAG .
#  --memory-swap '-1' \

publish $VERSION

if [ "${VERSION}" = "master" ] ; then
  docker tag $TAG $REPO:latest > /dev/null
  publish latest
fi
