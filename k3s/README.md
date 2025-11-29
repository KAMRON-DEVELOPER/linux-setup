# Setup K3S with Cilium, MetalLB, Traefik and Prometheus(kube-prometheus-stack) via Helm

note
Each machine must have a unique hostname. If your machines do not have unique hostnames, pass the K3S_NODE_NAME environment variable and provide a value with a valid and unique hostname for each node.

## server

```
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --write-kubeconfig-mode=644 --disable traefik --disable servicelb --flannel-backend none --disable-network-policy --disable-kube-proxy --cluster-cidr=10.42.0.0/16 --service-cidr=10.43.0.0/16 --bind-address=192.168.31.106 --advertise-address=192.168.31.106 --node-ip=192.168.31.106 --tls-san=192.168.31.106" sh -s -
# or
curl -sfL https://get.k3s.io | sh -s - server \
  --write-kubeconfig-mode=644 \
  --disable traefik \
  --disable servicelb \
  --flannel-backend=none \
  --disable-network-policy \
  --disable-kube-proxy \
  --cluster-cidr=10.42.0.0/16 \
  --service-cidr=10.43.0.0/16 \
  --bind-address=192.168.31.106 \
  --advertise-address=192.168.31.106 \
  --node-ip=192.168.31.106 \
  --tls-san=192.168.31.106
```

### Verify installation

sudo systemctl status k3s

### Why these flags?

--flannel-backend=none - Don't install Flannel
--disable-kube-proxy - Cilium will replace kube-proxy (eBPF magic!)
--disable traefik - We'll install it via Helm
--disable servicelb - We'll use MetalLB instead

## agent

### The value to use for K3S_TOKEN is stored at /var/lib/rancher/k3s/server/node-token on your server node

### `sudo cat /var/lib/rancher/k3s/server/node-token`

### output something like this

`sudo cat /etc/rancher/k3s/k3s.yaml | grep server`

### this command show "" or "" depending on whather you use `--tls-san` while k3s installation. if you used you don't need to run this `sed -i 's/127.0.0.1/192.168.31.116/g' ~/.kube/config` comamnd to change kube config api location when you copy config `scp user@192.168.31.116:/etc/rancher/k3s/k3s.yaml ~/.kube/config`

`K109d59e6883b4a60f9da90a2b5f6648bf6e82c23f6066bcbfd7de0187b36af727b::server:fbab02990a3bf9f31f546da93f862291`

### ssh into agent node and run these commands

`export NODE_TOKEN=...`
`export MASTER_IP=192.168.31.106`
`curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" K3S_TOKEN=${NODE_TOKEN} sh -`

```

```

curl -sfL <https://get.k3s.io> | INSTALL_K3S_EXEC="agent --server https://{k3s.example.com|192.168.31.106} --token mypassword" sh -s -

# or

curl -sfL <https://get.k3s.io> | K3S_URL=https://{k3s.example.com|192.168.31.106}:6443 K3S_TOKEN=mynodetoken sh -

```

By default, configuration is loaded from /etc/rancher/k3s/config.yaml


Step 3: Setup Kubeconfig on Host
# Copy kubeconfig from server
mkdir -p ~/.kube
scp kamronbek@192.168.31.106:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Update server IP
sed -i 's/127.0.0.1/192.168.31.106/g' ~/.kube/config

# Set permissions
chmod 600 ~/.kube/config

# Test connection
kubectl get nodes
# Should show: k3s-server   NotReady   control-plane,master
# NotReady is expected - no CNI yet!


Step 4: Install Cilium CLI
# Download and install Cilium CLI
on arch `sudo pcaman -S cilium-cli`

# Verify
cilium version --client


Step 5: Install Cilium CNI
```

###################################################################################

## helm install [RELEASE NAME] chart

### cilium

`helm install cilium cilium/cilium \
  --namespace kube-system \
  --set k8sServiceHost=192.168.31.106 \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true`

### metallb

```helm install metallb metallb/metallb --namespace metallb-system --create-namespace -f metallb-manifests/values.yaml
# note, you can apply <b>metallb-manifests/config.yaml</b> using `kubectl apply -f metallb-manifests/config.yaml` but with that it lives inside kubernetes not helm(not recommended)```

### traefik

`helm install traefik traefik/traefik --namespace traefik --create-namespace`

### kube-prometheus-stack

`helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=10Gi \
  --set grafana.adminPassword=admin`
