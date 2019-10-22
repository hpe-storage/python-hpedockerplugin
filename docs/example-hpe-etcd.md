## Example YAML for HPE-ETCD
After generating the file, place it in the /etc/kubernetes/manifests directory to automaticly start the pod and have it persist. This
example only covers a single instance; however, for HA you will want to replicate it to two additional nodes (3 nodes in total).

## HPE Etcd Setup
1. export HostIP="<Master node IP>"
2. Create the hpe-etcd.yaml file below; note that this file shares the TLS settings of your Kubernetes etcd cluster. In production
   you should create your own TLS keys and certificates for this separate etcd key value database.
```
cat <<EOF > hpe-etcd.yaml
apiVersion: v1
kind: Pod
metadata:
  labels:
    component: hpe-etcd
    tier: control-plane
  name: hpe-etcd
  namespace: kube-system
spec:
  containers:
  - command:
    - etcd
    - --advertise-client-urls=https://${HostIP}:23790,http://${HostIP}:4001
    - --trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt
    - --cert-file=/etc/kubernetes/pki/etcd/server.crt
    - --key-file=/etc/kubernetes/pki/etcd/server.key
    - --client-cert-auth=true
    - --data-dir=/var/lib/hpe-etcd
    - --initial-advertise-peer-urls=https://${HostIP}:23800
    - --initial-cluster-token=etcd-cluster-1
    - --initial-cluster-state=new
    - --initial-cluster=m2-dl360g9-75=https://${HostIP}:23800
    - --listen-client-urls=https://127.0.0.1:23790,https://127.0.0.1:4001
    - --listen-peer-urls=https://${HostIP}:23800
    - --peer-cert-file=/etc/kubernetes/pki/etcd/peer.crt
    - --peer-client-cert-auth=true
    - --peer-key-file=/etc/kubernetes/pki/etcd/peer.key
    - --peer-trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt
    - --snapshot-count=10000
    image: k8s.gcr.io/etcd:3.3.15-0
    imagePullPolicy: IfNotPresent
    livenessProbe:
      failureThreshold: 8
      httpGet:
        host: 127.0.0.1
        path: /health
        port: 2381
        scheme: HTTP
      initialDelaySeconds: 15
      timeoutSeconds: 15
    name: hpe-etcd
    resources: {}
    volumeMounts:
    - mountPath: /var/lib/hpe-etcd
      name: hpe-etcd-data
    - mountPath: /etc/kubernetes/pki/etcd
      name: etcd-certs
  hostNetwork: true
  priorityClassName: system-cluster-critical
  volumes:
  - hostPath:
      path: /etc/kubernetes/pki/etcd
      type: DirectoryOrCreate
    name: etcd-certs
  - hostPath:
      path: /var/lib/hpe-etcd
      type: DirectoryOrCreate
    name: hpe-etcd-data
status: {}
EOF
```
