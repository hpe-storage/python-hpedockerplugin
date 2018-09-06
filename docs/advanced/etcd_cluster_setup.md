
## Possible configuration for etcd clustering
![Approaches for etcd clustering](/docs/secure_etcd_configurations.png "etcd clustering")

Procedure for self signed certificates is given in the below links. Self signed certificates is used for setting up a secure
etcd cluster.

https://github.com/coreos/docs/blob/master/os/generate-self-signed-certificates.md  (Generating certificates)

## Steps to setup a 3 node secure etcd cluster 

Following three shell scripts (etcd1,2,3.sh will be invoked on 3 different machines, whose IP’s are given in etcd1,2,3 shell variables), and the certs folder will contain the server’s key/certificate, client’s key/certificate files in /home/docker/cfssl
 
etcd1.sh
 
 ```
etcd1=10.50.180.1
etcd2=10.50.164.1
etcd3=10.50.198.1
etcd=$etcd1
/usr/bin/etcd  --name infra0 --data-dir ./infra0 \
  --advertise-client-urls https://${etcd}:3379 \
  --listen-client-urls https://${etcd}:3379 \
  --initial-advertise-peer-urls http://${etcd}:23380 \
  --listen-peer-urls http://${etcd}:23380 \
  --initial-cluster-token etcd-cluster-1 \
  --initial-cluster infra0=http://${etcd1}:23380,infra1=http://${etcd2}:23380,infra2=http://${etcd3}:23380 \
  --cert-file=/home/docker/cfssl/server.pem \
  --key-file=/home/docker/cfssl/server-key.pem \
  --trusted-ca-file=/home/docker/cfssl/ca.pem \
  --client-cert-auth \
  --initial-cluster-state new
```



etcd2.sh
```
etcd1=10.50.180.1
etcd2=10.50.164.1
etcd3=10.50.198.1
etcd=$etcd2
/usr/bin/etcd  --name infra1 --data-dir ./infra1 \
  --advertise-client-urls https://${etcd}:3379,https://${etcd}:4001 \
  --listen-client-urls https://${etcd}:3379,https://${etcd}:4001 \
  --initial-advertise-peer-urls http://${etcd}:23380 \
  --listen-peer-urls http://${etcd}:23380 \
  --initial-cluster-token etcd-cluster-1 \
  --initial-cluster infra0=http://${etcd1}:23380,infra1=http://${etcd2}:23380,infra2=http://${etcd3}:23380 \
  --cert-file=/home/docker/cfssl/server.pem \
  --key-file=/home/docker/cfssl/server-key.pem \
  --trusted-ca-file=/home/docker/cfssl/ca.pem \
  --client-cert-auth \
  --initial-cluster-state new
```  
  


etcd3.sh
```
etcd1=10.50.180.1
etcd2=10.50.164.1
etcd3=10.50.198.1
etcd=$etcd3
/usr/bin/etcd  --name infra2 --data-dir ./infra2 \
  --advertise-client-urls https://${etcd}:3379,https://${etcd}:4001 \
  --listen-client-urls https://${etcd}:3379,https://${etcd}:4001 \
  --initial-advertise-peer-urls http://${etcd}:23380 \
  --listen-peer-urls http://${etcd}:23380 \
  --initial-cluster-token etcd-cluster-1 \
  --initial-cluster infra0=http://${etcd1}:23380,infra1=http://${etcd2}:23380,infra2=http://${etcd3}:23380 \
  --cert-file=/home/docker/cfssl/server.pem \
  --key-file=/home/docker/cfssl/server-key.pem \
  --trusted-ca-file=/home/docker/cfssl/ca.pem \
  --client-cert-auth \
  --initial-cluster-state new
``` 
 
## Sample python program using etcd client.  
``` 
import etcd 
client = etcd.Client(host=(('10.50.180.1',3379),('10.50.164.1',3379),('10.50.198.1',3379)),cert=('/home/docker/cfssl/client.pem','/home/docker/cfssl/client-key.pem'),protocol='https',port=3379,allow_reconnect=True)
client.write('/nodes/n1',1) 
print client.read('/nodes/n1')
```
 
## Sample CURL call to one of the cluster member

```
curl -k -cacert /home/docker/cfssl/ca.pem --cert /home/docker/cfssl/client.pem --key /home/docker/cfssl/client-key.pem  -L https://10.50.164.1:3379/v2/keys?recursive=true | grep secure
curl: (3) <url> malformed
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100  2130    0  2130    0     0  15521      0 --:--:-- --:--:-- --:--:-- 15434
{"action":"get","node":{"dir":true,"nodes":[{"key":"/nodes","dir":true,"nodes":[{"key":"/nodes/n1","value":"1","modifiedIndex":21,"createdIndex":21}],"modifiedIndex":17,"createdIndex":17},{"key":"/volumes","dir":true,"nodes":[{"key":"/volumes/fbcf10d3-6486-4980-85b7-6a75364b754b","value":"{\"status\": \"\", \"display_name\": \"test_vol_shared_secured_etcd\", \"name\": \"fbcf10d3-6486-4980-85b7-6a75364b754b\", \"availability_zone\": \"\", \"volume_attachment\": null, \"attach_status\": \"\", \"volume_type\": null, \"provisioning\": \"thin\", \"host\": \"\", \"provider_location\": null, \"volume_id\": \"\", \"path_info\": null, \"flash_cache\": null, \"id\": \"fbcf10d3-6486-4980-85b7-6a75364b754b\", \"size\": 12}","modifiedIndex":13,"createdIndex":13},{"key":"/volumes/5cbd251f-26f5-4565-a324-896952c46285","value":"{\"status\": \"\", \"display_name\": \"secure_multi_etcd_vol1\", \"name\": \"5cbd251f-26f5-4565-a324-896952c46285\", \"availability_zone\": \"\", \"volume_attachment\": null, \"attach_status\": \"\", \"volume_type\": null, \"provisioning\": \"thin\", \"host\": \"\", \"provider_location\": null, \"volume_id\": \"\", \"path_info\": null, \"flash_cache\": null, \"id\": \"5cbd251f-26f5-4565-a324-896952c46285\", \"size\": 1}","modifiedIndex":23,"createdIndex":23},{"key":"/volumes/297ea8bb-ef7a-4ebb-8dac-f38082101f50","value":"{\"status\": \"\", \"display_name\": \"secure_multi_etcd_vol2\", \"name\": \"297ea8bb-ef7a-4ebb-8dac-f38082101f50\", \"availability_zone\": \"\", \"volume_attachment\": null, \"attach_status\": \"\", \"volume_type\": null, \"provisioning\": \"thin\", \"host\": \"\", \"provider_location\": null, \"volume_id\": \"\", \"path_info\": null, \"flash_cache\": null, \"id\": \"297ea8bb-ef7a-4ebb-8dac-f38082101f50\", \"size\": 1}","modifiedIndex":26,"createdIndex":26}],"modifiedIndex":11,"createdIndex":11},{"key":"/volumes-lock","dir":true,"modifiedIndex":12,"createdIndex":12},{"key":"/foo","value":"bar","modifiedIndex":10,"createdIndex":10},{"key":"/foo1","value":"bar1","modifiedIndex":15,"createdIndex":15},{"key":"/foo2","value":"bar2","modifiedIndex":20,"createdIndex":20}]}}
```
