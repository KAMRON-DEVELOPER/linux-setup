# Complete K3s Setup Guide with Vault PKI and Kubernetes Auth

> **Production-ready K3s cluster with automated HTTPS using Vault PKI and Kubernetes authentication**

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [K3s Cluster Installation](#k3s-cluster-installation)
3. [Install Core Infrastructure](#install-core-infrastructure)
4. [Vault PKI Setup (Token-Based)](#vault-pki-setup-token-based)
5. [Vault Kubernetes Auth Setup](#vault-kubernetes-auth-setup)
6. [Deploy Applications with HTTPS](#deploy-applications-with-https)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### What You Need

- **Host Machine**: Arch Linux with Vault running in Docker
  - Vault accessible at `http://vault.poddle.uz:8200` or `http://192.168.31.247:8200`
  - Vault should be initialized and unsealed
  - DNS configured (dnsmasq resolving `*.poddle.uz`)

- **VMs**: 2+ Ubuntu 22.04 VMs
  - k3s-server: 192.168.31.106 (control plane)
  - k3s-agent: 192.168.31.26 (worker node)
  - Bridge networking to host
  - SSH access

### Verify Prerequisites

```bash
# On host: Check Vault is running
curl http://vault.poddle.uz:8200/v1/sys/health

# Check DNS resolution
nslookup vault.poddle.uz  # Should return 192.168.31.247
nslookup nginx.poddle.uz  # Should return 192.168.31.10

# Test VM connectivity
ssh kamronbek@192.168.31.106
ssh kamronbek@192.168.31.26
```

### Folder Structure

```bash
~/Documents/linux-setup/k3s/
├── charts/
│   ├── cilium-manifests/
│   │   └── values.yaml
│   ├── metallb-manifests/
│   │   ├── config.yaml
│   │   └── values.yaml
│   ├── prometheus-manifests/
│   │   └── values.yaml
│   └── traefik-manifests/
│       ├── values.yaml
│       └── traefik-dashboard.yaml
├── manifests/
│   ├── certificates/
│   │   └── wildcard-certificate.yaml
│   └── cluster-issuers/
│       └── cluster-issuers.yaml
└── example/
    ├── nginx-deployment.yaml
    ├── nginx-service.yaml
    └── nginx-ingress.yaml
```

---

## K3s Cluster Installation

### Step 1: Install K3s Server (Control Plane)

SSH into k3s-server VM (192.168.31.106):

```bash
ssh kamronbek@192.168.31.106

# Install K3s with minimal services
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

- `--disable traefik`: We'll install via Helm
- `--disable servicelb`: We'll use MetalLB
- `--flannel-backend=none`: We'll use Cilium as CNI
- `--disable-kube-proxy`: Cilium replaces kube-proxy (eBPF)

### Step 2: Verify K3s Server Installation

```bash
# Check K3s is running
sudo systemctl status k3s

# Get node token for agents
sudo cat /var/lib/rancher/k3s/server/node-token
# Save this token - you'll need it for agents
```

### Step 3: Install K3s Agent (Worker Node)

SSH into k3s-agent VM (192.168.31.26):

```bash
ssh kamronbek@192.168.31.26

# Set environment variables
export NODE_TOKEN="<token-from-server>"
export MASTER_IP="192.168.31.106"

# Install K3s agent
curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" \
  K3S_TOKEN="${NODE_TOKEN}" sh -
```

### Step 4: Setup Kubeconfig on Host

On your Arch Linux host:

```bash
# Copy kubeconfig from server
mkdir -p ~/.kube
scp kamronbek@192.168.31.106:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Update server IP (if you used --tls-san, you may not need this)
sed -i 's/127.0.0.1/192.168.31.106/g' ~/.kube/config

# Set permissions
chmod 600 ~/.kube/config

# Verify connection
kubectl get nodes
```

Expected output:

```
NAME         STATUS     ROLES                  AGE   VERSION
k3s-server   NotReady   control-plane,master   2m    v1.28.x
k3s-agent    NotReady   <none>                 1m    v1.28.x
```

**Note**: Nodes are "NotReady" because we haven't installed a CNI yet.

---

## Install Core Infrastructure

### Step 1: Create Directory Structure

```bash
cd ~/Documents/linux-setup/k3s
mkdir -p charts/{cilium-manifests,metallb-manifests,traefik-manifests,prometheus-manifests}
mkdir -p manifests/{certificates,cluster-issuers}
mkdir -p example
```

### Step 2: Install Cilium (CNI)

Create `charts/cilium-manifests/values.yaml`:

```yaml
ipam:
  mode: kubernetes
k8sServiceHost: 192.168.31.106
k8sServicePort: 6443
kubeProxyReplacement: true
```

Install Cilium:

```bash
# Add Helm repository
helm repo add cilium https://helm.cilium.io/
helm repo update

# Install Cilium
helm install cilium cilium/cilium \
  --namespace kube-system \
  --values charts/cilium-manifests/values.yaml

# Wait for Cilium to be ready
kubectl -n kube-system rollout status deployment/cilium-operator

# Verify nodes are now Ready
kubectl get nodes
```

Expected output:

```
NAME         STATUS   ROLES                  AGE   VERSION
k3s-server   Ready    control-plane,master   5m    v1.28.x
k3s-agent    Ready    <none>                 4m    v1.28.x
```

### Step 3: Install MetalLB (Load Balancer)

Create `charts/metallb-manifests/values.yaml`:

```yaml
prometheus:
  podMonitor:
    enabled: true
```

Create `charts/metallb-manifests/config.yaml`:

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

Install MetalLB:

```bash
# Add Helm repository
helm repo add metallb https://metallb.github.io/metallb
helm repo update

# Install MetalLB
helm install metallb metallb/metallb \
  --namespace metallb-system \
  --create-namespace \
  --values charts/metallb-manifests/values.yaml

# Apply configuration
kubectl apply -f charts/metallb-manifests/config.yaml

# Verify MetalLB is running
kubectl get pods -n metallb-system
```

### Step 4: Install Traefik (Ingress Controller)

Create `charts/traefik-manifests/values.yaml`:

```yaml
ports:
  web:
    redirectTo:
      port: websecure
  websecure:
    http3:
      enabled: true
    tls:
      enabled: true
ingressRoute:
  dashboard:
    enabled: true
```

Create `charts/traefik-manifests/traefik-dashboard.yaml`:

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: traefik-dashboard
  namespace: traefik
spec:
  entryPoints:
    - web
  routes:
    - match: Host('traefik.poddle.uz')
      kind: Rule
      services:
        - name: api@internal
          kind: TraefikService
```

Install Traefik:

```bash
# Add Helm repository
helm repo add traefik https://traefik.github.io/charts
helm repo update

# Install Traefik
helm install traefik traefik/traefik \
  --namespace traefik \
  --create-namespace \
  --values charts/traefik-manifests/values.yaml

# Verify Traefik got an external IP
kubectl get svc -n traefik
```

Expected output:

```
NAME      TYPE           CLUSTER-IP     EXTERNAL-IP     PORT(S)
traefik   LoadBalancer   10.43.x.x      192.168.31.10   80:xxx/TCP,443:xxx/TCP
```

### Step 5: Install cert-manager

```bash
# Add Helm repository
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Install cert-manager with CRDs
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.19.1 \
  --set crds.enabled=true

# Verify installation
kubectl get pods -n cert-manager
```

All three pods should be running:

- cert-manager
- cert-manager-cainjector
- cert-manager-webhook

### Step 6: Install Prometheus (Optional)

Create `charts/prometheus-manifests/values.yaml`:

```yaml
grafana:
  adminPassword: admin
prometheus:
  prometheusSpec:
    storageSpec:
      volumeClaimTemplate:
        spec:
          resources:
            requests:
              storage: 10Gi
```

Install Prometheus:

```bash
# Add Helm repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --values charts/prometheus-manifests/values.yaml

# Access Grafana
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Visit http://localhost:3000 (admin/admin)
```

---

## Vault PKI Setup (Token-Based)

This section configures Vault as a Certificate Authority and sets up token-based authentication for cert-manager.

### Step 1: Enable and Configure PKI

On your host machine:

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

echo "✅ Root CA certificate saved to ~/poddle-root-ca.crt"
```

### Step 2: Configure PKI URLs

```bash
# Configure certificate URLs
vault write pki/config/urls \
    issuing_certificates="http://vault.poddle.uz:8200/v1/pki/ca" \
    crl_distribution_points="http://vault.poddle.uz:8200/v1/pki/crl"
```

### Step 3: Create Role for Issuing Certificates

```bash
# Create role for *.poddle.uz domains
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

echo "✅ Vault PKI role 'poddle-uz' created"
```

### Step 4: Create Policy for cert-manager

```bash
# Create policy file
cat > /tmp/cert-manager-policy.hcl <<EOF
# Allow cert-manager to sign certificates
path "pki/sign/poddle-uz" {
  capabilities = ["create", "update"]
}

path "pki/issue/poddle-uz" {
  capabilities = ["create", "update"]
}

# Allow reading CA certificate
path "pki/cert/ca" {
  capabilities = ["read"]
}
EOF

# Apply policy
vault policy write cert-manager /tmp/cert-manager-policy.hcl

echo "✅ Vault policy 'cert-manager' created"
```

### Step 5: Create Token for cert-manager

```bash
# Create token
vault token create \
    -policy=cert-manager \
    -period=24h \
    -display-name=cert-manager \
    -no-default-policy \
    -format=json | tee ~/cert-manager-token.json

# Extract token
CERT_MANAGER_TOKEN=$(jq -r '.auth.client_token' ~/cert-manager-token.json)

echo "✅ Token created: $CERT_MANAGER_TOKEN"
```

### Step 6: Store Token in Kubernetes

```bash
# Create secret in cert-manager namespace
kubectl create secret generic vault-token \
    --from-literal=token="${CERT_MANAGER_TOKEN}" \
    -n cert-manager

echo "✅ Token stored in Kubernetes secret 'vault-token'"
```

### Step 7: Create ClusterIssuer (Token-Based)

Create `manifests/cluster-issuers/cluster-issuers.yaml`:

```yaml
---
# Token-based issuer (Simple, works immediately)
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
---
# Self-signed issuer (Fallback)
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned-ci
spec:
  selfSigned: {}
```

Apply:

```bash
kubectl apply -f manifests/cluster-issuers/cluster-issuers.yaml

# Verify issuer is ready
kubectl get clusterissuer vault-token-ci
```

Expected output:

```
NAME              READY   AGE
vault-token-ci    True    10s
```

### Step 8: Test Certificate Issuance

Create a test certificate:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: test-certificate
  namespace: default
spec:
  secretName: test-tls
  issuerRef:
    name: vault-token-ci
    kind: ClusterIssuer
  commonName: test.poddle.uz
  dnsNames:
    - test.poddle.uz
EOF

# Watch certificate creation
kubectl get certificate test-certificate -w
```

The certificate should become READY within 10-30 seconds.

---

## Vault Kubernetes Auth Setup

Kubernetes authentication is more secure than static tokens. It uses ServiceAccount tokens that are automatically rotated.

### Step 1: Enable Kubernetes Auth in Vault

```bash
export VAULT_ADDR='http://vault.poddle.uz:8200'
export VAULT_TOKEN='<your-root-token>'

# Enable Kubernetes auth method
vault auth enable kubernetes

echo "✅ Kubernetes auth method enabled"
```

### Step 2: Configure Kubernetes Auth

You need to provide Vault with:

1. Kubernetes API server URL
2. Kubernetes CA certificate
3. A JWT token to verify against

```bash
# Get Kubernetes CA certificate
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)

# Get Kubernetes API server
K8S_HOST="https://192.168.31.106:6443"

# Get ServiceAccount JWT token
# First, get the token from the cert-manager ServiceAccount
TOKEN_NAME=$(kubectl get serviceaccount cert-manager -n cert-manager \
    -o jsonpath='{.secrets[0].name}' 2>/dev/null)

if [ -z "$TOKEN_NAME" ]; then
    # For K8s 1.24+, tokens are not automatically created
    # Create a token manually
    kubectl create token cert-manager -n cert-manager --duration=8760h > /tmp/sa-token
    SA_JWT_TOKEN=$(cat /tmp/sa-token)
else
    SA_JWT_TOKEN=$(kubectl get secret $TOKEN_NAME -n cert-manager \
        -o jsonpath='{.data.token}' | base64 -d)
fi

# Configure Kubernetes auth
vault write auth/kubernetes/config \
    kubernetes_host="$K8S_HOST" \
    kubernetes_ca_cert="$K8S_CA_CERT" \
    token_reviewer_jwt="$SA_JWT_TOKEN"

echo "✅ Kubernetes auth configured"
```

### Step 3: Create Vault Role for cert-manager

```bash
# Create role that binds to cert-manager ServiceAccount
vault write auth/kubernetes/role/cert-manager \
    bound_service_account_names=cert-manager \
    bound_service_account_namespaces=cert-manager \
    policies=cert-manager \
    ttl=24h

echo "✅ Vault role 'cert-manager' created for Kubernetes auth"
```

### Step 4: Create Kubernetes Auth ClusterIssuer

Add to `manifests/cluster-issuers/cluster-issuers.yaml`:

```yaml
---
# Kubernetes auth issuer (Production-ready, more secure)
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

Apply:

```bash
kubectl apply -f manifests/cluster-issuers/cluster-issuers.yaml

# Verify issuer is ready
kubectl get clusterissuer vault-k8s-ci
```

Expected output:

```
NAME            READY   AGE
vault-k8s-ci    True    10s
```

### Step 5: Test Kubernetes Auth

Create a test certificate using Kubernetes auth:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: test-k8s-auth
  namespace: default
spec:
  secretName: test-k8s-auth-tls
  issuerRef:
    name: vault-k8s-ci
    kind: ClusterIssuer
  commonName: k8s-test.poddle.uz
  dnsNames:
    - k8s-test.poddle.uz
EOF

# Watch certificate creation
kubectl get certificate test-k8s-auth -w
```

### Step 6: Create Wildcard Certificate

Create `manifests/certificates/wildcard-certificate.yaml`:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-poddle-uz-certificate
  namespace: default
spec:
  secretName: wildcard-poddle-uz-secret
  issuerRef:
    name: vault-k8s-ci
    kind: ClusterIssuer
  commonName: "*.poddle.uz"
  dnsNames:
    - "*.poddle.uz"
    - "poddle.uz"
  duration: 720h # 30 days
  renewBefore: 168h # Renew 7 days before expiry
```

Apply:

```bash
kubectl apply -f manifests/certificates/wildcard-certificate.yaml

# Watch certificate creation
kubectl get certificate wildcard-poddle-uz-certificate -w
```

---

## Deploy Applications with HTTPS

### Example: Nginx with Automatic HTTPS

#### 1. Create Deployment

Create `example/nginx-deployment.yaml`:

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

#### 2. Create Service

Create `example/nginx-service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: nginx
  namespace: default
spec:
  type: ClusterIP # Not LoadBalancer!
  selector:
    app: nginx
  ports:
    - port: 80
      targetPort: 80
```

#### 3. Create Ingress with TLS

Create `example/nginx-ingress.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-ingress
  namespace: default
  annotations:
    # Use Kubernetes auth issuer
    cert-manager.io/cluster-issuer: vault-k8s-ci
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  tls:
    - hosts:
        - nginx.poddle.uz
      secretName: nginx-tls-cert
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
kubectl apply -f example/nginx-deployment.yaml
kubectl apply -f example/nginx-service.yaml
kubectl apply -f example/nginx-ingress.yaml

# Watch certificate creation
kubectl get certificate -w
```

#### 5. Verify

```bash
# Check certificate is ready
kubectl get certificate
# NAME             READY   SECRET           AGE
# nginx-tls-cert   True    nginx-tls-cert   1m

# Test HTTP (should redirect to HTTPS)
curl -I http://nginx.poddle.uz

# Test HTTPS
curl https://nginx.poddle.uz
```

### Using Wildcard Certificate

To use the wildcard certificate for all services, just reference it in Ingress:

```yaml
spec:
  tls:
    - hosts:
        - any-service.poddle.uz
      secretName: wildcard-poddle-uz-secret # Shared across all services
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

Common issues:

- **DNS resolution**: Vault hostname not resolvable from pods
- **Network connectivity**: Pods can't reach Vault
- **Authentication**: Token expired or K8s auth misconfigured

### Vault Connection Issues

```bash
# Test from host
curl http://vault.poddle.uz:8200/v1/sys/health

# Test from K3s pod
kubectl run test --image=curlimages/curl --rm -it -- \
    curl http://vault.poddle.uz:8200/v1/sys/health
```

### Kubernetes Auth Fails

```bash
# Verify ServiceAccount exists
kubectl get sa cert-manager -n cert-manager

# Verify Vault role
vault read auth/kubernetes/role/cert-manager

# Test authentication manually
vault write auth/kubernetes/login \
    role=cert-manager \
    jwt="$(kubectl create token cert-manager -n cert-manager)"
```

### ClusterIssuer Not Ready

```bash
# Check ClusterIssuer status
kubectl describe clusterissuer vault-k8s-ci

# Common reasons:
# - Vault server unreachable
# - Wrong path or role name
# - ServiceAccount doesn't have permissions
```

---

## Summary

### What We Built

✅ **K3s Cluster**: Production-ready Kubernetes cluster
✅ **Cilium CNI**: Modern container networking with eBPF
✅ **MetalLB**: LoadBalancer for on-premises clusters
✅ **Traefik**: Ingress controller with automatic TLS
✅ **cert-manager**: Automatic certificate management
✅ **Vault PKI**: Custom Certificate Authority
✅ **Two Auth Methods**:

- Token-based (simple, works immediately)
- Kubernetes auth (production-ready, more secure)

### ClusterIssuer Comparison

| Issuer           | Auth Method        | Security                | Use Case                 |
| ---------------- | ------------------ | ----------------------- | ------------------------ |
| `vault-token-ci` | Static token       | ⚠️ Token expires in 24h | Quick setup, development |
| `vault-k8s-ci`   | ServiceAccount JWT | ✅ Auto-rotated         | Production, recommended  |
| `selfsigned-ci`  | None               | ⚠️ Self-signed          | Testing only             |

### Next Steps

1. **Install Root CA**: Add `~/poddle-root-ca.crt` to your system trust store
2. **Configure Browser**: Import Root CA into Firefox/Chrome
3. **Deploy Applications**: Use `cert-manager.io/cluster-issuer: vault-k8s-ci` annotation
4. **Monitor**: Check Prometheus/Grafana dashboards
5. **Production**: Switch to Let's Encrypt for public domains

### Key Commands

```bash
# Check cluster health
kubectl get nodes
kubectl get pods -A

# Check certificates
kubectl get certificate -A
kubectl get clusterissuer

# Check Vault
vault status
vault read auth/kubernetes/role/cert-manager

# Renew cert-manager token (if using token auth)
vault token renew <token>
```

---

**Your K3s cluster with automated HTTPS is now ready! 🚀**
