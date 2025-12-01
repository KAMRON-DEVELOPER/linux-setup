# What is K8S_CA_CERT?

## 📜 Certificate Authority (CA) Certificate

**What it is**: The root certificate that signed your Kubernetes API server's TLS certificate.

**Why Vault needs it**: When Vault talks to the Kubernetes API server to verify JWT tokens, it needs to trust the API server's SSL certificate.

```
┌─────────────┐                           ┌──────────────────┐
│   Vault     │ "Is JWT valid?"           │  Kubernetes API  │
│             │──────────────────────────>│  (HTTPS)         │
│             │  (over HTTPS/TLS)         │  192.168.31.106  │
│             │                           └──────────────────┘
│             │                                     │
│  Needs to   │                                     │
│  verify:    │                                     │
│  Is this    │                          Signed by: │
│  really K8s?│<────────────────────────────────────┘
│             │         K8S_CA_CERT
└─────────────┘         (Root certificate)
```

**Without CA cert**: Vault would get SSL errors when trying to talk to Kubernetes API.

**Where it comes from**:
- K3s automatically generates this CA when you install K3s
- It's stored in your kubeconfig (`~/.kube/config`)
- This specific CA is ONLY for your Kubernetes cluster

**The command extracts it**:
```bash
K8S_CA_CERT=$(kubectl config view --raw --minify --flatten \
    -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)
```

This gets the CA certificate from your kubeconfig and decodes it from base64.

## 🔐 TLS Trust Chain

```
Root CA (K8s CA)
    │
    ├── Signs K8s API Server Certificate
    │      (192.168.31.106:6443)
    │
    └── Vault uses this CA to verify
        the API server's identity
```

## Why does Vault need this?

When Vault calls the Kubernetes TokenReview API:

```
1. Vault → "Hey K8s API, verify this JWT"
2. K8s API → Sends response over HTTPS
3. Vault → "Wait, how do I know you're really the K8s API?"
4. K8s API → "Here's my certificate signed by the K8s CA"
5. Vault → "Let me check... yes, K8S_CA_CERT signed this. I trust you!"
```

**This is standard TLS/SSL trust verification**, just like your browser verifies websites.