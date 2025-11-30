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

## add repos

`helm repo add traefik https://traefik.github.io/charts`

### cilium

`helm install cilium cilium/cilium \
  --namespace kube-system \
  --set k8sServiceHost=192.168.31.106 \
  --set k8sServicePort=6443 \
  --set ipam.mode=kubernetes \
  --set kubeProxyReplacement=true`

### metallb

#### "In MetalLB v0.13+, configuration is done via Custom Resources (CRs) rather than a single ConfigMap

. When using Helm, you typically define these CRs in a separate YAML file and apply it to the cluster after the MetalLB Helm chart is deployed, or you can pass the configuration directly via the charts.metallb-full.configuration parameter in a values file."

#### You can "<https://metallb.io/configuration/>" or "<https://metallb.io/apis/>", for examples "<https://github.com/metallb/metallb/tree/v0.15.2/configsamples>"(version amy be differ), for usage "<https://metallb.io/usage/>"

Load Balancer test

To test te correct operation of the load balancer we are going to deploy Nginx

#### Create deploy

kubectl create deploy nginx --image=nginx

#### Expose the deploy as a LoadBalancer type

kubectl expose deploy nginx --port=80 --target-port=80 --type=LoadBalancer

#### Verify

kubectl get svc nginx
NAME    TYPE           CLUSTER-IP     EXTERNAL-IP     PORT(S)        AGE
nginx   LoadBalancer   10.43.60.115   192.168.52.30   80:32676/TCP   5h19m

#### Use the curl command we can see the successful response

`curl 192.168.52.30:80`

#### Cleanup

### traefik

### You can "<https://github.com/traefik/traefik-helm-chart/blob/master/EXAMPLES.md>"

`helm install traefik traefik/traefik --namespace traefik --create-namespace`

### kube-prometheus-stack

`helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.storageSpec.volumeClaimTemplate.spec.resources.requests.storage=10Gi \
  --set grafana.adminPassword=admin`

### cert-manager

#### We use self signed certificates for local development by using Vault as a PKI(Private Key Infrastructure) and letsencrypt for staging and production

#### note: "The first thing you'll need to configure after you've installed cert-manager is an Issuer or a ClusterIssuer. These are resources that represent certificate authorities (CAs) able to sign certificates in response to certificate signing requests."

`helm repo add jetstack https://charts.jetstack.io --force-update`

#### # Install the cert-manager helm chart

`helm install \
  cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.19.1 \
  --set crds.enabled=true`

#######################

On Arch, the Debian/Ubuntu path /usr/local/share/ca-certificates/ does not exist.
Arch uses the p11-kit / trust store layout instead.

#######################

vault read -field=certificate pki/cert/ca > ~/poddle-root-ca.crt

#######################

What is certutil?

certutil (from NSS(Network Security Services) tools) manages certificate databases used by Firefox/Thunderbird.
certutil

A Mozilla NSS (Network Security Services) tool for managing certificate databases. Firefox uses NSS to store certificates, not the system certificate store.

Key operations:

    -A = Add certificate
    -D = Delete certificate
    -L = List certificates
    -n = Nickname (human-readable name)
    -d = Database directory
    -i = Input file
    -t = Trust flags

Old Firefox used dbm: format, modern uses sql:.
-t "C,C,C" Trust Flags

Three comma-separated flags for different certificate uses:

    First C = SSL/TLS (websites)
    Second C = Email (S/MIME)
    Third C = Code signing

Trust levels:

    C = Trusted CA (can issue certificates)
    T = Trusted peer (trust this specific cert)
    P = Trusted peer (do not trust as CA)
    p = Valid peer
    , = No trust

C,C,C means: "Trust this as a Certificate Authority for SSL, email, and code signing."

Firefox does not read /etc/ssl/certs.
It uses NSS DB, stored inside your Firefox profile.

You use certutil to:

import CA certificates,

remove certificates,

view trust flags.

What is: "sql:$FIREFOX_PROFILE"?

NSS (Network Security Services) supports two DB formats:

dbm: (legacy)

sql: (modern SQLite-based)

sql:$FIREFOX_PROFILE means:

Use the SQLite certificate database inside the Firefox profile at path $FIREFOX_PROFILE.

What is: -t "C,C,C" (SSL trust flags)?

Flags define how Firefox should trust a CA:

Flag Meaning
C Trusted for issuing SSL server certificates
C Trusted for issuing email certificates
C Trusted for issuing code-signing certificates

Why Firefox Shows:

"connection verified by a certificate issuer that is not recognized by mozilla"
Because:
You are your own CA.
Firefox does not trust it by default.
You imported your Root CA into Firefox manually.
But Mozilla’s CA Program does not include your CA, therefore it displays this message.
Browser logic:
Certificate chain is valid.
But root is not in Mozilla trust store.
Therefore browser shows "not recognized by Mozilla" warning.
This is normal for private PKI such as Vault.

Why You Got SEC_ERROR_UNKNOWN_ISSUER

This error means:
Firefox cannot build a trusted certificate chain from the server’s certificate to a trusted root.

You fixed the CA trust part manually, but Firefox still warns because:
Self-managed CA root ≠ Mozilla-trusted root.

