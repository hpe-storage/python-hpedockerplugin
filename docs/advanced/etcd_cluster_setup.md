
## Possible configuration for etcd clustering

For etcd cluster creation please refer https://github.com/etcd-io/etcd/tree/master/contrib/systemd/etcd3-multinode
 
 
```
## Steps to create a 3 node etcd cluster:
```
```
Node1:
1. sudo mkdir -p /root/hpe-etcd
   #Note: /root/hpe-etcd is the data-dir
2. sudo chown -R root:$(whoami) /root/hpe-etcd
3. sudo chmod -R a+rw /root/hpe-etcd
4. vi /etc/systemd/system/hpe-etcd-1.service

[Unit]
Description=etcd
Documentation=https://github.com/coreos/etcd

[Service]
Type=notify
Restart=always
RestartSec=5s
LimitNOFILE=40000
TimeoutStartSec=0
ExecStart=/usr/bin/etcd --name 10.50.9.10 --data-dir /root/hpe-etcd --listen-client-urls http://10.50.9.10:23790 --advertise-client-urls http://10.50.9.10:23790 --listen-peer-urls http://10.50.9.10:23800 --initial-advertise-peer-urls http://10.50.9.10:23800 --initial-cluster 10.50.9.10=http://10.50.9.10:23800,10.50.9.22=http://10.50.9.22:23800,10.50.9.23=http://10.50.9.23:23800 --initial-cluster-token my-etcd-token --initial-cluster-state new

[Install]
WantedBy=multi-user.target

5. sudo systemctl daemon-reload
6. sudo systemctl enable hpe-etcd-1.service
7. sudo systemctl start hpe-etcd-1.service

Node2:
1. sudo mkdir -p /root/hpe-etcd
2. sudo chown -R root:$(whoami) /root/hpe-etcd
3. sudo chmod -R a+rw /root/hpe-etcd
4. vi /etc/systemd/system/hpe-etcd-2.service

[Unit]
Description=etcd
Documentation=https://github.com/coreos/etcd

[Service]
Type=notify
Restart=always
RestartSec=5s
LimitNOFILE=40000
TimeoutStartSec=0
ExecStart=/usr/bin/etcd --name 10.50.9.22 \
    --data-dir /root/hpe-etcd \
    --listen-client-urls http://10.50.9.22:23790 \
    --advertise-client-urls http://10.50.9.22:23790 \
    --listen-peer-urls http://10.50.9.22:23800 \
    --initial-advertise-peer-urls http://10.50.9.22:23800 \
    --initial-cluster 10.50.9.10=http://10.50.9.10:23800,10.50.9.22=http://10.50.9.22:23800,10.50.9.23=http://10.50.9.23:23800 \
    --initial-cluster-token my-etcd-token \
    --initial-cluster-state new

[Install]
WantedBy=multi-user.target

5. sudo systemctl daemon-reload
6. sudo systemctl enable hpe-etcd-2.service
7. sudo systemctl start hpe-etcd-2.service

Node3:
1. sudo mkdir -p /root/hpe-etcd
2. sudo chown -R root:$(whoami) /root/hpe-etcd
3. sudo chmod -R a+rw /root/hpe-etcd
4. vi /etc/systemd/system/hpe-etcd-3.service

[Unit]
Description=etcd
Documentation=https://github.com/coreos/etcd

[Service]
Type=notify
Restart=always
RestartSec=5s
LimitNOFILE=40000
TimeoutStartSec=0
ExecStart=/usr/bin/etcd --name 10.50.9.23 \
    --data-dir /root/hpe-etcd \
    --listen-client-urls http://10.50.9.23:23790 \
    --advertise-client-urls http://10.50.9.23:23790 \
    --listen-peer-urls http://10.50.9.23:23800 \
    --initial-advertise-peer-urls http://10.50.9.23:23800 \
    --initial-cluster 10.50.9.10=http://10.50.9.10:23800,10.50.9.22=http://10.50.9.22:23800,10.50.9.23=http://10.50.9.23:23800 \
    --initial-cluster-token my-etcd-token \
    --initial-cluster-state new

[Install]
WantedBy=multi-user.target

5. sudo systemctl daemon-reload
6. sudo systemctl enable hpe-etcd-2.service
7. sudo systemctl start hpe-etcd-2.service
```




## List members of etcd cluster

```
etcdctl --endpoint http://10.50.9.23:23790 member list

92bf602c3e52c786: name=10.50.9.22 peerURLs=http://10.50.9.22:23800 clientURLs=http://10.50.9.22:23790 isLeader=true

df87d2bb2823677b: name=10.50.9.23 peerURLs=http://10.50.9.23:23800 clientURLs=http://10.50.9.23:23790 isLeader=false

eba454355c8689a7: name=10.50.9.10 peerURLs=http://10.50.9.10:23800 clientURLs=http://10.50.9.10:23790 isLeader=false
```


## Command to check the health of etcd cluster:

```
etcdctl --endpoint http://10.50.9.23:23790 cluster-health
member 69973f2749d2cb96 is healthy: got healthy result from http://10.50.9.23:23790
member 92bf602c3e52c786 is healthy: got healthy result from http://10.50.9.22:23790
member eba454355c8689a7 is healthy: got healthy result from http://10.50.9.10:23790
cluster is healthy
```


## Sample python program using etcd client.

```
import etcd
client = etcd.Client(host=(('10.50.9.22',23790),('10.50.9.23',23790),('10.50.9.10',23790)),protocol='http',port=23790,allow_reconnect=True)
client.write('/nodes/n1',1)
print client.read('/nodes/n1')  
```


## Sample CURL call to one of the cluster member
```
curl http://10.50.9.23:23790/v2/members
{"members":[{"id":"69973f2749d2cb96","name":"etcd3","peerURLs":["http://10.50.9.23:23800"],"clientURLs":["http://10.50.9.23:23790"]},{"id":"92bf602c3e52c786","name":"10.50.9.22","peerURLs":["http://10.50.9.22:23800"],"clientURLs":["http://10.50.9.22:23790"]},{"id":"eba454355c8689a7","name":"10.50.9.10","peerURLs":["http://10.50.9.10:23800"],"clientURLs":["http://10.50.9.10:23790"]}]}

```




