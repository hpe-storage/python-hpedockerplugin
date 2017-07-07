#!/bin/bash
# (c) Copyright [2017] Nimble Storage, A Hewlett Packard Enterprise Company
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

# this is an early hack... it works, but you need docker 13 or >
if [ -z "$1" ]; then
    echo "Plugin name must be supplied as ARG1"
    exit 1
fi
pluginName=$1

#
# Clean up existsing plugins
#
docker plugin disable ${pluginName} -f > /dev/null 2>&1
docker plugin rm ${pluginName} -f > /dev/null 2>&1

for x in `ls /var/lib/docker/plugins`
do
   if [ ${x} = "storage" ] || [ ${x} = "tmp" ]; then
     echo skipping ${x}
   else
     umount /var/lib/docker/plugins/${x}/rootfs/etc/hpedockerplugin/data
     rm -rf /var/lib/docker/plugins/${x}
   fi
done

rm -rf v2plugin
mkdir v2plugin > /dev/null 2>&1

rm -rf v2plugin/rootfs
#docker build -t rootfsimage .a
./containerize.sh
docker tag wdurairaj/python-hpedockerplugin:plugin_v2 $1
rc=$?
 if [[ $rc -ne 0 ]]; then
  echo "ERROR: failed"
  exit $rc
fi

id=$(docker create $1 true)
rc=$?
 if [[ $rc -ne 0 ]]; then
  echo "ERROR: failed"
  exit $rc
fi

mkdir -p v2plugin/rootfs
rc=$?
 if [[ $rc -ne 0 ]]; then
  echo "ERROR: failed"
  exit $rc
fi

docker export "$id" | sudo tar -x -C v2plugin/rootfs
rc=$?
 if [[ $rc -ne 0 ]]; then
  echo "ERROR: failed"
  exit $rc
fi

#docker rm -vf "$id"
rc=$?
 if [[ $rc -ne 0 ]]; then
  echo "ERROR: failed"
  exit $rc
fi

#docker rmi wdurairaj/python-hpedockerplugin:plugin_v2
rc=$?
 if [[ $rc -ne 0 ]]; then
  echo "ERROR: failed"
  exit $rc
fi

cp config.json v2plugin
rc=$?
 if [[ $rc -ne 0 ]]; then
  echo "ERROR: failed"
  exit $rc
fi
docker plugin create ${pluginName} v2plugin
