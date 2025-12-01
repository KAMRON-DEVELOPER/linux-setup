# PKI vs Secrets - Two Different Systems

## ⚠️ IMPORTANT: These are SEPARATE uses of Kubernetes auth!

```
vault auth enable kubernetes  ← ONE auth backend, MULTIPLE uses
    │
    ├─→ Use #1: cert-manager (for PKI/TLS certificates)
    │      Role: cert-manager
    │      Purpose: Issue TLS certificates
    │
    ├─→ Use #2: compute-provisioner (for secrets)
    │      Role: compute-provisioner  
    │      Purpose: Store/retrieve deployment secrets
    │
    └─→ Use #3: vault-secrets-operator (VSO)
           Role: vso
           Purpose: Sync secrets from Vault to K8s
```

## 🔧 The Shared Infrastructure

### What's Shared?

**Kubernetes Auth Configuration** (you only do this ONCE):

```bash
# This configuration is shared by ALL roles
vault write auth/kubernetes/config \
    kubernetes_host="$K8S_HOST" \
    kubernetes_ca_cert="$K8S_CA_CERT" \
    token_reviewer_jwt="$REVIEWER_TOKEN"
```

**What this does**: 
- Tells Vault HOW to talk to Kubernetes API
- Used by ALL apps that use Kubernetes auth

**The `vault-reviewer` ServiceAccount**:
- ONE ServiceAccount with special permissions
- Used by Vault to verify ALL JWT tokens
- Think of it as Vault's "master key" to check IDs

```bash
# Create once, used by everything
kubectl create serviceaccount vault-reviewer -n kube-system
kubectl create clusterrolebinding vault-reviewer-binding \
    --clusterrole=system:auth-delegator \
    --serviceaccount=kube-system:vault-reviewer
```

## 🎭 Different Roles for Different Apps

### Role 1: cert-manager (PKI)

```bash
# Enable PKI secrets engine
vault secrets enable pki

# Create role for cert-manager
vault write auth/kubernetes/role/cert-manager \
    bound_service_account_names=cert-manager \
    bound_service_account_namespaces=cert-manager \
    policies=cert-manager-policy \
    ttl=24h

# Policy for PKI
vault policy write cert-manager-policy - <<EOF
path "pki/sign/poddle-uz" {
  capabilities = ["create", "update"]
}
EOF
```

**What cert-manager does**:
1. Authenticates to Vault using its ServiceAccount
2. Requests TLS certificates from Vault PKI
3. Stores them as Kubernetes Secrets
4. Used by Ingress/services for HTTPS

### Role 2: compute-provisioner (Secrets)

```bash
# Enable KV secrets engine
vault secrets enable -path=kvv2 -version=2 kv

# Create role for compute-provisioner
vault write auth/kubernetes/role/compute-provisioner \
    bound_service_account_names=compute-provisioner \
    bound_service_account_namespaces=poddle-system \
    policies=vso-policy \
    ttl=24h

# Policy for secrets
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

**What compute-provisioner does**:
1. Authenticates to Vault using its ServiceAccount
2. Stores user deployment secrets
3. Retrieves secrets when needed
4. Manages application secrets

### Role 3: vault-secrets-operator (Optional)

```bash
# Create role for VSO
vault write auth/kubernetes/role/vso \
    bound_service_account_names=vault-secrets-operator \
    'bound_service_account_namespaces=vault-secrets-operator,user-*' \
    policies=vso-policy \
    ttl=24h
```

**What VSO does** (if you use it):
1. Watches for VaultSecret CRDs in Kubernetes
2. Syncs secrets from Vault → Kubernetes Secrets
3. Automatically updates when Vault secrets change

## 🔄 How TokenReview Works

When ANY app authenticates:

```
┌─────────────────┐
│  Your App       │
│  (any of them)  │
└────────┬────────┘
         │ JWT
         ▼
┌─────────────────┐
│  Vault          │
│  "Let me verify"│
└────────┬────────┘
         │ Uses vault-reviewer SA
         ▼
┌─────────────────────────────────┐
│  Kubernetes API - TokenReview   │
│                                 │
│  POST /apis/authentication.k8s.io/v1/tokenreviews
│  {                              │
│    "spec": {                    │
│      "token": "eyJhbGc..."      │
│    }                            │
│  }                              │
└────────┬────────────────────────┘
         │ Response
         ▼
┌─────────────────────────────────┐
│  {                              │
│    "status": {                  │
│      "authenticated": true,     │
│      "user": {                  │
│        "username": "system:serviceaccount:poddle-system:compute-provisioner",
│        "uid": "...",            │
│        "groups": [...]          │
│      }                          │
│    }                            │
│  }                              │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Vault          │
│  "Token valid!  │
│   Check role..." │
└────────┬────────┘
         │
         ▼
    Is it the right:
    - ServiceAccount name?
    - Namespace?
    If YES → Issue Vault token
    If NO → Deny
