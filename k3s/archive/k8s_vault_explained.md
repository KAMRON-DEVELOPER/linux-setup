# Kubernetes + Vault Authentication Complete Guide

## 🎯 The Big Picture

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR KUBERNETES CLUSTER                      │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Pod: compute-provisioner                                │  │
│  │                                                          │  │
│  │  ServiceAccount: compute-provisioner ←─────────┐        │  │
│  │                                                 │        │  │
│  │  Auto-mounted JWT at:                          │        │  │
│  │  /var/run/secrets/kubernetes.io/               │        │  │
│  │  serviceaccount/token                          │        │  │
│  │                                                 │        │  │
│  │  ┌──────────────────────────────┐              │        │  │
│  │  │  Your Rust App reads JWT     │              │        │  │
│  │  │  from that path              │              │        │  │
│  │  └──────────────────────────────┘              │        │  │
│  │                │                                │        │  │
│  └────────────────│────────────────────────────────┘        │  │
│                   │                                          │  │
│                   ▼ (Sends JWT)                              │  │
│  ┌────────────────────────────────────────────────┐          │  │
│  │         Kubernetes API Server                  │          │  │
│  │    (Validates tokens via TokenReview)          │◄─────────┘  │
│  └────────────────────────────────────────────────┘          │  │
│                   ▲                                          │  │
└───────────────────│──────────────────────────────────────────┘
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

## 🔑 Key Concepts Explained

### 1. ServiceAccount (Kubernetes Side)

**What it is**: An identity for your pod

```bash
# Create a ServiceAccount
kubectl create serviceaccount compute-provisioner -n default
```

**What happens**: 
- Kubernetes creates an identity named "compute-provisioner"
- ANY pod that uses this ServiceAccount will get a JWT token for it
- The token is auto-mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`

### 2. ServiceAccount JWT Token

**What it is**: Proof of identity (automatically created by K8s)

**Where it lives in your pod**: `/var/run/secrets/kubernetes.io/serviceaccount/token`

**What's inside the JWT**:
```json
{
  "iss": "kubernetes/serviceaccount",
  "namespace": "default",
  "serviceaccount": {
    "name": "compute-provisioner"
  },
  "sub": "system:serviceaccount:default:compute-provisioner"
}
```

**This is what `k8s_sa_token_path` points to!**

### 3. Vault Kubernetes Auth Backend

**What it is**: A way for Vault to trust Kubernetes

**Setup Steps**:

```bash
# 1. Enable Kubernetes auth in Vault
vault auth enable kubernetes

# 2. Create a ServiceAccount that can VALIDATE other tokens
kubectl create serviceaccount vault-reviewer -n kube-system
kubectl create clusterrolebinding vault-reviewer-binding \
    --clusterrole=system:auth-delegator \
    --serviceaccount=kube-system:vault-reviewer

# 3. Configure Vault to trust your Kubernetes cluster
REVIEWER_TOKEN=$(kubectl create token vault-reviewer -n kube-system --duration=87600h)
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)
K8S_HOST="https://192.168.31.106:6443"

vault write auth/kubernetes/config \
    kubernetes_host="$K8S_HOST" \
    kubernetes_ca_cert="$K8S_CA_CERT" \
    token_reviewer_jwt="$REVIEWER_TOKEN"
```

**What this does**:
- Gives Vault the ability to ask Kubernetes "Is this JWT token valid?"
- `vault-reviewer` is the ServiceAccount that Vault USES to verify other tokens
- It's like giving Vault a master key to check IDs

### 4. Vault Roles (The Important Part!)

A **Vault role** maps Kubernetes identities to Vault permissions.

```bash
vault write auth/kubernetes/role/compute-provisioner \
    bound_service_account_names=compute-provisioner \
    bound_service_account_namespaces=default,compute \
    policies=vso-policy \
    ttl=24h