To eliminate the warning:
Import the Root CA as trusted into Firefox and OS trust store.

#######################

Why You Got SEC_ERROR_UNKNOWN_ISSUER
The Certificate Chain of Trust

HTTPS security relies on a chain of trust:

Root CA (in browser's trust store)
    ↓ signs
Intermediate CA (optional)
    ↓ signs
Server Certificate (nginx.poddle.uz)

Your situation:

    Vault generated "Poddle Root CA" (self-signed root certificate)
    Vault signed a certificate for nginx.poddle.uz
    Traefik presented this certificate to your browser
    Browser checked: "Who signed this certificate?"
    Browser looked in its trust store: "I don't know 'Poddle Root CA'"
    Result: SEC_ERROR_UNKNOWN_ISSUER

Why it worked after running certutil: You manually added "Poddle Root CA" to Firefox's trust store with C,C,C flags, telling Firefox: "Trust this CA to sign certificates."

#######################

 How HTTPS/TLS Actually Works (Deep Dive)
The TLS Handshake (Simplified)

Client (Browser)                    Server (nginx.poddle.uz)
      |                                      |
      |-------- ClientHello ---------------->|
      |  (Supported ciphers, TLS versions)   |
      |                                      |
      |<------- ServerHello -----------------|
      |  (Chosen cipher, TLS version)        |
      |                                      |
      |<------- Certificate -----------------|
      |  (Server's public key + signature)   |
      |                                      |
      | [Verify certificate chain]           |
      | [Check: Is it signed by trusted CA?] |
      | [Check: Does domain match?]          |
      | [Check: Is it expired?]              |
      |                                      |
      |-------- ClientKeyExchange ---------->|
      |  (Pre-master secret, encrypted with  |
      |   server's public key)               |
      |                                      |
      | [Both derive session keys]           |
      |                                      |
      |<------- Finished --------------------|
      |-------- Finished ------------------->|
      |                                      |
      | [Encrypted communication begins]     |

Step-by-Step Breakdown

1. ClientHello

Browser says: "I support TLS 1.3, TLS 1.2, and these cipher suites: AES-GCM, ChaCha20..."
2. ServerHello + Certificate

Server responds:

    "Let's use TLS 1.3 with AES-256-GCM"
    "Here's my certificate chain":

    Certificate for nginx.poddle.uz
      Issued by: Poddle Root CA
      Public Key: [RSA 2048-bit key]
      Signature: [Signed by Poddle Root CA's private key]

3. Certificate Verification (Critical!)

Browser performs these checks:

a) Chain of Trust:

nginx.poddle.uz cert
  ↓ Signed by?
Poddle Root CA
  ↓ Is this CA trusted?
Check browser's trust store...
  ↓ NOT FOUND!
❌ SEC_ERROR_UNKNOWN_ISSUER

b) Domain Validation:

    Certificate says: "Valid for *.poddle.uz"
    Browser requested: "nginx.poddle.uz"
    ✅ Match!

c) Expiration:

    Not before: 2025-01-01
    Not after: 2025-04-01
    Current date: 2025-01-15
    ✅ Valid!

d) Revocation Check (optional):

    Check CRL (Certificate Revocation List) at http://vault.poddle.uz:8200/v1/pki/crl
    Or use OCSP (Online Certificate Status Protocol)

4. Key Exchange (Why Asymmetric → Symmetric)

Problem: Asymmetric encryption (RSA, ECDSA) is 100-1000x slower than symmetric encryption (AES).

Solution: Use asymmetric encryption ONLY to exchange a shared secret, then switch to symmetric.

Process:

1. Browser generates random "pre-master secret"
2. Browser encrypts it with server's PUBLIC key (from certificate)
3. Server decrypts it with its PRIVATE key
4. Both derive the same "master secret" using:
   - Pre-master secret
   - Client random (from ClientHello)
   - Server random (from ServerHello)
5. Master secret → Session keys (for AES encryption)

Modern TLS 1.3 uses Diffie-Hellman instead:

    Both sides contribute to key generation
    Even if someone records the traffic and later steals the server's private key, they can't decrypt past sessions (Perfect Forward Secrecy)

5. Encrypted Communication

All HTTP traffic is now encrypted with AES (symmetric):

GET /index.html HTTP/1.1
Host: nginx.poddle.uz

Becomes:

[Encrypted blob: a8f3d9e2c1b4...]

#######################

How Traefik Fits In
Traefik's Role as Reverse Proxy

Browser                 Traefik                 nginx Pod
   |                       |                        |
   |-- HTTPS request ----->|                        |
   |   (TLS handshake)     |                        |
   |<-- Certificate -------|                        |
   |   (from Secret)       |                        |
   |                       |                        |
   |== Encrypted tunnel ===|                        |
   |                       |                        |
   |                       |--- HTTP request ------>|
   |                       |   (plain text)         |
   |                       |<-- HTTP response ------|
   |                       |                        |
   |<== Encrypted data =====|                        |

What Traefik does:

    Reads TLS certificate from Kubernetes Secret (wildcard-poddle-tls)
    Terminates TLS (decrypts HTTPS → HTTP)
    Forwards plain HTTP to backend pod
    Encrypts response and sends back to browser