```

**Who calls it?**: Vault (using the `vault-reviewer` ServiceAccount)
**When?**: Every time ANY app tries to authenticate with Kubernetes auth
**How?**: Vault makes an HTTPS call to the K8s API using the reviewer token

## 🎯 Your Complete Setup

```bash
# ============================================
# ONE-TIME SETUP (Infrastructure)
# ============================================

# 1. Enable Kubernetes auth (once)
vault auth enable kubernetes

# 2. Create vault-reviewer (once)
kubectl create serviceaccount vault-reviewer -n kube-system
kubectl create clusterrolebinding vault-reviewer-binding \
    --clusterrole=system:auth-delegator \
    --serviceaccount=kube-system:vault-reviewer

# 3. Configure Kubernetes auth (once)
REVIEWER_TOKEN=$(kubectl create token vault-reviewer -n kube-system --duration=87600h)
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)
K8S_HOST="https://192.168.31.106:6443"

vault write auth/kubernetes/config \
    kubernetes_host="$K8S_HOST" \
    kubernetes_ca_cert="$K8S_CA_CERT" \
    token_reviewer_jwt="$REVIEWER_TOKEN"

# ============================================
# PKI SETUP (for TLS certificates)
# ============================================

# 4. Enable and configure PKI
vault secrets enable pki
vault secrets tune -max-lease-ttl=87600h pki

# 5. Create root CA
vault write -field=certificate pki/root/generate/internal \
    common_name="Poddle Root CA" \
    ttl=87600h

# 6. Configure PKI URLs
vault write pki/config/urls \
    issuing_certificates="http://vault.poddle.uz:8200/v1/pki/ca" \
    crl_distribution_points="http://vault.poddle.uz:8200/v1/pki/crl"

# 7. Create PKI role
vault write pki/roles/poddle-uz \
    allowed_domains="poddle.uz" \
    allow_subdomains=true \
    max_ttl="8760h"

# 8. Create cert-manager policy and role
vault policy write cert-manager-policy - <<EOF
path "pki/sign/poddle-uz" {
  capabilities = ["create", "update"]
}
EOF

vault write auth/kubernetes/role/cert-manager \
    bound_service_account_names=cert-manager \
    bound_service_account_namespaces=cert-manager \
    policies=cert-manager-policy \
    ttl=24h

# ============================================
# SECRETS SETUP (for application secrets)
# ============================================

# 9. Enable KV secrets engine
vault secrets enable -path=kvv2 -version=2 kv

# 10. Create secrets policy
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

# 11. Create compute-provisioner role
vault write auth/kubernetes/role/compute-provisioner \
    bound_service_account_names=compute-provisioner \
    bound_service_account_namespaces=poddle-system \
    policies=vso-policy \
    ttl=24h

# 12. Optional: Create VSO role (if you use it)
vault write auth/kubernetes/role/vso \
    bound_service_account_names=vault-secrets-operator \
    'bound_service_account_namespaces=vault-secrets-operator,user-*' \
    policies=vso-policy \
    ttl=24h
```

## 📊 Final Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    VAULT                                   │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │  Auth: kubernetes (ONE backend)                      │ │
│  │  Config: K8s API + vault-reviewer token             │ │
│  └──────────────────────────────────────────────────────┘ │
│           │                    │                   │       │
│           ▼                    ▼                   ▼       │
│     ┌─────────┐         ┌──────────┐        ┌─────────┐  │
│     │  Role:  │         │  Role:   │        │ Role:   │  │
│     │cert-mgr │         │compute-  │        │  vso    │  │
│     │         │         │provision │        │         │  │
│     └────┬────┘         └────┬─────┘        └────┬────┘  │
│          │                   │                    │       │
│          ▼                   ▼                    ▼       │
│     ┌─────────┐         ┌──────────┐        ┌─────────┐  │
│     │   PKI   │         │   KV:    │        │   KV:   │  │
│     │ Engine  │         │   kvv2   │        │   kvv2  │  │
│     └─────────┘         └──────────┘        └─────────┘  │
│         │                    │                    │       │
└─────────│────────────────────│────────────────────│───────┘
          │                    │                    │
          ▼                    ▼                    ▼
    TLS Certs         Deployment Secrets    Auto-sync to K8s
```

## ✅ Summary

1. **`vault auth enable kubernetes`**: ONE auth backend, MANY roles
2. **`vault-reviewer`**: Shared by ALL roles to verify tokens
3. **PKI role**: For cert-manager to get TLS certificates
4. **Secrets role**: For compute-provisioner to manage app secrets
5. **VSO role**: Optional, for automatic secret sync
6. **They DON'T interfere**: Separate policies, separate purposes
7. **Your compute-provisioner**: Only needs the secrets role