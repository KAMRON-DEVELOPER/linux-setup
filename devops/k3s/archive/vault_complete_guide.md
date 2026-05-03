# Complete Vault + Kubernetes + cert-manager Integration Guide

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Install cert-manager](#install-cert-manager)
4. [Vault PKI Setup (Static Token Method)](#vault-pki-setup-static-token-method)
5. [Kubernetes Auth with Vault (Recommended)](#kubernetes-auth-with-vault-recommended)
6. [Vault KV Secrets for Applications](#vault-kv-secrets-for-applications)
7. [Multi-Tenant PaaS Best Practices](#multi-tenant-paas-best-practices)
8. [Deep Dive: How Everything Works](#deep-dive-how-everything-works)
9. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Your Infrastructure Setup

```
Host Machine (Physical/VM)
├── Docker
│   └── Vault (http://vault.poddle.uz:8200)
│       ├── PKI Engine (for TLS certificates)
│       └── KV v2 Engine (for application secrets)
└── dnsmasq (DNS server)

KVM VMs (K3s Kubernetes Cluster)
├── cert-manager namespace
│   ├── cert-manager (requests TLS certs from Vault)
│   ├── ServiceAccount: cert-manager
│   └── Secret: vault-token (for static token method)
├── vault-secrets-operator namespace
│   └── vault-secrets-operator (syncs app secrets from Vault to K8s)
├── kube-system namespace
│   └── ServiceAccount: vault-reviewer (for TokenReview API)
├── user-c24c787985e140a3 namespace (tenant 1)
│   ├── Your deployed applications
│   └── VaultAuth CR (per-tenant Vault authentication)
├── user-XXXXXXXX namespace (tenant 2)
│   └── VaultAuth CR (isolated per-tenant)
└── poddle-system namespace
    └── compute-provisioner (your Rust service that talks to K8s)
        └── ServiceAccount: compute-provisioner
```

### Two Separate Vault Use Cases

**Important**: Vault serves TWO distinct purposes in your setup:

1. **PKI Engine** → TLS Certificates for HTTPS
   - Used by: cert-manager
   - Purpose: Issue wildcard certificates like `*.poddle.uz`
   - Storage: Certificates stored as Kubernetes Secrets
   - Renewal: Automatic (cert-manager handles it)

2. **KV v2 Engine** → Application Secrets
   - Used by: vault-secrets-operator + your applications
   - Purpose: Store sensitive data (passwords, API keys, tokens)
   - Storage: Synced from Vault to Kubernetes Secrets
   - Access: Per-tenant isolation via namespace-specific VaultAuth

---

## Prerequisites

- K3s or any Kubernetes cluster running
- Vault installed and unsealed
- `kubectl` configured
- `vault` CLI installed on your machine
- Helm 3.x installed

---

## Install cert-manager

cert-manager is a Kubernetes controller that automates TLS certificate management.

```bash
# Add the Jetstack Helm repository
helm repo add jetstack https://charts.jetstack.io
helm repo update

# Install cert-manager with CRDs
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.15.1 \
  --set crds.enabled=true \
  --set "extraArgs={--enable-gateway-api}"
```

**What this installs:**
- `cert-manager` pod: Main controller
- `cert-manager-cainjector` pod: Injects CA bundles into webhooks/APIServices
- `cert-manager-webhook` pod: Validates cert-manager CRDs

**Verify installation:**

```bash
kubectl get pods -n cert-manager
# Expected output: All 3 pods in Running state

# Check if CRDs are installed
kubectl get crd | grep cert-manager
# Should show: certificates, issuers, clusterissuers, etc.
```

---

## Vault PKI Setup (Static Token Method)

> **Note**: This is the simpler but less secure method. For production, use [Kubernetes Auth](#kubernetes-auth-with-vault-recommended).

### Step 1: Enable PKI Secrets Engine

Connect to Vault:

```bash
export VAULT_ADDR='http://vault.poddle.uz:8200'
export VAULT_TOKEN='<your-root-token>'

# Enable PKI at the "pki/" mount path
vault secrets enable pki
```

**What this does:**
- Creates a new secrets engine of type "pki" at the path `/pki`
- This engine specializes in generating and managing X.509 certificates
- Think of it as a dedicated CA (Certificate Authority) service inside Vault

### Step 2: Configure PKI Engine

```bash
# Set maximum lease TTL to 10 years
vault secrets tune -max-lease-ttl=87600h pki
```

**What is `-max-lease-ttl`?**
- **Lease**: In Vault, everything has a "lease" (expiration time)
- `87600h` = 10 years (365 days × 10 × 24 hours)
- This is the **absolute maximum** lifetime for any certificate issued by this PKI engine
- Even if a role allows 20 years, Vault will reject it because the engine's limit is 10 years

### Step 3: Generate Root CA Certificate

```bash
vault write -field=certificate pki/root/generate/internal \
    common_name="Poddle Root CA" \
    issuer_name="root-2025" \
    ttl=87600h > ~/poddle-root-ca.crt
```

**Breaking down this command:**

1. **`vault write`**: Write data to Vault (not just reading)

2. **`-field=certificate`**:
   - Vault normally returns JSON with metadata (serial number, expiration, etc.)
   - `-field=certificate` extracts ONLY the certificate in PEM format
   - Clean output suitable for piping to a file

3. **`pki/root/generate/internal`**:
   - `pki/` = The mount path of your PKI engine
   - `root/generate/` = Generate a new Root CA certificate
   - `internal` = **Critical choice**: The private key is generated INSIDE Vault and NEVER leaves
     - Alternative: `exported` would give you the private key (less secure)
     - With `internal`, even root users can't extract the CA's private key

4. **`common_name="Poddle Root CA"`**:
   - The "CN" field in the certificate
   - This is what browsers/tools will show as the issuer name

5. **`issuer_name="root-2025"`**:
   - Internal Vault identifier for this CA
   - Useful if you have multiple CAs (e.g., for key rotation)
   - You can reference it later as `issuer_ref=root-2025`

6. **`ttl=87600h`**:
   - This CA certificate expires in 10 years
   - After expiration, ALL certificates it signed become untrusted
   - You'd need to generate a new CA and re-issue all certificates

7. **`> ~/poddle-root-ca.crt`**:
   - Saves the certificate to a file
   - Distribute this to clients/browsers that need to trust your internal CA

**What gets created:**
- A self-signed X.509 certificate (acts as the root of trust)
- Private key stored in Vault's encrypted storage (never accessible)
- Certificate saved to `~/poddle-root-ca.crt` for distribution

### Step 4: Configure CA and CRL URLs

```bash
vault write pki/config/urls \
    issuing_certificates="http://vault.poddle.uz:8200/v1/pki/ca" \
    crl_distribution_points="http://vault.poddle.uz:8200/v1/pki/crl"
```

**Why configure these URLs?**

These URLs are **embedded into every certificate** Vault issues. When a client (browser, curl, application) receives a certificate, it can:

1. **Download the CA certificate** via `issuing_certificates`
   - Purpose: Build the complete certificate chain
   - Example: Browser doesn't have your CA installed → downloads it automatically
   - URL returns the public CA certificate (same as in `~/poddle-root-ca.crt`)

2. **Check if certificate is revoked** via `crl_distribution_points`
   - CRL = Certificate Revocation List
   - URL returns a list of certificate serial numbers that have been revoked
   - Example: You compromised a cert → revoke it → clients download CRL and reject it

**Inspect a certificate to see these URLs:**

```bash
# After you get a certificate from Vault
openssl x509 -in certificate.pem -text -noout | grep -A 5 "Authority Information Access"

# Output will show:
# Authority Information Access:
#     CA Issuers - URI:http://vault.poddle.uz:8200/v1/pki/ca
# 
# CRL Distribution Points:
#     Full Name:
#       URI:http://vault.poddle.uz:8200/v1/pki/crl
```

### Step 5: Create PKI Role

```bash
vault write pki/roles/poddle-uz \
    allowed_domains="poddle.uz" \
    allow_subdomains=true \
    allow_bare_domains=true \
    allow_localhost=false \
    allow_wildcard_certificates=true \
    max_ttl="8760h" \
    ttl="720h" \
    key_bits=2048 \
    key_type=rsa
```

**What is a PKI Role?**

A role is a **template** that defines:
- What domains can be certified
- How long certificates can live
- What type of keys to use
- Security restrictions

**Parameter explanations:**

| Parameter | Value | Explanation |
|-----------|-------|-------------|
| `allowed_domains` | `poddle.uz` | Only issue certs for `*.poddle.uz` domains |
| `allow_subdomains` | `true` | Allow `app.poddle.uz`, `api.poddle.uz`, etc. |
| `allow_bare_domains` | `true` | Allow `poddle.uz` itself (not just subdomains) |
| `allow_localhost` | `false` | Disallow `localhost` certificates (security) |
| `allow_wildcard_certificates` | `true` | Allow `*.poddle.uz` wildcards |
| `max_ttl` | `8760h` (1 year) | **Hard limit**: No cert can be issued longer than this |
| `ttl` | `720h` (30 days) | **Default**: If no duration specified, use 30 days |
| `key_bits` | `2048` | RSA key size (2048 is standard, 4096 is more secure) |
| `key_type` | `rsa` | Key algorithm (alternatives: `ec`, `ed25519`) |

**TTL vs Max TTL in detail:**

```
When cert-manager requests a certificate:

Scenario 1: No duration specified
└── Vault issues cert with TTL = 720h (30 days)

Scenario 2: Requests 90 days (2160h)
├── 2160h < max_ttl (8760h)
└── Vault issues cert with TTL = 2160h ✅

Scenario 3: Requests 2 years (17520h)
├── 17520h > max_ttl (8760h)
└── Vault REJECTS the request ❌

Scenario 4: Requests 6 months (4380h)
├── 4380h < max_ttl (8760h)
└── Vault issues cert with TTL = 4380h ✅
```

**Why short default TTL (30 days)?**
- Security: If a certificate is compromised, it expires quickly
- Best practice: Short-lived certificates with automated renewal
- cert-manager handles renewal automatically (no manual work)

### Step 6: Create Policy for cert-manager

```bash
cat > /tmp/cert-manager-policy.hcl <<EOF
# Allow cert-manager to request certificates
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

vault policy write cert-manager /tmp/cert-manager-policy.hcl
```

**What does each path do?**

#### Path 1: `pki/sign/poddle-uz`

**Purpose**: Sign a CSR (Certificate Signing Request)

**Flow:**
```
cert-manager:
1. Generates RSA private key (2048-bit)
2. Creates CSR with CN=app.poddle.uz
3. POST /v1/pki/sign/poddle-uz
   Body: { "csr": "-----BEGIN CERTIFICATE REQUEST-----...", "common_name": "app.poddle.uz" }

Vault:
4. Validates CSR against role constraints:
   - Is "app.poddle.uz" in allowed_domains? ✅
   - Is requested TTL <= max_ttl? ✅
5. Signs CSR with Root CA private key
6. Returns certificate

cert-manager:
7. Receives certificate
8. Combines with private key → Kubernetes Secret
```

**Key point**: The private key **never leaves cert-manager**. Vault only sees the CSR.

#### Path 2: `pki/issue/poddle-uz`

**Purpose**: Generate private key + certificate (all-in-one)

**Flow:**
```
cert-manager:
1. POST /v1/pki/issue/poddle-uz
   Body: { "common_name": "app.poddle.uz", "ttl": "720h" }

Vault:
2. Generates RSA private key
3. Creates CSR internally
4. Signs CSR with Root CA
5. Returns BOTH private key + certificate

cert-manager:
6. Receives private key + certificate
7. Stores both in Kubernetes Secret
```

**Key point**: Vault generates the private key. This is simpler but gives Vault more control.

#### Path 3: `pki/cert/ca`

**Purpose**: Read the CA certificate

**Why needed:**
- cert-manager needs to include the CA cert in Kubernetes Secrets
- Clients need the CA cert to validate the issued certificates
- Used to build the certificate chain: `[leaf cert] → [CA cert]`

**Example usage:**
```bash
curl http://vault.poddle.uz:8200/v1/pki/cert/ca
# Returns the same certificate as in ~/poddle-root-ca.crt
```

#### Why `sign` vs `issue`?

| Method | Who generates private key? | Security | Use case |
|--------|---------------------------|----------|----------|
| **sign** | cert-manager (in K8s) | More secure | Production |
| **issue** | Vault | Less secure (but simpler) | Testing/dev |

**Recommendation**: Use `sign` for production. The private key should stay in Kubernetes and never transit over the network.

### Step 7: Create Token for cert-manager

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

**Understanding the flags:**

1. **`-policy=cert-manager`**:
   - Attach the policy we created in Step 6
   - Token can ONLY do what the policy allows:
     - Sign/issue certificates for `poddle.uz`
     - Read CA certificate
     - Nothing else (can't read secrets, can't admin Vault)

2. **`-period=24h`** (MOST IMPORTANT):
   - Creates a **periodic token** (not a regular token)
   - Regular token (`-ttl=24h`): Expires after 24h, game over ❌
   - Periodic token (`-period=24h`): **Auto-renews** every time it's used ✅
   
   **How periodic tokens work:**
   ```
   Token created at 00:00
   ├── Valid until 24:00 (24h from now)
   │
   cert-manager uses token at 12:00
   ├── Vault automatically renews it
   └── Now valid until 36:00 (24h from last use)
   
   cert-manager uses token at 35:00
   ├── Vault renews again
   └── Now valid until 59:00
   
   If cert-manager DOESN'T use the token for 24h:
   └── Token expires and becomes invalid ❌
   ```
   
   **Key takeaway**: As long as cert-manager keeps requesting certificates, the token never expires.

3. **`-display-name=cert-manager`**:
   - Human-readable name in Vault UI
   - Helps identify which token is used where
   - Shows up in Vault audit logs

4. **`-no-default-policy`**:
   - By default, Vault attaches the "default" policy to all tokens
   - The default policy allows reading your own token info, renewing it, etc.
   - `-no-default-policy` removes this (more restrictive)
   - For service accounts, you usually want this flag

5. **`-format=json`**:
   - Output as JSON instead of table format
   - Makes it easy to parse with `jq`

**Token output explained:**

```json
{
  "auth": {
    "client_token": "hvs.CAESIKqL...",  // This is what you need
    "accessor": "hmac-sha256:...",       // Used for token management
    "policies": ["cert-manager"],
    "token_policies": ["cert-manager"],
    "metadata": null,
    "lease_duration": 86400,             // 24h in seconds
    "renewable": true,                   // Can be renewed
    "entity_id": "",
    "token_type": "service",
    "orphan": false,
    "mfa_requirement": null,
    "num_uses": 0                        // Unlimited uses
  }
}
```

### Step 8: Store Token in Kubernetes

```bash
kubectl create secret generic vault-token \
    --from-literal=token="${CERT_MANAGER_TOKEN}" \
    -n cert-manager
```

**What this creates:**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: vault-token
  namespace: cert-manager
type: Opaque
data:
  token: aHZzLkNBRVNJS3FMTi4uLg==  # Base64 encoded token
```

**How cert-manager uses it:**
- Mounts this secret as an environment variable or file
- Includes the token in every Vault API request: `X-Vault-Token: hvs.CAESI...`
- Vault validates the token and checks its policy permissions

### Step 9: Create ClusterIssuer (Static Token)

```bash
kubectl apply -f - <<EOF
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
EOF
```

**ClusterIssuer vs Issuer:**

| Resource | Scope | Use case |
|----------|-------|----------|
| **Issuer** | Namespace-scoped | Certificates in ONE namespace |
| **ClusterIssuer** | Cluster-wide | Certificates in ANY namespace |

**For your PaaS**: Use ClusterIssuer so all tenant namespaces can request certificates.

**Configuration explained:**

```yaml
spec:
  vault:
    server: http://192.168.31.247:8200  # Vault API endpoint
    path: pki/sign/poddle-uz            # Vault API path (uses "sign" method)
    auth:
      tokenSecretRef:
        name: vault-token    # Secret name in cert-manager namespace
        key: token           # Key within the Secret (data.token)
```

**Verify the issuer:**

```bash
kubectl get clusterissuer vault-token-ci
# NAME              READY   AGE
# vault-token-ci    True    10s

kubectl describe clusterissuer vault-token-ci
# Look for: Status: Ready: True, Message: Vault verified
```

**Common issues:**

| Error | Cause | Solution |
|-------|-------|----------|
| `Vault verified: false` | Token invalid/expired | Regenerate token |
| `Connection refused` | Wrong Vault server URL | Check `http://192.168.31.247:8200` |
| `Permission denied` | Policy doesn't allow `pki/sign` | Fix policy |

---

## Kubernetes Auth with Vault (Recommended)

> **Why this is better**: No static tokens, automatic rotation, follows Kubernetes RBAC patterns.

### The Problem with Static Tokens

```
Static Token Method:
├── You create a token: hvs.CAESI...
├── Token stored in Kubernetes Secret
├── If token expires: cert-manager breaks ❌
├── If token leaked: No way to trace which pod used it ❌
└── Manual rotation required ❌

Kubernetes Auth Method:
├── cert-manager uses its ServiceAccount JWT (auto-rotated by K8s)
├── Vault validates JWT via Kubernetes TokenReview API
├── Vault issues short-lived tokens (24h) automatically ✅
├── Full audit trail (which pod requested what) ✅
└── Zero manual token management ✅
```

### Step 1: Enable Kubernetes Auth

```bash
vault auth enable kubernetes
```

**What this does:**
- Enables a new authentication method at `/auth/kubernetes`
- This method validates Kubernetes ServiceAccount JWT tokens
- Essentially: Vault trusts Kubernetes to identify pods

### Step 2: Create Token Reviewer ServiceAccount

This is the **most critical** and misunderstood part.

```bash
# Create ServiceAccount in kube-system
kubectl create serviceaccount vault-reviewer -n kube-system

# Grant it system:auth-delegator permissions
kubectl create clusterrolebinding vault-reviewer-binding \
    --clusterrole=system:auth-delegator \
    --serviceaccount=kube-system:vault-reviewer
```

**Why do we need this?**

When cert-manager tries to authenticate to Vault:

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  cert-manager   │         │    Vault     │         │  Kubernetes API │
│                 │         │              │         │                 │
└────────┬────────┘         └──────┬───────┘         └────────┬────────┘
         │                         │                          │
         │ 1. Here's my JWT token  │                          │
         │────────────────────────>│                          │
         │                         │                          │
         │                         │ 2. Is this JWT valid?    │
         │                         │  (TokenReview API call)  │
         │                         │─────────────────────────>│
         │                         │                          │
         │                         │ 3. YES, it's valid.      │
         │                         │    SA: cert-manager      │
         │                         │    Namespace: cert-mgr   │
         │                         │<─────────────────────────│
         │                         │                          │
         │ 4. Here's your Vault    │                          │
         │    access token (24h)   │                          │
         │<────────────────────────│                          │
         │                         │                          │
```

**The problem:** Step 2 requires special permissions!

**What is `system:auth-delegator`?**

This is a built-in Kubernetes ClusterRole that grants:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: system:auth-delegator
rules:
- apiGroups: ["authentication.k8s.io"]
  resources: ["tokenreviews"]
  verbs: ["create"]
```

**What is the TokenReview API?**

```bash
# This is what Vault calls:
POST /apis/authentication.k8s.io/v1/tokenreviews
Content-Type: application/json

{
  "apiVersion": "authentication.k8s.io/v1",
  "kind": "TokenReview",
  "spec": {
    "token": "eyJhbGciOiJSUzI1NiIsImtpZCI6Ik..."  // cert-manager's JWT
  }
}

# Kubernetes responds:
{
  "status": {
    "authenticated": true,
    "user": {
      "username": "system:serviceaccount:cert-manager:cert-manager",
      "uid": "a1b2c3d4-...",
      "groups": ["system:serviceaccounts", "system:serviceaccounts:cert-manager"]
    }
  }
}
```

**Why must this SA be in `kube-system`?**

Actually, it **doesn't** have to be! It's just a convention:
- `kube-system` is for cluster-infrastructure components
- Makes it clear this is not an application ServiceAccount
- You could use any namespace

**What if we DON'T create this SA?**

```
Vault tries to call TokenReview API
└── Kubernetes API: "Error: Forbidden (403)"
    └── Vault can't verify ANY tokens
        └── All Kubernetes auth fails ❌
        └── cert-manager can't get certificates ❌
```

### Step 3: Configure Kubernetes Auth

```bash
# Get Kubernetes CA certificate (to verify API server identity)
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)

# Get Kubernetes API server address
K8S_HOST="https://192.168.31.106:6443"

# Create a long-lived token for vault-reviewer SA
REVIEWER_TOKEN=$(kubectl create token vault-reviewer -n kube-system --duration=87600h)

# Configure Vault to talk to Kubernetes
vault write auth/kubernetes/config \
    kubernetes_host="$K8S_HOST" \
    kubernetes_ca_cert="$K8S_CA_CERT" \
    token_reviewer_jwt="$REVIEWER_TOKEN"
```

**Understanding each parameter:**

#### 1. `kubernetes_host`

**What it is:** The HTTPS endpoint of your Kubernetes API server

**Why Vault needs it:**
- To make TokenReview API calls
- To verify ServiceAccount JWTs

**How to find it:**
```bash
kubectl cluster-info
# Kubernetes control plane is running at https://192.168.31.106:6443

# Or from kubeconfig:
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
```

#### 2. `kubernetes_ca_cert`

**What it is:** The Certificate Authority that signed the Kubernetes API server's TLS certificate

**Why Vault needs it:**

```
Vault makes HTTPS call to: https://192.168.31.106:6443
├── Kubernetes API returns its TLS certificate
├── Vault checks: "Is this cert signed by a trusted CA?"
├── Uses kubernetes_ca_cert to validate
└── If invalid: Vault refuses to connect (MITM protection)
```

**Where it comes from:**
```bash
kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}'
# Output: Base64-encoded certificate

# Decode it:
kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d
# Output: 
# -----BEGIN CERTIFICATE-----
# MIIBdzCCAR2gAwIBAgIBADAKBggqhkjOPQQDAjAjMSEwHwYDVQQDDBhrM3Mtc2Vy
# ...
# -----END CERTIFICATE-----
```

**What if you don't provide it?**
- Vault cannot verify the Kubernetes API server's identity
- TLS connection fails
- All Kubernetes auth fails

#### 3. `token_reviewer_jwt`

**What it is:** A JWT token for the `vault-reviewer` ServiceAccount

**Why Vault needs it:**
- To authenticate itself to Kubernetes when calling TokenReview API
- This is Vault's "identity" when talking to Kubernetes

**Important details:**

```bash
# Creating the token
kubectl create token vault-reviewer -n kube-system --duration=87600h
#                   └─ Must be the SA with auth-delegator permissions!
#                                                        └─ 10 years

# Alternative (older Kubernetes versions):
kubectl create token vault-reviewer -n kube-system
# This creates a token with default 1-hour expiration ❌
# After 1 hour, Vault can't verify tokens anymore!
```

**Duration deep dive:**

| Duration | Impact | Recommendation |
|----------|--------|----------------|
| `1h` (default) | Token expires after 1h → All Vault auth breaks | ❌ Don't use |
| `24h` | Must regenerate daily | ❌ Operational burden |
| `8760h` (1 year) | Regenerate annually | ⚠️ Acceptable |
| `87600h` (10 years) | Set and forget | ✅ Recommended |

**Can we use any ServiceAccount's token?**

**NO!** It must be a ServiceAccount with `system:auth-delegator` permissions.

```bash
# If you try using cert-manager's token:
WRONG_TOKEN=$(kubectl create token cert-manager -n cert-manager --duration=87600h)
vault write auth/kubernetes/config token_reviewer_jwt="$WRONG_TOKEN" ...

# When Vault tries to verify tokens:
# Kubernetes API responds: "Error: Forbidden (403)"
# cert-manager ServiceAccount doesn't have TokenReview permission!
```

**What this configuration creates in Vault:**

```bash
vault read auth/kubernetes/config
# Output:
# kubernetes_host                https://192.168.31.106:6443
# kubernetes_ca_cert             -----BEGIN CERTIFICATE-----...
# token_reviewer_jwt_set         true  ← Vault doesn't show the actual token
# disable_iss_validation         false
```

### Step 4: Create Vault Role for cert-manager

```bash
vault write auth/kubernetes/role/cert-manager \
    bound_service_account_names=cert-manager \
    bound_service_account_namespaces=cert-manager \
    policies=cert-manager \
    ttl=24h
```

**What is a Vault role?**

A role defines **who can authenticate** and **what permissions they get**.

**Parameter breakdown:**

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `bound_service_account_names` | `cert-manager` | Only the SA named "cert-manager" can use this role |
| `bound_service_account_namespaces` | `cert-manager` | Only from the "cert-manager" namespace |
| `policies` | `cert-manager` | Grant the "cert-manager" policy (PKI permissions) |
| `ttl` | `24h` | Vault tokens issued via this role expire in 24h |

**How authentication works:**

```
1. cert-manager pod has ServiceAccount: cert-manager
   ├── Kubernetes auto-mounts JWT at /var/run/secrets/kubernetes.io/serviceaccount/token
   └── JWT contains: namespace=cert-manager, sa=cert-manager

2. cert-manager sends JWT to Vault:
   POST /v1/auth/kubernetes/login
   {
     "role": "cert-manager",
     "jwt": "eyJhbGciOiJSUzI1