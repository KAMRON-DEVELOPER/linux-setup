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
9. [Vault KV Secrets for Applications](#9-vault-kv-secrets-for-applications)
10. [Deploy Test Application](#10-deploy-test-application)
11. [Trust Root CA](#11-trust-root-ca)
12. [Troubleshooting](#12-troubleshooting)
13. [Understanding Kubernetes + Vault Auth](#13-understanding-kubernetes--vault-auth)

---

## 1. Prerequisites

### Assumptions

- **Vault is running** in Docker on your host machine (e.g., `192.168.31.2:8200`)
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
| Server | k3s-server | 192.168.31.4 | Ubuntu 22.04 |
| Agent | k3s-agent-1 | 192.168.31.5 | Ubuntu 22.04 |
| Agent | k3s-agent-2 | 192.168.31.6 | Ubuntu 22.04 |

> Each machine must have a unique hostname.

---

## 2. K3s Cluster Installation

### 2.1 Install K3s Server

SSH into the server node (`192.168.31.4`):

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
  --bind-address=192.168.31.4 \
  --advertise-address=192.168.31.4 \
  --node-ip=192.168.31.4 \
  --tls-san=192.168.31.4
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

SSH into the agent node (`192.168.31.5`):

```bash
export NODE_TOKEN="<token-from-server>"
export MASTER_IP="192.168.31.4"

curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" \
  K3S_TOKEN="${NODE_TOKEN}" sh -
```

### 2.3 Setup Kubeconfig on Host

On your Arch Linux host:

```bash
mkdir -p ~/.kube
scp kamronbek@192.168.31.4:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Update API server address
sed -i 's/127.0.0.1/192.168.31.4/g' ~/.kube/config

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
  --set k8sServiceHost=192.168.31.4 \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true

# or

helm install cilium cilium/cilium \                                                           
  --namespace kube-system \
  --set k8sServiceHost=192.168.31.146 \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true \
  --values k3s/charts/cilium-manifests/cilium-values.yaml
```

Wait for Cilium to be ready:

> Don't forget to install cilium-cli. On arch ```sudo pacman -S cilium-cli```

```bash
kubectl -n kube-system rollout status deployment/cilium-operator
cilium-cli status --wait
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

# or

helm install metallb metallb/metallb \                                                      
  --namespace metallb-system \
  --create-namespace \
  --values k3s/charts/metallb-manifests/metallb-values.yaml
```

Wait for MetalLB pods:

```bash
kubectl -n metallb-system rollout status deployment/metallb-controller
```

Apply IP pool configuration:

```bash
kubectl apply -f k3s/charts/metallb-manifests/config.yaml
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

# or `https://doc.traefik.io/traefik/getting-started/quick-start-with-kubernetes/`
helm install traefik traefik/traefik --wait \
  --set ingressRoute.dashboard.enabled=true \
  --set ingressRoute.dashboard.matchRule='Host(`traefik.poddle.uz`)' \
  --set ingressRoute.dashboard.entryPoints={web} \
  --set providers.kubernetesGateway.enabled=true \
  --set gateway.listeners.web.namespacePolicy.from=All \
  --namespace traefik \
  --create-namespace

# or
helm install traefik traefik/traefik \                                                      
  --namespace traefik --create-namespace \
  --values k3s/charts/traefik-manifests/traefik-values.yaml
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
  --set crds.enabled=true

# or

helm repo add jetstack https://charts.jetstack.io --force-update
helm upgrade --install \
cert-manager jetstack/cert-manager \
--namespace cert-manager \
--create-namespace \ 
--set crds.enabled=true \
--set "extraArgs={--enable-gateway-api}"
```

Verify:

```bash
kubectl get pods -n cert-manager
# All pods should be Running
```

---

## 7. Vault PKI Setup (Static Token)

> This approach uses a manually created Vault token stored in Kubernetes Secret.

### 7.1 Initial vault setup

```bash
~/Documents/Docker ❯ vault operator init
```

> output

```bash
Unseal Key 1: ...
Unseal Key 2: ...
Unseal Key 3: ...
Unseal Key 4: ...
Unseal Key 5: ...

Initial Root Token: ...

Vault initialized with 5 key shares and a key threshold of 3. Please securely
distribute the key shares printed above. When the Vault is re-sealed,
restarted, or stopped, you must supply at least 3 of these keys to unseal it
before it can start servicing requests.

Vault does not store the generated root key. Without at least 3 keys to
reconstruct the root key, Vault will remain permanently sealed!

It is possible to generate new unseal keys, provided you have a quorum of
existing unseal keys shares. See "vault operator rekey" for more information.
```

> Run these commands, You should run at leasy three of them to unseal vault

```bash
~/Documents/Docker ❯ vault operator unseal $UNSEAL_KEY1
~/Documents/Docker ❯ vault operator unseal $UNSEAL_KEY2
~/Documents/Docker ❯ vault operator unseal $UNSEAL_KEY3
```

> ~/.zsh_secrets file should be like this

```bash
UNSEAL_KEY1='...'
UNSEAL_KEY2='...'
UNSEAL_KEY3='...'
UNSEAL_KEY4='...'
UNSEAL_KEY5='...'

VAULT_TOKEN='...'
```

> ~/.zshrc file should be added, so it prevent from adding to git/stow like flow

```bash
export KUBE_EDITOR="nvim"
export VAULT_ADDR='http://vault.poddle.uz:8200'

# Load local secrets
[[ -f "$HOME/.zsh_secrets" ]] && source "$HOME/.zsh_secrets"
# if [[ -f "$HOME/.zsh_secrets" ]]; then
#   source "$HOME/.zsh_secrets"
# fi
```

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
    issuer_name="poddle-issuer-2025-12-26" \
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
    server: http://192.168.31.2:8200
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
K8S_HOST="https://192.168.31.4:6443"

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
> there is no flag like `--serviceaccount=...` But!
> The vault-reviewer in this command is the ServiceAccount name. The command is specifically creating a token for that ServiceAccount.

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
kubectl apply -f k3s/manifests/cluster-issuers/cluster-issuers.yaml
```

<details>
<summary>manifests/cluster-issuers/cluster-issuers.yaml (k8s-auth)</summary>

```yaml
# Self-signed issuer for local development
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-ci
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: vault-token-ci
spec:
  vault:
    server: http://192.168.31.53:8200
    path: pki/sign/poddle-uz
    auth:
      tokenSecretRef:
        name: vault-token
        key: token
---
# Kubernetes auth
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: vault-k8s-ci
spec:
  vault:
    server: http://192.168.31.53:8200
    path: pki/sign/poddle-uz
    auth:
      kubernetes:
        role: cert-manager
        mountPath: /v1/auth/kubernetes
        serviceAccountRef:
          name: cert-manager
---
# Let's Encrypt Staging
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging-ci
spec:
  acme:
    # Staging server for testing (higher rate limits)
    email: atajanovkamronbek2003@gmail.com
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-staging-private-key
    solvers:
      - http01:
          ingress:
            class: traefik
---
# Let's Encrypt Production
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-production-ci
spec:
  acme:
    # Production server (strict rate limits)
    email: atajanovkamronbek2003@gmail.com
    server: https://acme-v02.api.letsencrypt.org/directory
    privateKeySecretRef:
      name: letsencrypt-production-private-key
    solvers:
      - http01:
          ingress:
            class: traefik
```

</details>

### Checking

```bash
~ ❯ kubectl get clusterissuers
NAME                        READY   AGE
letsencrypt-production-ci   True    2m37s
letsencrypt-staging-ci      True    2m37s
selfsigned-ci               True    2m37s
vault-k8s-ci                True    2m37s
vault-token-ci              False   2m37s
```

### Apply wildcard certificate

```bash
kubectl apply -f k3s/manifests/certificates/wildcard-certificate.yaml
```

<details>
<summary>manifests/cluster-issuers/cluster-issuers.yaml (k8s-auth)</summary>

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-poddle-uz-certificate
  namespace: traefik
spec:
  secretName: wildcard-poddle-uz-tls
  issuerRef:
    name: vault-k8s-ci
    kind: ClusterIssuer
    group: cert-manager.io
  commonName: "*.poddle.uz"
  dnsNames:
    - "*.poddle.uz"
    - "poddle.uz"
  duration: 720h # 30 days
  renewBefore: 168h # Renew 7 days before expiry
```

</details>

---

> head to k3s/manifests/vault/README.md

---

## 9. Vault KV Secrets for Applications (OLD)

> This section configures Vault to store application secrets (env vars, API keys, etc.) separately from PKI certificates.

### Understanding PKI vs Secrets

Vault uses ONE Kubernetes auth backend for MULTIPLE purposes:

```
vault auth enable kubernetes  ← ONE auth backend, MULTIPLE uses
    │
    ├─→ Use #1: cert-manager (for PKI/TLS certificates)
    │      Role: cert-manager
    │      Purpose: Issue TLS certificates
    │
    └─→ Use #2: compute-provisioner (for secrets)
           Role: compute-provisioner
           Purpose: Store/retrieve deployment secrets
```

### 9.1 Enable KV Secrets Engine

```bash
vault secrets enable -path=kvv2 -version=2 kv
```

### 9.2 Create Secrets Policy

```bash
vault policy write vso-policy - <<EOF
path "kvv2/data/deployments/*" {
  capabilities = ["read", "create", "update"]
}
path "kvv2/metadata/deployments/*" {
  capabilities = ["list", "read"]
}
path "kvv2/delete/deployments/*" {
  capabilities = ["update"]
}
EOF
```

### 9.3 Create ServiceAccount for Your Application

```bash
kubectl create serviceaccount compute-provisioner -n poddle-system
```

### 9.4 Create Vault Role for compute-provisioner

```bash
vault write auth/kubernetes/role/compute-provisioner \
    bound_service_account_names=compute-provisioner \
    bound_service_account_namespaces=poddle-system \
    policies=vso-policy \
    ttl=24h
```

**Parameter Breakdown:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `bound_service_account_names` | `compute-provisioner` | Only this SA can authenticate |
| `bound_service_account_namespaces` | `poddle-system` | Only from this namespace |
| `policies` | `vso-policy` | What secrets can be accessed |
| `ttl` | `24h` | Token lifetime before re-auth |

### 9.5 Configure Your Application

Your application needs these environment variables:

```yaml
env:
  - name: VAULT_ADDRESS
    value: "http://192.168.31.2:8200"
  - name: VAULT_AUTH_MOUNT
    value: "kubernetes"
  - name: VAULT_AUTH_ROLE
    value: "compute-provisioner"
  - name: VAULT_KV_MOUNT
    value: "kvv2"
```

The ServiceAccount JWT is automatically mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`.

### 9.6 Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: compute-provisioner
  namespace: poddle-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: compute-provisioner
  template:
    metadata:
      labels:
        app: compute-provisioner
    spec:
      serviceAccountName: compute-provisioner  # Important!
      containers:
        - name: app
          image: your-image:latest
          env:
            - name: VAULT_ADDRESS
              value: "http://192.168.31.2:8200"
            - name: VAULT_AUTH_MOUNT
              value: "kubernetes"
            - name: VAULT_AUTH_ROLE
              value: "compute-provisioner"
            - name: VAULT_KV_MOUNT
              value: "kvv2"
```

### 9.7 Verify Authentication

```bash
# Test from inside a pod
kubectl exec -it <pod-name> -n poddle-system -- sh

# Read the SA token
cat /var/run/secrets/kubernetes.io/serviceaccount/token

# Test Vault login (from your host with the token)
vault write auth/kubernetes/login \
    role=compute-provisioner \
    jwt="$(kubectl create token compute-provisioner -n poddle-system)"
```

---

## 10. Deploy Test Application

### 10.1 Deploy Nginx

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

### 10.2 Verify Certificate

```bash
# Watch certificate creation
kubectl get certificate -w

# Check certificate details
kubectl describe certificate nginx-tls-secret

# Test HTTPS
curl -k https://nginx.poddle.uz
```

---

## 11. Trust Root CA

### 11.1 Arch Linux System-Wide

```bash
sudo cp ~/poddle-root-ca.crt /etc/ca-certificates/trust-source/anchors/
sudo update-ca-trust

# Verify
trust list | grep -A4 "Poddle Root CA"
```

### 11.2 Firefox

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

## 12. Troubleshooting

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
forward . 192.168.31.2 /etc/resolv.conf
```

Or use IP directly in ClusterIssuer:

```yaml
server: http://192.168.31.2:8200  # Use IP instead of hostname
```

### Vault Connection Issues

```bash
# Test from host
curl http://vault.poddle.uz:8200/v1/sys/health

# Test from K3s node
ssh kamronbek@192.168.31.4
curl http://192.168.31.2:8200/v1/sys/health
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

---

## 13. Understanding Kubernetes + Vault Auth

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR KUBERNETES CLUSTER                      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Pod: compute-provisioner                                │  │
│  │                                                          │  │
│  │  ServiceAccount: compute-provisioner                     │  │
│  │                                                          │  │
│  │  Auto-mounted JWT at:                                    │  │
│  │  /var/run/secrets/kubernetes.io/serviceaccount/token     │  │
│  │                                                          │  │
│  │  ┌──────────────────────────────┐                        │  │
│  │  │  Your App reads JWT          │                        │  │
│  │  │  from that path              │                        │  │
│  │  └──────────────────────────────┘                        │  │
│  │                │                                          │  │
│  └────────────────│──────────────────────────────────────────┘  │
│                   │                                              │
│                   ▼ (Sends JWT)                                  │
│  ┌────────────────────────────────────────────────┐              │
│  │         Kubernetes API Server                  │◄─────────────┤
│  │    (Validates tokens via TokenReview)          │              │
│  └────────────────────────────────────────────────┘              │
│                   ▲                                              │
└───────────────────│──────────────────────────────────────────────┘
                    │
                    │ (Vault asks K8s: "Is this JWT valid?")
                    │
┌───────────────────│──────────────────────────────────────────┐
│                   │         VAULT (Running on Host)          │
│                   │                                          │
│  ┌────────────────▼─────────────────────────────┐            │
│  │  Kubernetes Auth Backend                     │            │
│  │  (Configured with vault-reviewer SA)         │            │
│  └──────────────────────────────────────────────┘            │
│                   │                                          │
│                   ▼ (JWT is valid!)                          │
│  ┌──────────────────────────────────────────────┐            │
│  │  Issues Vault Token with policies            │            │
│  │  Policies: vso-policy                        │            │
│  └──────────────────────────────────────────────┘            │
│                   │                                          │
│                   ▼                                          │
│  ┌──────────────────────────────────────────────┐            │
│  │  KV Secrets Engine (kvv2)                    │            │
│  │  Path: kvv2/data/deployments/*               │            │
│  └──────────────────────────────────────────────┘            │
└──────────────────────────────────────────────────────────────┘
```

### What is K8S_CA_CERT?

The `K8S_CA_CERT` is the root certificate that signed your Kubernetes API server's TLS certificate. Vault needs it to verify it's talking to the real K8s API server.

```bash
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)
```

### Why Two ServiceAccounts?

| ServiceAccount | Purpose | Permissions |
|----------------|---------|-------------|
| `vault-reviewer` | Allows Vault to verify JWT tokens | `system:auth-delegator` |
| `compute-provisioner` | Identity for your app | None (just identity) |

**vault-reviewer** is used by Vault itself to call the Kubernetes TokenReview API. It's like giving Vault a master key to check IDs.

**compute-provisioner** is the identity your application uses. When your app sends its JWT to Vault, Vault uses the vault-reviewer credentials to ask Kubernetes "Is this JWT valid?"

### Step-by-Step Auth Flow

1. **Pod starts** with ServiceAccount `compute-provisioner`
2. **Kubernetes injects** JWT at `/var/run/secrets/kubernetes.io/serviceaccount/token`
3. **Your app reads** that JWT file
4. **App sends JWT to Vault** at `/v1/auth/kubernetes/login` with role name: `compute-provisioner`
5. **Vault asks Kubernetes**: "Is this JWT valid?" (using vault-reviewer SA)
6. **Kubernetes responds**: "Yes, it's valid for SA=compute-provisioner, namespace=poddle-system"
7. **Vault checks role**: Does it match `bound_service_account_names` and `bound_service_account_namespaces`?
8. **Vault issues token** with `vso-policy` attached
9. **Your app uses Vault token** to read/write secrets at `kvv2/data/deployments/*`

### ClusterIssuer Comparison

| Issuer | Auth Method | Security | Use Case |
|--------|-------------|----------|----------|
| `vault-token-ci` | Static token | ⚠️ Token expires in 24h | Quick setup, development |
| `vault-k8s-ci` | ServiceAccount JWT | ✅ Auto-rotated | Production, recommended |
