# K3s Cluster Setup Guide

> Complete guide for setting up K3s with Cilium, MetalLB, Traefik, cert-manager, and Vault PKI on Arch Linux

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [K3s Cluster Installation](#2-k3s-cluster-installation)
3. [Install CNI (Cilium)](#3-install-cni-cilium)
4. [Install MetalLB](#4-install-metallb)
5. [Install Traefik](#5-install-traefik)
6. [Install cert-manager](#6-install-cert-manager)
7. [Vault PKI Setup (Static Token)](#7-vault-pki-setup-static-token)
8. [Kubernetes Auth with Vault (Advanced)](#8-kubernetes-auth-with-vault-advanced)
9. [Deploy Test Application](#9-deploy-test-application)
10. [Trust Root CA](#10-trust-root-ca)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

### Assumptions

- **Vault is running** in Docker on your host machine (e.g., `192.168.31.247:8200`)
- VMs have network access to the host (Vault accessible via bridge network)
- DNS is configured (dnsmasq or similar) to resolve `*.poddle.uz`

### Host Machine (Arch Linux)

Install required tools:

```bash
sudo pacman -S kubectl helm cilium-cli
```

### VM Requirements

| Role | Hostname | IP Address | OS |
|------|----------|------------|-----|
| Server | k3s-server | 192.168.31.106 | Ubuntu 22.04 |
| Agent | k3s-agent | 192.168.31.26 | Ubuntu 22.04 |

> Each machine must have a unique hostname.

---

## 2. K3s Cluster Installation

### 2.1 Install K3s Server

SSH into the server node (`192.168.31.106`):

```bash
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

**Why these flags?**

| Flag | Reason |
|------|--------|
| `--flannel-backend=none` | Cilium will provide CNI |
| `--disable-kube-proxy` | Cilium replaces kube-proxy with eBPF |
| `--disable traefik` | We install Traefik via Helm |
| `--disable servicelb` | We use MetalLB instead |

Verify installation:

```bash
sudo systemctl status k3s
```

Get the node token for agents:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

### 2.2 Install K3s Agent

SSH into the agent node (`192.168.31.26`):

```bash
export NODE_TOKEN="<token-from-server>"
export MASTER_IP="192.168.31.106"

curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" \
  K3S_TOKEN="${NODE_TOKEN}" sh -
```

### 2.3 Setup Kubeconfig on Host

On your Arch Linux host:

```bash
mkdir -p ~/.kube
scp kamronbek@192.168.31.106:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Update API server address
sed -i 's/127.0.0.1/192.168.31.106/g' ~/.kube/config

chmod 600 ~/.kube/config
```

Verify connection:

```bash
kubectl get nodes
# Output: k3s-server   NotReady   control-plane,master
# NotReady is expected - no CNI yet!
```

---

## 3. Install CNI (Cilium)

```bash
helm repo add cilium https://helm.cilium.io/
helm repo update

helm install cilium cilium/cilium \
  --namespace kube-system \
  --set k8sServiceHost=192.168.31.106 \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true
```

Wait for Cilium to be ready:

```bash
kubectl -n kube-system rollout status deployment/cilium-operator
cilium status --wait
```

Verify nodes are now Ready:

```bash
kubectl get nodes
# All nodes should show Ready status
```

---

## 4. Install MetalLB

```bash
helm repo add metallb https://metallb.github.io/metallb
helm repo update

helm install metallb metallb/metallb \
  --namespace metallb-system \
  --create-namespace
```

Wait for MetalLB pods:

```bash
kubectl -n metallb-system rollout status deployment/metallb-controller
```

Apply IP pool configuration:

```bash
kubectl apply -f charts/metallb-manifests/config.yaml
```

<details>
<summary>charts/metallb-manifests/config.yaml</summary>

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: metallb-system
---
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: ip-address-pool
  namespace: metallb-system
spec:
  addresses:
    - 192.168.31.10-192.168.31.19
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: l2-advertisement
  namespace: metallb-system
spec:
  ipAddressPools:
    - ip-address-pool
```

</details>

---

## 5. Install Traefik

```bash
helm repo add traefik https://traefik.github.io/charts
helm repo update

helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace
```

Verify Traefik got an external IP:

```bash
kubectl get svc -n traefik
# Should show EXTERNAL-IP: 192.168.31.10
```

---

## 6. Install cert-manager

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.19.1 \
  --set crds.enabled=true
```

Verify:

```bash
kubectl get pods -n cert-manager
# All pods should be Running
```

---

## 7. Vault PKI Setup (Static Token)

> This approach uses a manually created Vault token stored in Kubernetes Secret.

### 7.1 Configure Vault PKI

On your host (with Vault access):

```bash
export VAULT_ADDR='http://vault.poddle.uz:8200'
export VAULT_TOKEN='<your-root-token>'

# Enable PKI secrets engine
vault secrets enable pki

# Set max TTL to 10 years
vault secrets tune -max-lease-ttl=87600h pki

# Generate Root CA
vault write -field=certificate pki/root/generate/internal \
    common_name="Poddle Root CA" \
    issuer_name="root-2025" \
    ttl=87600h > ~/poddle-root-ca.crt

# Configure CA URLs
vault write pki/config/urls \
    issuing_certificates="http://vault.poddle.uz:8200/v1/pki/ca" \
    crl_distribution_points="http://vault.poddle.uz:8200/v1/pki/crl"

# Create role for issuing certificates
vault write pki/roles/poddle-uz \
    allowed_domains="poddle.uz" \
    allow_subdomains=true \
    allow_bare_domains=true \
    allow_localhost=false \
    max_ttl="8760h" \
    ttl="720h" \
    key_bits=2048 \
    key_type=rsa
```

### 7.2 Create Policy for cert-manager

```bash
cat > /tmp/cert-manager-policy.hcl <<EOF
path "pki/sign/poddle-uz" {
  capabilities = ["create", "update"]
}

path "pki/issue/poddle-uz" {
  capabilities = ["create", "update"]
}

path "pki/cert/ca" {
  capabilities = ["read"]
}
EOF

vault policy write cert-manager /tmp/cert-manager-policy.hcl
```

### 7.3 Create Token for cert-manager

```bash
vault token create \
    -policy=cert-manager \
    -period=24h \
    -display-name=cert-manager \
    -no-default-policy \
    -format=json | tee ~/cert-manager-token.json

# Extract the token
CERT_MANAGER_TOKEN=$(jq -r '.auth.client_token' ~/cert-manager-token.json)
echo $CERT_MANAGER_TOKEN
```

### 7.4 Store Token in Kubernetes

```bash
kubectl create secret generic vault-token \
    --from-literal=token="${CERT_MANAGER_TOKEN}" \
    -n cert-manager
```

### 7.5 Create ClusterIssuer

```bash
kubectl apply -f manifests/cluster-issuers/vault-ci.yaml
```

<details>
<summary>manifests/cluster-issuers/vault-ci.yaml (token-based)</summary>

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: vault-token-ci
spec:
  vault:
    server: http://192.168.31.247:8200
    path: pki/sign/poddle-uz
    auth:
      tokenSecretRef:
        name: vault-token
        key: token
```

</details>

Verify the issuer:

```bash
kubectl get clusterissuer
kubectl describe clusterissuer vault-token-ci
# Status should show: "Vault verified"
```

---

## 8. Kubernetes Auth with Vault (Advanced)

> More secure than static tokens. Vault verifies Kubernetes Service Account JWTs.

### 8.1 Enable Kubernetes Auth in Vault

```bash
vault auth enable kubernetes
```

### 8.2 Create Token Reviewer ServiceAccount

Vault needs a ServiceAccount with `system:auth-delegator` permission to verify JWT tokens via the TokenReview API.

```bash
# Create a ServiceAccount for Vault token review
kubectl create serviceaccount vault-reviewer -n kube-system

# Bind it to the system:auth-delegator ClusterRole
kubectl create clusterrolebinding vault-reviewer-binding \
    --clusterrole=system:auth-delegator \
    --serviceaccount=kube-system:vault-reviewer
```

### 8.3 Configure Kubernetes Auth

Get the required values from your cluster:

```bash
# Get Kubernetes CA certificate
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)

# Get the Kubernetes API server address
K8S_HOST="https://192.168.31.106:6443"

# Get token from vault-reviewer SA (has TokenReview permissions)
REVIEWER_TOKEN=$(kubectl create token vault-reviewer -n kube-system --duration=87600h)

# Configure Kubernetes auth
vault write auth/kubernetes/config \
    kubernetes_host="$K8S_HOST" \
    kubernetes_ca_cert="$K8S_CA_CERT" \
    token_reviewer_jwt="$REVIEWER_TOKEN"
```

> **IMPORTANT**: The `token_reviewer_jwt` must be from a ServiceAccount with `system:auth-delegator` role.  
> Using the `cert-manager` SA will cause "permission denied" errors because it can't call the TokenReview API.

### 8.4 Create Vault Role for cert-manager

```bash
vault write auth/kubernetes/role/cert-manager \
    bound_service_account_names=cert-manager \
    bound_service_account_namespaces=cert-manager \
    policies=cert-manager \
    ttl=24h
```

### 8.5 Create ClusterIssuer with Kubernetes Auth

```bash
kubectl apply -f manifests/cluster-issuers/vault-ci.yaml
```

<details>
<summary>manifests/cluster-issuers/vault-ci.yaml (k8s-auth)</summary>

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: vault-k8s-ci
spec:
  vault:
    server: http://192.168.31.247:8200
    path: pki/sign/poddle-uz
    auth:
      kubernetes:
        role: cert-manager
        mountPath: /v1/auth/kubernetes
        serviceAccountRef:
          name: cert-manager
```

</details>

---

## 9. Deploy Test Application

### 9.1 Deploy Nginx

```bash
kubectl apply -f example/nginx-deployment.yaml
kubectl apply -f example/nginx-service.yaml
kubectl apply -f example/nginx-ingress.yaml
```

<details>
<summary>example/nginx-deployment.yaml</summary>

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
        - name: nginx
          image: nginx:latest
          ports:
            - containerPort: 80
          resources:
            requests:
              cpu: "100m"
              memory: "100Mi"
            limits:
              cpu: "200m"
              memory: "200Mi"
```

</details>

<details>
<summary>example/nginx-service.yaml</summary>

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
spec:
  type: ClusterIP
  selector:
    app: nginx
  ports:
    - port: 80
      targetPort: 80
```

</details>

<details>
<summary>example/nginx-ingress.yaml</summary>

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
  annotations:
    cert-manager.io/cluster-issuer: vault-token-ci
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - nginx.poddle.uz
      secretName: nginx-tls-secret
  rules:
    - host: nginx.poddle.uz
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: nginx
                port:
                  number: 80
```

</details>

### 9.2 Verify Certificate

```bash
# Watch certificate creation
kubectl get certificate -w

# Check certificate details
kubectl describe certificate nginx-tls-secret

# Test HTTPS
curl -k https://nginx.poddle.uz
```

---

## 10. Trust Root CA

### 10.1 Arch Linux System-Wide

```bash
sudo cp ~/poddle-root-ca.crt /etc/ca-certificates/trust-source/anchors/
sudo update-ca-trust

# Verify
trust list | grep -A4 "Poddle Root CA"
```

### 10.2 Firefox

```bash
# Find Firefox profile
FIREFOX_PROFILE=$(ls -d ~/.mozilla/firefox/*.default-release 2>/dev/null | head -1)

# Import CA certificate
certutil -A -n "Poddle Root CA" -t "C,C,C" -i ~/poddle-root-ca.crt -d "sql:$FIREFOX_PROFILE"

# Verify
certutil -L -d "sql:$FIREFOX_PROFILE" | grep "Poddle Root CA"

# Restart Firefox
pkill -9 firefox
```

Now visit `https://nginx.poddle.uz` - you should see a green lock.

---

## 11. Troubleshooting

### Certificate Not Ready

```bash
kubectl describe certificate <cert-name>
kubectl logs -n cert-manager -l app=cert-manager -f
kubectl get certificaterequest
```

### DNS Resolution Issues

The error `lookup vault.poddle.uz: no such host` from inside the cluster means CoreDNS can't resolve external domains.

**Solution:** Configure CoreDNS to use your host's dnsmasq or add a static entry:

```bash
kubectl -n kube-system edit configmap coredns
```

Add forward to your host DNS:

```
forward . 192.168.31.247 /etc/resolv.conf
```

Or use IP directly in ClusterIssuer:

```yaml
server: http://192.168.31.247:8200  # Use IP instead of hostname
```

### Vault Connection Issues

```bash
# Test from host
curl http://vault.poddle.uz:8200/v1/sys/health

# Test from K3s node
ssh kamronbek@192.168.31.106
curl http://192.168.31.247:8200/v1/sys/health
```

---

## File Structure

```
k3s/
├── charts/
│   ├── cilium-manifests/
│   │   └── values.yaml
│   ├── metallb-manifests/
│   │   ├── config.yaml
│   │   └── values.yaml
│   ├── prometheus-manifests/
│   │   └── values.yaml
│   └── traefik-manifests/
│       ├── traefik-config.yaml
│       ├── traefik-dashboard.yaml
│       └── values.yaml
├── example/
│   ├── nginx-deployment.yaml
│   ├── nginx-ingress.yaml
│   └── nginx-service.yaml
├── manifests/
│   ├── certificates/
│   │   └── wildcard-certificate.yaml
│   └── cluster-issuers/
│       └── vault-ci.yaml
└── README.md
```

---

## Quick Reference

| Component | Command |
|-----------|---------|
| Check nodes | `kubectl get nodes` |
| Check pods | `kubectl get pods -A` |
| Check certificates | `kubectl get certificate -A` |
| Check issuers | `kubectl get clusterissuer` |
| Vault status | `vault status` |
| Renew token | `vault token renew` |