```

**Parameter Breakdown**:

- **`auth/kubernetes/role/compute-provisioner`**: 
  - Creates a role named "compute-provisioner"
  - This is the name your Rust code uses: `VAULT_AUTH_ROLE=compute-provisioner`

- **`bound_service_account_names=compute-provisioner`**:
  - ONLY pods using ServiceAccount "compute-provisioner" can use this role
  - Like saying "Only people named 'compute-provisioner' allowed"

- **`bound_service_account_namespaces=default,compute`**:
  - ONLY from namespaces "default" OR "compute"
  - Like saying "Only from these rooms in the building"

- **`policies=vso-policy`**:
  - What permissions this role gets in Vault
  - `vso-policy` allows reading `kvv2/data/deployments/*`

- **`ttl=24h`**:
  - How long the Vault token lasts (24 hours)
  - After 24h, your app must re-authenticate

### 5. KV Mount (`kv_mount` in VaultService)

**What it is**: The location where secrets are stored in Vault

```bash
# Create a KV v2 secrets engine at path "kvv2"
vault secrets enable -path=kvv2 -version=2 kv
```

**In your code**:
```rust
pub kv_mount: String, // This is "kvv2"
```

**When storing secrets**:
```rust
let path = "deployments/1213";
kv2::set(&client, "kvv2", &path, &secrets).await?;
//                 ^^^^^^ This is kv_mount
```

**Full path in Vault**: `kvv2/data/deployments/1213`
- `kvv2` = mount point
- `data` = automatically added by KV v2
- `deployments/1213` = your secret path

## 📋 Complete Setup Checklist

### Kubernetes Side

```bash
# 1. Create ServiceAccount for your app
kubectl create serviceaccount compute-provisioner -n default

# 2. Create ServiceAccount for Vault to verify tokens
kubectl create serviceaccount vault-reviewer -n kube-system
kubectl create clusterrolebinding vault-reviewer-binding \
    --clusterrole=system:auth-delegator \
    --serviceaccount=kube-system:vault-reviewer

# 3. Deploy your pod with the ServiceAccount
# In your deployment.yaml:
spec:
  serviceAccountName: compute-provisioner  # <-- Important!
```

### Vault Side

```bash
# 1. Enable Kubernetes auth
vault auth enable kubernetes

# 2. Configure Kubernetes auth (connect Vault to K8s)
REVIEWER_TOKEN=$(kubectl create token vault-reviewer -n kube-system --duration=87600h)
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)
K8S_HOST="https://192.168.31.106:6443"

vault write auth/kubernetes/config \
    kubernetes_host="$K8S_HOST" \
    kubernetes_ca_cert="$K8S_CA_CERT" \
    token_reviewer_jwt="$REVIEWER_TOKEN"

# 3. Create KV secrets engine
vault secrets enable -path=kvv2 -version=2 kv

# 4. Create policy (what can be accessed)
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

# 5. Create role (who can access)
vault write auth/kubernetes/role/compute-provisioner \
    bound_service_account_names=compute-provisioner \
    bound_service_account_namespaces=default,compute \
    policies=vso-policy \
    ttl=24h
```

## 🔄 Authentication Flow (Step by Step)

1. **Pod starts** with ServiceAccount `compute-provisioner`
2. **Kubernetes injects** JWT at `/var/run/secrets/kubernetes.io/serviceaccount/token`
3. **Your Rust app reads** that JWT file
4. **App sends JWT to Vault** at `/v1/auth/kubernetes/login`
   - With role name: `compute-provisioner`
5. **Vault asks Kubernetes**: "Is this JWT valid?"
   - Uses the `vault-reviewer` ServiceAccount to call TokenReview API
6. **Kubernetes responds**: "Yes, it's valid for SA=compute-provisioner, namespace=default"
7. **Vault checks role**: Does it match?
   - bound_service_account_names ✓
   - bound_service_account_namespaces ✓
8. **Vault issues token** with `vso-policy` attached
9. **Your app uses Vault token** to read/write secrets at `kvv2/data/deployments/*`

## 🆚 Why Two Roles?

```bash
# Role 1: For Vault Secrets Operator (VSO)
vault write auth/kubernetes/role/vso \
    bound_service_account_names=vault-secrets-operator \
    'bound_service_account_namespaces=vault-secrets-operator,user-*' \
    policies=vso-policy \
    ttl=24h

# Role 2: For your compute-provisioner app
vault write auth/kubernetes/role/compute-provisioner \
    bound_service_account_names=compute-provisioner \
    bound_service_account_namespaces=default,compute \
    policies=vso-policy \
    ttl=24h
```

**Why different roles?**

1. **Different ServiceAccounts** = Different identities
   - `vault-secrets-operator` is one app
   - `compute-provisioner` is another app

2. **Different namespace permissions**
   - VSO can access `vault-secrets-operator` AND `user-*` namespaces
   - compute-provisioner can only access `default` and `compute`

3. **Security**: Each app only gets what it needs (principle of least privilege)

**Same policy?** Yes, both use `vso-policy` because they need the same secrets access. You could create different policies if needed.

## 🎓 Summary

- **ServiceAccount** = Identity in Kubernetes
- **JWT Token** = Proof of that identity (auto-injected by K8s)
- **`k8s_sa_token_path`** = Where to find the JWT (usually `/var/run/secrets/kubernetes.io/serviceaccount/token`)
- **`kv_mount`** = Where secrets are stored in Vault (`kvv2`)
- **Vault Role** = Mapping of K8s identity → Vault permissions
- **Policy** = What paths/operations are allowed in Vault

**Not bad at all!** This is secure because:
- Each pod gets a unique token
- Vault verifies the token with Kubernetes
- Tokens are scoped to specific ServiceAccounts and namespaces
- No manual secret management needed