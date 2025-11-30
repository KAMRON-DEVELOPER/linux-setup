# Poddle PaaS - Complete Setup Guide for Arch Linux

> **Complete local development infrastructure with automated HTTPS using Vault PKI**

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Host Setup](#host-setup)
4. [K3s Cluster Setup](#k3s-cluster-setup)
5. [Vault PKI Setup](#vault-pki-setup)
6. [Deploy Services](#deploy-services)
7. [Troubleshooting](#troubleshooting)
8. [Reference](#reference)

---

## Overview

### Architecture

```bash
┌─────────────────────────────────────────────────────────────┐
│  Host (Arch Linux) - 192.168.31.247                         │
│  ├─ dnsmasq (DNS server)                                    │
│  ├─ Docker Compose                                          │
│  │  └─ Vault (PKI/CA) - vault.poddle.uz:8200              │
│  └─ Bridge: br0                                             │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ VMs use host DNS
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  K3s Cluster (Ubuntu VMs)                                   │
│  ├─ k3s-server (192.168.31.106) - Control Plane            │
│  ├─ k3s-agent (192.168.31.26) - Worker                     │
│  │                                                           │
│  ├─ MetalLB - 192.168.31.10-192.168.31.20                  │
│  ├─ Traefik - Ingress Controller + TLS Termination         │
│  ├─ cert-manager - Automatic certificate management         │
│  ├─ Cilium - CNI (replaces kube-proxy)                     │
│  └─ Prometheus + Grafana - Monitoring                      │
└─────────────────────────────────────────────────────────────┘
```

### What We Achieved

✅ **Automated HTTPS**: Deploy any service → get HTTPS automatically  
✅ **Custom CA**: Vault acts as Certificate Authority for `*.poddle.uz`  
✅ **Trusted Certificates**: Green lock in browser (after installing root CA)  
✅ **Zero Manual Cert Management**: cert-manager handles everything  
✅ **Production-Ready**: Same setup works with Let's Encrypt for public domains

---

## Prerequisites

### Host Machine (Arch Linux)

- Arch Linux with systemd-networkd
- Docker & Docker Compose
- Vault CLI
- Bridge network configured
- dnsmasq for DNS

### VM Requirements

- 2+ Ubuntu 22.04 VMs (k3s-server + k3s-agent)
- Bridge networking to host
- SSH access

---

## Host Setup

### 1. Install Required Packages

```bash
# Install base packages
sudo pacman -S docker docker-compose vault dnsmasq bridge-utils

# Install Kubernetes tools
sudo pacman -S kubectl helm cilium-cli

# Enable Docker
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

### 2. Configure Bridge Network

```bash
# Create bridge interface
sudo tee /etc/systemd/network/10-br0.netdev <<EOF
[NetDev]
Name=br0
Kind=bridge
EOF

# Configure bridge networking
sudo tee /etc/systemd/network/10-br0.network <<EOF
[Match]
Name=br0

[Network]
DHCP=yes
EOF

# Bind physical interface to bridge
sudo tee /etc/systemd/network/20-enp2s0.network <<EOF
[Match]
Name=enp2s0  # Change to your interface name

[Network]
Bridge=br0
EOF

# Restart networking
sudo systemctl restart systemd-networkd
```

### 3. Configure dnsmasq

```bash
# Create Poddle DNS config
sudo tee /etc/dnsmasq.d/poddle.conf <<EOF
# Wildcard: all *.poddle.uz → MetalLB IP
address=/.poddle.uz/192.168.31.10

# Specific: vault.poddle.uz → Host Docker IP
address=/vault.poddle.uz/192.168.31.247
EOF

# Restart dnsmasq
sudo systemctl enable --now dnsmasq
sudo systemctl restart dnsmasq

# Test DNS
nslookup vault.poddle.uz  # Should return 192.168.31.247
nslookup nginx.poddle.uz  # Should return 192.168.31.10
```

### 4. Deploy Vault with Docker Compose

Create `~/Documents/Docker/docker-compose.local.yml`:

```yaml
services:
  vault:
    image: hashicorp/vault:latest
    container_name: vault_container
    command: "vault server -config=/vault/config/config.json"
    environment:
      VAULT_ADDR: "http://127.0.0.1:8200"
    ports:
      - "127.0.0.1:8200:8200"       # For host CLI
      - "192.168.31.247:8200:8200"  # For VM access
    cap_add:
      - IPC_LOCK
    networks:
      - local_network_bridge
    volumes:
      - ./volumes/vault_storage:/vault/file
      - ./configurations/vault/config/config.json:/vault/config/config.json
    restart: unless-stopped

networks:
  local_network_bridge:
    driver: bridge

volumes:
  vault_storage:
```

Create Vault config `~/Documents/Docker/configurations/vault/config/config.json`:

```json
{
  "ui": true,
  "storage": {
    "file": {
      "path": "/vault/file"
    }
  },
  "listener": {
    "tcp": {
      "address": "0.0.0.0:8200",
      "tls_disable": true
    }
  },
  "api_addr": "http://vault.poddle.uz:8200"
}
```

Start Vault:

```bash
cd ~/Documents/Docker
docker-compose -f docker-compose.local.yml up -d vault
```

### 5. Initialize Vault

```bash
export VAULT_ADDR='http://vault.poddle.uz:8200'

# Initialize Vault (FIRST TIME ONLY)
vault operator init

# Save the output! You'll get:
# - 5 Unseal Keys
# - 1 Root Token

# Save to file
cat > ~/vault-keys.txt <<EOF
Unseal Key 1: <key1>
Unseal Key 2: <key2>
Unseal Key 3: <key3>
Unseal Key 4: <key4>
Unseal Key 5: <key5>

Initial Root Token: <token>
EOF

chmod 600 ~/vault-keys.txt

# Unseal Vault (need 3 of 5 keys)
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Login
export VAULT_TOKEN='<root-token>'
vault status  # Should show Sealed: false
```

---

## K3s Cluster Setup

### 1. Install K3s Server

On `k3s-server` VM (192.168.31.106):

```bash
# Install K3s with specific configuration
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

# Verify
sudo systemctl status k3s

# Get node token for agents
sudo cat /var/lib/rancher/k3s/server/node-token
```

### 2. Install K3s Agent

On `k3s-agent` VM (192.168.31.26):

```bash
export NODE_TOKEN="<token-from-server>"
export MASTER_IP="192.168.31.106"

curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" \
  K3S_TOKEN="${NODE_TOKEN}" sh -
```

### 3. Setup Kubeconfig on Host

On Arch host:

```bash
# Copy kubeconfig from server
mkdir -p ~/.kube
scp kamronbek@192.168.31.106:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Update server IP
sed -i 's/127.0.0.1/192.168.31.106/g' ~/.kube/config

# Set permissions
chmod 600 ~/.kube/config

# Test
kubectl get nodes
# Should show: NotReady (no CNI yet)
```

### 4. Install Cilium (CNI)

```bash
# Add Helm repos
helm repo add cilium https://helm.cilium.io/
helm repo update

# Install Cilium
helm install cilium cilium/cilium \
  --namespace kube-system \
  --set k8sServiceHost=192.168.31.106 \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true

# Wait for Cilium to be ready
kubectl -n kube-system rollout status deployment/cilium-operator

# Verify nodes are now Ready
kubectl get nodes
```

### 5. Install MetalLB (Load Balancer)

```bash
# Add Helm repo
helm repo add metallb https://metallb.github.io/metallb
helm repo update

# Install MetalLB
helm install metallb metallb/metallb \
  --namespace metallb-system \
  --create-namespace

# Configure IP pool
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
    - 192.168.31.10-192.168.31.20
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-l2
  namespace: metallb-system
spec:
  ipAddressPools:
    - default-pool
EOF
```

### 6. Install Traefik (Ingress Controller)

```bash
# Add Helm repo
helm repo add traefik https://traefik.github.io/charts
helm repo update

# Install Traefik
helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace

# Verify Traefik got an external IP
kubectl get svc -n traefik
# Should show EXTERNAL-IP: 192.168.31.10
```

### 7. Install cert-manager

```bash
# Add Helm repo
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Install cert-manager
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.19.1 \
  --set crds.enabled=true

# Verify
kubectl get pods -n cert-manager
```

---

## Vault PKI Setup

### 1. Configure Vault as Certificate Authority

```bash
export VAULT_ADDR='http://vault.poddle.uz:8200'
export VAULT_TOKEN='<your-root-token>'

# Enable PKI secrets engine
vault secrets enable pki

# Tune TTL to 10 years
vault secrets tune -max-lease-ttl=87600h pki

# Generate Root CA (IMPORTANT: Save this certificate!)
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
    key_type=rsa \
    require_cn=false \
    use_csr_common_name=true
```

### 2. Create Policy for cert-manager

```bash
# Create policy
vault policy write cert-manager - <<EOF
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

# Create token for cert-manager
vault token create \
    -policy=cert-manager \
    -period=24h \
    -display-name=cert-manager \
    -no-default-policy \
    -format=json | tee ~/cert-manager-token.json

# Extract token
CERT_MANAGER_TOKEN=$(jq -r '.auth.client_token' ~/cert-manager-token.json)
```

### 3. Store Token in Kubernetes

```bash
# Create secret in cert-manager namespace
kubectl create secret generic vault-token \
    --from-literal=token="${CERT_MANAGER_TOKEN}" \
    -n cert-manager
```

### 4. Create ClusterIssuers

Create `~/k3s-setup/cluster-issuers.yaml`:

```yaml
---
# Vault issuer for local development (PRIMARY)
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: vault-issuer
spec:
  vault:
    server: http://192.168.31.247:8200
    path: pki/sign/poddle-uz
    auth:
      tokenSecretRef:
        name: vault-token
        key: token

---
# Self-signed issuer (FALLBACK)
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-issuer
spec:
  selfSigned: {}

---
# Let's Encrypt Staging (TESTING PUBLIC DOMAINS)
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    email: your-email@example.com
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-staging-key
    solvers:
      - http01:
          ingress:
            class: traefik

---
# Let's Encrypt Production (PRODUCTION PUBLIC DOMAINS)
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-production
spec:
  acme:
    email: your-email@example.com
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-production-key
    solvers:
      - http01:
          ingress:
            class: traefik
```

Apply:

```bash
kubectl apply -f ~/k3s-setup/cluster-issuers.yaml

# Verify all issuers are ready
kubectl get clusterissuer
```

### 5. Install Root CA on Host (Arch Linux)

```bash
# Install root CA system-wide
sudo cp ~/poddle-root-ca.crt /etc/ca-certificates/trust-source/anchors/
sudo update-ca-trust

# Verify installation
trust list | grep -A4 "Poddle Root CA"
```

### 6. Configure Firefox to Trust Root CA

```bash
# Find Firefox profile
FIREFOX_PROFILE=$(ls -d ~/.mozilla/firefox/*.default-release 2>/dev/null | head -1)

# Remove existing certificate (if any)
certutil -D -n "Poddle Root CA" -d "sql:$FIREFOX_PROFILE" 2>/dev/null || true

# Import with SSL trust flags
certutil -A -n "Poddle Root CA" -t "C,C,C" -i ~/poddle-root-ca.crt -d "sql:$FIREFOX_PROFILE"

# Verify
certutil -L -d "sql:$FIREFOX_PROFILE" | grep "Poddle Root CA"
# Should show: Poddle Root CA                                               C,C,C

# Restart Firefox COMPLETELY
pkill -9 firefox
```

---

## Deploy Services

### Example: Nginx with Automatic HTTPS

#### 1. Deployment

`nginx-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
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

#### 2. Service (ClusterIP, not LoadBalancer)

`nginx-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
  namespace: default
spec:
  type: ClusterIP  # Not LoadBalancer!
  selector:
    app: nginx
  ports:
    - port: 80
      targetPort: 80
```

#### 3. Ingress with Automatic TLS

`nginx-ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
  namespace: default
  annotations:
    # Use Vault for certificates
    cert-manager.io/cluster-issuer: vault-issuer
    # Traefik configuration
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - nginx.poddle.uz
      secretName: nginx-tls-cert  # Auto-created by cert-manager
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

#### 4. Deploy

```bash
kubectl apply -f nginx-deployment.yaml
kubectl apply -f nginx-service.yaml
kubectl apply -f nginx-ingress.yaml

# Watch certificate creation
kubectl get certificate -w
# Wait for READY=True

# Test HTTPS
curl https://nginx.poddle.uz
# Should show nginx welcome page

# Open in Firefox
firefox https://nginx.poddle.uz
# Should show green lock with "Connection verified by Poddle Root CA"
```

### Wildcard Certificate (Recommended)

Create one certificate for all subdomains:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-poddle-tls
  namespace: default
spec:
  secretName: wildcard-poddle-tls
  issuerRef:
    name: vault-issuer
    kind: ClusterIssuer
  commonName: "*.poddle.uz"
  dnsNames:
    - "*.poddle.uz"
    - "poddle.uz"
  duration: 2160h       # 90 days
  renewBefore: 720h     # Renew 30 days before expiry
```

Then in any Ingress, just reference the same secret:

```yaml
spec:
  tls:
    - hosts:
        - any-service.poddle.uz
      secretName: wildcard-poddle-tls  # Same for all services!
```

---

## Troubleshooting

### Certificate Not Ready

```bash
# Check certificate status
kubectl describe certificate <cert-name>

# Check cert-manager logs
kubectl logs -n cert-manager -l app=cert-manager -f

# Check certificate request
kubectl get certificaterequest
kubectl describe certificaterequest <request-name>
```

### DNS Not Resolving

```bash
# Test from host
nslookup nginx.poddle.uz  # Should return 192.168.31.10

# Test from K3s pod
kubectl run dns-test --image=busybox:1.36 --rm -it -- nslookup nginx.poddle.uz
```

### Vault Connection Issues

```bash
# Test from host
curl http://vault.poddle.uz:8200/v1/sys/health

# Test from K3s node
ssh kamronbek@192.168.31.106
curl http://vault.poddle.uz:8200/v1/sys/health
```

### Firefox Still Shows Warning

1. Verify certificate is installed:

   ```bash
   certutil -L -d sql:~/.mozilla/firefox/*.default-release | grep "Poddle Root CA"
   ```

   Should show `C,C,C` at the end

2. Completely restart Firefox:

   ```bash
   pkill -9 firefox
   ```

3. Clear Firefox certificate cache:
   - Settings → Privacy & Security → Certificates → View Certificates
   - Authorities → Find "Poddle Root CA"
   - Should show all checkboxes checked

---

## Reference

### Useful Commands

```bash
# Vault
export VAULT_ADDR='http://vault.poddle.uz:8200'
export VAULT_TOKEN='<token>'
vault status
vault token renew  # Renew cert-manager token

# Kubernetes
kubectl get clusterissuer
kubectl get certificate -A
kubectl get certificaterequest -A
kubectl get ingress -A

# cert-manager
kubectl logs -n cert-manager -l app=cert-manager -f
cmctl check api
cmctl status certificate <cert-name>

# DNS
nslookup vault.poddle.uz
dig @127.0.0.1 nginx.poddle.uz

# Firefox certificates
certutil -L -d sql:~/.mozilla/firefox/*.default-release
```

### File Structure

```bash
~/
├── poddle-root-ca.crt          # Root CA certificate (IMPORTANT!)
├── vault-keys.txt               # Vault unseal keys (IMPORTANT!)
├── cert-manager-token.json      # cert-manager token
└── k3s-setup/
    ├── cluster-issuers.yaml     # All certificate issuers
    ├── wildcard-cert.yaml       # Wildcard certificate
    └── examples/
        ├── nginx-deployment.yaml
        ├── nginx-service.yaml
        └── nginx-ingress.yaml
```

### ClusterIssuer Selection Guide

| Issuer | Use For | Browser Trust | Requires Public Domain |
|--------|---------|---------------|------------------------|
| `vault-issuer` | **Local development** (*.poddle.uz) | ✅ (after installing root CA) | ❌ No |
| `selfsigned-issuer` | Quick testing, no setup | ❌ Browser warning | ❌ No |
| `letsencrypt-staging` | Testing LE before production | ❌ Test certificates | ✅ Yes |
| `letsencrypt-production` | **Production public sites** | ✅ Automatic | ✅ Yes |

### Certificate Lifecycle

```bash
Root CA (Poddle Root CA)
├─ Valid for: 10 years
├─ Generated: Once
└─ Needs renewal: No (regenerate after 10 years)

Service Certificates (nginx.poddle.uz)
├─ Valid for: 30 days (default)
├─ Generated: Automatically by cert-manager
├─ Renewed: Automatically 7 days before expiry
└─ Signed by: Poddle Root CA
```

### Important Notes

1. **Root CA is everything**: If you lose `poddle-root-ca.crt`, you'll need to regenerate it and re-trust it on all machines
2. **Vault token renewal**: The cert-manager token expires after 24h but is renewable. Consider implementing auto-renewal
3. **Backup Vault data**: The Vault data in `~/Documents/Docker/volumes/vault_storage` contains the Root CA private key
4. **Production**: For production, use Let's Encrypt issuers (`letsencrypt-production`) for public domains

---

## What We Built

✨ **A production-ready Platform-as-a-Service with:**

- 🔐 Automated HTTPS for all services
- 🎫 Custom Certificate Authority (Vault PKI)
- 🚀 Zero-config deployments (just add Ingress, get HTTPS)
- 🔄 Automatic certificate renewal
- 📊 Full monitoring stack (Prometheus + Grafana)
- 🌐 Custom domain routing (`*.poddle.uz`)
- 🏗️ Highly available K3s cluster
- 📦 Container networking with Cilium

**Deploy a new service in 3 steps:**

1. Create Deployment + Service
2. Create Ingress with `cert-manager.io/cluster-issuer: vault-issuer`
3. Visit `https://your-service.poddle.uz` → ✅ Secure!

---

**Questions?** Check the troubleshooting section or review the architecture diagram.