The Secret contains:

apiVersion: v1
kind: Secret
metadata:
  name: wildcard-poddle-tls
type: kubernetes.io/tls
data:
  tls.crt: [Base64-encoded certificate]
  tls.key: [Base64-encoded private key]

How cert-manager populates this Secret:

    cert-manager sees Certificate resource
    Generates private key
    Creates CSR (Certificate Signing Request)
    Sends CSR to Vault (via ClusterIssuer)
    Vault signs CSR with "Poddle Root CA"
    cert-manager stores certificate + key in Secret
    Traefik reads Secret and uses it for TLS

#######################

Why Vault Needs Initialization
Vault's Security Model

Vault starts "sealed":

Vault Storage (encrypted)
    ↓
Master Key (splits into 5 shares via Shamir's Secret Sharing)
    ↓
Unseal Keys (need 3 out of 5 to reconstruct master key)
    ↓
Root Token (full access to Vault)

Initialization (vault operator init):

    Generates master encryption key
    Splits master key into 5 unseal keys (configurable)
    Encrypts all data with master key
    Gives you unseal keys + root token
    You must save these! Vault doesn't store them.

Why this design?

    Security: No single person can unseal Vault (need 3 out of 5 keys)
    Disaster recovery: If 2 keys are lost, you can still unseal
    Separation of duties: Different people hold different keys

Unsealing (vault operator unseal):

Vault starts sealed → Can't read any data
    ↓
Enter unseal key 1 → Progress: 1/3
    ↓
Enter unseal key 2 → Progress: 2/3
    ↓
Enter unseal key 3 → Vault unsealed! ✅

#######################

Vault PKI Commands Explained
vault secrets enable pki

Enables the PKI secrets engine at path /pki.

What PKI engine does:

    Acts as a Certificate Authority
    Generates root/intermediate CAs
    Signs certificate requests
    Manages certificate lifecycle

vault secrets tune -max-lease-ttl=87600h pki

Sets maximum TTL (Time To Live) for certificates to 10 years.

Why tune?

    Default max TTL is often 30 days
    Root CAs should live longer (years)
    Leaf certificates (for servers) should be shorter (days/months)

vault write -field=certificate pki/root/generate/internal

Breaking it down:

vault write = Write data to Vault (like HTTP POST)

-field=certificate = Only output the certificate field (not the full JSON response)

pki/root/generate/internal = API path

    pki = PKI secrets engine
    root = Root CA operations
    generate = Generate new CA
    internal = Keep private key inside Vault (never export it)

Alternative: generate/exported

    Exports private key
    Dangerous! If private key leaks, entire PKI is compromised

What happens:

1. Vault generates RSA 2048-bit key pair
2. Creates self-signed root certificate:
   Subject: CN=Poddle Root CA
   Issuer: CN=Poddle Root CA (self-signed!)
   Valid: 10 years
3. Stores private key in Vault (encrypted)
4. Returns certificate (public part)

Output saved to ~/poddle-root-ca.crt:

-----BEGIN CERTIFICATE-----
MIIDXTCCAkWgAwIBAgIUF3...
-----END CERTIFICATE-----

This is what you import into Firefox!
vault write pki/roles/poddle-uz

Creates a "role" = template for issuing certificates.

Key parameters:

allowed_domains="poddle.uz"

    Only issue certs for *.poddle.uz or poddle.uz
    Prevents issuing certs for google.com (security!)

allow_subdomains=true

    Can issue nginx.poddle.uz, api.poddle.uz, etc.

max_ttl="8760h"

    Certificates expire after 1 year max
    Forces rotation (security best practice)

key_bits=2048 + key_type=rsa

    Generate 2048-bit RSA keys
    Modern standard (3072-bit or ECDSA P-256 is better)

require_cn=false

    Don't require Common Name (CN) field
    Modern certs use Subject Alternative Names (SAN) instead

#######################
Production Best Practices

1. Use Intermediate CA

Don't sign certificates directly with root CA:

Root CA (offline, air-gapped)
  ↓ signs
Intermediate CA (in Vault)
  ↓ signs
Server certificates

Why?

    If intermediate CA is compromised, revoke it (root CA still safe)
    Root CA private key never touches network

2. Short Certificate Lifetimes

duration: 2160h       # 90 days
renewBefore: 720h     # Renew 30 days before expiry

Why?

    Limits damage if certificate is compromised
    Forces automation (can't manually renew every 90 days)

3. Use Kubernetes Auth Instead of Tokens

auth:
  kubernetes:
    role: cert-manager
    mountPath: /v1/auth/kubernetes

Why?

    Tokens can be stolen
    Kubernetes auth uses ServiceAccount tokens (auto-rotated)
    Vault verifies token with Kubernetes API

4. Monitor Certificate Expiry

kubectl get certificates -A

Use Prometheus + Alertmanager to alert before expiry.
5. Separate Vault Policies

Don't use root token in production:

path "pki/sign/poddle-uz" {
  capabilities = ["create", "update"]
}

# No read/delete/list capabilities

#######################

#######################
