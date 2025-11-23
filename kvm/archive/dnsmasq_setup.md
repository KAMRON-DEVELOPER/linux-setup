# Complete dnsmasq Setup Guide for Local PaaS

## Table of Contents

1. [Overview](#overview)
2. [The Problem: DNS Conflicts](#the-problem-dns-conflicts)
3. [Understanding dnsmasq](#understanding-dnsmasq)
4. [Step-by-Step Setup](#step-by-step-setup)
5. [Common Pitfalls & Solutions](#common-pitfalls--solutions)
6. [Testing & Verification](#testing--verification)
7. [Integration with Kubernetes/K3s](#integration-with-kubernetesk3s)

---

## Overview

This guide documents the complete setup of **dnsmasq** as a local DNS server for a PaaS (Platform as a Service) project called **Poddle**. The goal is to resolve custom domains like `*.poddle.uz` to local Kubernetes clusters running in KVM VMs.

### Network Architecture Documentation

                       Internet
                           |
                           v
                     +-----------+
                     |  enp2s0   |   (physical NIC)
                     +-----------+
                           |
                           |
                     +-----------+
                     |   br0     |   (bridge interface)
                     | 192.168.31.197  ← host IP
                     +-----------+
                   /       |        \
                  /        |         \
                 v         v          v
        +--------------+  +--------------+   +----------------+
        |    VM        |  |     VM       |   |      Host      |
        |  k3s-server  |  |  k3s-agent   |   |     itself     |
        +--------------+  +--------------+   +----------------+

DNS flow:
\*.poddle.uz → 192.168.31.207 (resolved by dnsmasq)

### Architecture

```
┌─────────────────┐
│   Your PC       │
│  192.168.31.197 │
│                 │
│  ┌──────────┐   │
│  │ dnsmasq  │   │──┐
│  │ :53      │   │  │
│  └──────────┘   │  │
└─────────────────┘  │
                     │ Bridge Network (br0)
┌─────────────────┐  │
│  k3s-server VM  │◄─┘
│  192.168.31.207 │
│                 │
│  ┌──────────┐   │
│  │ Traefik  │   │
│  │ :80 :443 │   │
│  └──────────┘   │
└─────────────────┘

┌─────────────────┐
│  k3s-agent VM   │
│  192.168.31.146 │
└─────────────────┘
```

**Flow:**

1. Browser requests `myapp.poddle.uz`
2. dnsmasq resolves it to `192.168.31.207`
3. Request goes to Traefik ingress controller
4. Traefik routes to the correct pod based on Host header

---

## The Problem: DNS Conflicts

### Port 53 is Busy!

Multiple services try to use port 53 for DNS:

| Service              | Purpose                               | Conflict                           |
| -------------------- | ------------------------------------- | ---------------------------------- |
| **systemd-resolved** | System DNS resolver (systemd default) | ✅ Uses port 53                    |
| **NetworkManager**   | Network management with built-in DNS  | ✅ Uses port 53 via dnsmasq plugin |
| **dnsmasq**          | Lightweight DNS/DHCP server           | ✅ Needs port 53                   |

**You can only have ONE service listening on port 53!**

### The Solution

For a custom DNS setup with KVM bridge networking:

- ✅ Keep **systemd-networkd** (manages br0 bridge)
- ✅ Keep **dnsmasq** (custom DNS resolver)
- ❌ **Disable NetworkManager** (conflicts and not needed with systemd-networkd)
- ❌ **Disable systemd-resolved** (we're using dnsmasq instead)

---

## Understanding dnsmasq

### What is dnsmasq?

dnsmasq is a lightweight DNS forwarder and DHCP server that:

- Resolves DNS queries
- Caches DNS responses
- Can override DNS for specific domains
- Forwards unknown queries to upstream DNS servers (1.1.1.1, 8.8.8.8)

### Key Concepts

#### 1. Upstream DNS Servers

These are the "real" DNS servers that dnsmasq forwards queries to:

```
Internet Query → dnsmasq → 1.1.1.1 or 8.8.8.8 → Response
```

#### 2. Custom Address Records

Override DNS for specific domains:

```conf
address=/.poddle.uz/192.168.31.207
```

This tells dnsmasq: "For ANY subdomain under `.poddle.uz`, return `192.168.31.207`"

Examples:

- `test.poddle.uz` → 192.168.31.207
- `myapp.poddle.uz` → 192.168.31.207
- `anything.poddle.uz` → 192.168.31.207

#### 3. The DNS Loop Problem

**CRITICAL:** dnsmasq reads `/etc/resolv.conf` to find upstream DNS servers.

❌ **WRONG Setup (Creates Loop):**

```bash
# /etc/resolv.conf
nameserver 127.0.0.1
```

```conf
# /etc/dnsmasq.conf
# (no server= directives)
```

**What happens:**

1. Your system uses 127.0.0.1 for DNS (good)
2. dnsmasq reads `/etc/resolv.conf` and sees `127.0.0.1`
3. dnsmasq says "ignoring nameserver 127.0.0.1 - local interface" (to prevent loop)
4. dnsmasq has **no upstream servers** → DNS fails for non-local domains!

✅ **CORRECT Setup:**

```bash
# /etc/resolv.conf
nameserver 127.0.0.1
```

```conf
# /etc/dnsmasq.conf
no-resolv  # Don't read /etc/resolv.conf
server=1.1.1.1
server=8.8.8.8
```

**What happens:**

1. Your system uses 127.0.0.1 for DNS
2. dnsmasq ignores `/etc/resolv.conf`
3. dnsmasq uses explicitly configured upstream servers
4. Everything works! ✅

---

## Step-by-Step Setup

### Step 1: Disable Conflicting Services

```bash
# Disable NetworkManager (if using systemd-networkd)
sudo systemctl stop NetworkManager
sudo systemctl disable NetworkManager
sudo systemctl mask NetworkManager

# Disable systemd-resolved
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
sudo systemctl mask systemd-resolved
```

**Verify nothing is using port 53:**

```bash
sudo lsof -i :53
# Should return empty
```

### Step 2: Install dnsmasq

```bash
# Arch Linux
sudo pacman -S dnsmasq

# Ubuntu/Debian
sudo apt install dnsmasq
```

### Step 3: Configure dnsmasq

Edit `/etc/dnsmasq.conf`:

```bash
sudo nvim /etc/dnsmasq.conf
```

**Minimal working configuration:**

```conf
# Bind to localhost
port=53
listen-address=127.0.0.1

# Listen on bridge interface (for VMs)
interface=br0

# Don't forward queries for non-routed addresses
domain-needed
bogus-priv

# Don't read /etc/resolv.conf for upstream servers
no-resolv

# Upstream DNS servers (explicitly configured)
server=1.1.1.1
server=8.8.8.8
server=4.4.4.4
server=8.8.4.4

# Enable DNS caching
cache-size=1000

# Load additional config files
conf-dir=/etc/dnsmasq.d
```

### Step 4: Add Custom Domain Rules

Create `/etc/dnsmasq.d/poddle.conf`:

```bash
sudo nvim /etc/dnsmasq.d/poddle.conf
```

```conf
# Resolve *.poddle.uz to k3s-server
address=/.poddle.uz/192.168.31.207
```

### Step 5: Configure /etc/resolv.conf

**Important:** Many services (NetworkManager, systemd-resolved, DHCP clients) try to overwrite `/etc/resolv.conf`. We need to protect it.

```bash
# Remove any existing resolv.conf
sudo chattr -i /etc/resolv.conf  # Remove immutable flag if set
sudo rm -f /etc/resolv.conf

# Create new resolv.conf pointing to dnsmasq
echo "nameserver 127.0.0.1" | sudo tee /etc/resolv.conf

# Make it immutable (prevents other services from overwriting)
sudo chattr +i /etc/resolv.conf
```

**Verify:**

```bash
cat /etc/resolv.conf
# Output: nameserver 127.0.0.1

lsattr /etc/resolv.conf
# Output: ----i---------e----- /etc/resolv.conf
#         ^ This 'i' means immutable
```

### Step 6: Start and Enable dnsmasq

```bash
sudo systemctl enable dnsmasq
sudo systemctl start dnsmasq
```

**Check status:**

```bash
sudo systemctl status dnsmasq
```

**Expected output:**

```
● dnsmasq.service - dnsmasq - A lightweight DHCP and caching DNS server
     Active: active (running)

   using nameserver 1.1.1.1#53
   using nameserver 8.8.8.8#53
```

**❌ BAD:** If you see:

```
   ignoring nameserver 127.0.0.1 - local interface
```

This means you have the DNS loop problem! Go back to Step 3 and add `no-resolv` and explicit `server=` directives.

---

## Common Pitfalls & Solutions

### Problem 1: "ignoring nameserver 127.0.0.1"

**Cause:** dnsmasq is reading `/etc/resolv.conf` which points to itself.

**Solution:**

```conf
# /etc/dnsmasq.conf
no-resolv
server=1.1.1.1
server=8.8.8.8
```

### Problem 2: Custom domains return NXDOMAIN

**Symptoms:**

```bash
dig myapp.poddle.uz
# Returns: NXDOMAIN (domain doesn't exist)
```

**Causes & Solutions:**

**A) dnsmasq config not loaded:**

```bash
# Check if conf-dir is enabled
grep "conf-dir" /etc/dnsmasq.conf
# Should show: conf-dir=/etc/dnsmasq.d

# If not, add it:
echo "conf-dir=/etc/dnsmasq.d" | sudo tee -a /etc/dnsmasq.conf
sudo systemctl restart dnsmasq
```

**B) Wrong interface:**

```bash
# If using bridge networking, listen on bridge interface
# /etc/dnsmasq.conf
interface=br0  # Not enp2s0 if it's enslaved to br0
```

**C) Syntax error in address directive:**

```conf
# Wrong:
address=/poddle.uz/192.168.31.207  # Missing leading dot

# Correct:
address=/.poddle.uz/192.168.31.207  # Dot before domain
```

### Problem 3: Can't resolve internet domains

**Symptoms:**

```bash
dig google.com
# Timeout or fails
```

**Cause:** No upstream DNS servers configured.

**Solution:**

```conf
# /etc/dnsmasq.conf
server=1.1.1.1
server=8.8.8.8
```

### Problem 4: dnsmasq won't start - "Address already in use"

**Cause:** Port 53 is used by another service.

**Solution:**

```bash
# Find what's using port 53
sudo lsof -i :53

# Common culprits:
sudo systemctl stop systemd-resolved
sudo systemctl stop NetworkManager

# Then restart dnsmasq
sudo systemctl restart dnsmasq
```

### Problem 5: /etc/resolv.conf keeps getting overwritten

**Solution:** Make it immutable:

```bash
sudo chattr +i /etc/resolv.conf
```

**To remove immutable flag (when you need to edit):**

```bash
sudo chattr -i /etc/resolv.conf
```

---

## Testing & Verification

### Test 1: Check dnsmasq is Running

```bash
sudo systemctl status dnsmasq
sudo lsof -i :53
# Should show dnsmasq listening on port 53
```

### Test 2: Test Custom Domain Resolution

```bash
dig whatever.poddle.uz

# Expected output:
# ;; ANSWER SECTION:
# whatever.poddle.uz.   0   IN   A   192.168.31.207
#
# ;; Query time: 0 msec
# ;; SERVER: 127.0.0.1#53(127.0.0.1)
```

**Key indicators of success:**

- ✅ Status: `NOERROR` (not NXDOMAIN)
- ✅ Answer section shows your IP
- ✅ Query time: 0 msec (cached/local)
- ✅ SERVER: 127.0.0.1 (using dnsmasq)

### Test 3: Test Internet Domain Resolution

```bash
dig google.com

# Expected:
# ;; ANSWER SECTION:
# google.com.   284   IN   A   <some IP>
#
# ;; SERVER: 127.0.0.1#53(127.0.0.1)
```

### Test 4: Test Multiple Subdomains

```bash
dig app1.poddle.uz
dig app2.poddle.uz
dig test.poddle.uz
# All should return 192.168.31.207
```

### Test 5: Verify with nslookup

```bash
nslookup myapp.poddle.uz
# Server:         127.0.0.1
# Address:        127.0.0.1#53
#
# Name:   myapp.poddle.uz
# Address: 192.168.31.207
```

---

## Integration with Kubernetes/K3s

### Expose Traefik Ingress Controller

K3s comes with Traefik as a LoadBalancer service. Check it:

```bash
kubectl get svc -n kube-system traefik

# Output:
# NAME      TYPE           EXTERNAL-IP       PORT(S)
# traefik   LoadBalancer   192.168.31.207    80:30976/TCP,443:32130/TCP
```

Traefik is automatically exposed on your node IPs (192.168.31.207) on ports 80 and 443!

### Deploy Test Application

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-test
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx-test
  template:
    metadata:
      labels:
        app: nginx-test
    spec:
      containers:
        - name: nginx
          image: nginx:alpine
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: nginx-test
  namespace: default
spec:
  selector:
    app: nginx-test
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-test
  namespace: default
  annotations:
    kubernetes.io/ingress.class: "traefik"
spec:
  rules:
    - host: nginx-test.poddle.uz
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: nginx-test
                port:
                  number: 80
```

### Apply and Test

```bash
kubectl apply -f nginx-test.yaml

# Wait for pod to be ready
kubectl get pods -w

# Check ingress
kubectl get ingress nginx-test

# Test from your browser or CLI
curl http://nginx-test.poddle.uz
# Should show nginx welcome page!
```

### Access from Browser

Just open: `http://nginx-test.poddle.uz`

Your browser will:

1. Query DNS → dnsmasq returns 192.168.31.207
2. Send HTTP request to 192.168.31.207:80
3. Traefik receives it and checks `Host: nginx-test.poddle.uz`
4. Traefik routes to the correct Service/Pod
5. Response flows back

---

## Advanced Configuration

### Enable Query Logging (for debugging)

```conf
# /etc/dnsmasq.conf
log-queries
log-dhcp
```

View logs:

```bash
sudo journalctl -u dnsmasq -f
```

### Add Multiple Custom Domains

```conf
# /etc/dnsmasq.d/custom-domains.conf
address=/.dev.local/192.168.1.100
address=/.test.local/192.168.1.200
address=/.poddle.uz/192.168.31.207
```

### Specific Host Overrides

```conf
# /etc/dnsmasq.d/hosts.conf
address=/api.example.com/10.0.0.5
address=/db.example.com/10.0.0.10
```

### Use /etc/hosts for Static Entries

dnsmasq automatically reads `/etc/hosts`:

```bash
# /etc/hosts
192.168.31.207  k3s-server.local
192.168.31.146  k3s-agent.local
```

Now `dig k3s-server.local` will work!

---

## Troubleshooting Commands

### Check DNS Resolution Chain

```bash
# What nameserver is your system using?
cat /etc/resolv.conf

# Test with specific DNS server
dig google.com @127.0.0.1  # via dnsmasq
dig google.com @1.1.1.1    # direct to Cloudflare

# Check dnsmasq cache
sudo killall -SIGUSR1 dnsmasq  # Dumps cache to syslog
sudo journalctl -u dnsmasq | tail -50
```

### Restart Everything

```bash
# Full reset
sudo systemctl restart dnsmasq
sudo systemctl restart systemd-networkd

# Clear DNS cache in applications
# Chrome: chrome://net-internals/#dns → Clear host cache
# Firefox: about:networking#dns → Clear DNS Cache
```

### Test from VMs

From inside k3s-server VM:

```bash
# Check if Traefik is accessible
curl localhost:80
# Should return: 404 page not found (from Traefik)

# Check specific ingress
curl -H "Host: nginx-test.poddle.uz" localhost:80
# Should return nginx page
```

---

## Security Considerations

### 1. Protect /etc/resolv.conf

Always use immutable flag:

```bash
sudo chattr +i /etc/resolv.conf
```

### 2. Restrict dnsmasq Listening

For production, only listen on localhost and bridge:

```conf
listen-address=127.0.0.1
interface=br0
bind-interfaces  # Only bind to specified interfaces
```

### 3. Enable DNSSEC (Optional)

```conf
# /etc/dnsmasq.conf
conf-file=/usr/share/dnsmasq/trust-anchors.conf
dnssec
dnssec-check-unsigned
```

---

## Quick Reference

### Essential Commands

```bash
# Restart dnsmasq
sudo systemctl restart dnsmasq

# View logs
sudo journalctl -u dnsmasq -f

# Test DNS
dig domain.com
nslookup domain.com

# Check port 53
sudo lsof -i :53

# Edit config
sudo nvim /etc/dnsmasq.conf

# Test config syntax
dnsmasq --test
```

### Key Config Locations

| File                    | Purpose                    |
| ----------------------- | -------------------------- |
| `/etc/dnsmasq.conf`     | Main configuration         |
| `/etc/dnsmasq.d/*.conf` | Additional configs         |
| `/etc/resolv.conf`      | System DNS resolver config |
| `/etc/hosts`            | Static host entries        |

### Config Directives Reference

```conf
# Upstream servers
no-resolv                    # Don't read /etc/resolv.conf
server=1.1.1.1              # Use this upstream server

# Listening
port=53                      # DNS port
listen-address=127.0.0.1    # Listen on this IP
interface=br0                # Listen on this interface

# Custom domains
address=/.poddle.uz/IP      # Wildcard domain override
address=/specific.com/IP     # Specific host override

# Behavior
domain-needed               # Don't forward plain names
bogus-priv                  # Don't forward private IPs
cache-size=1000             # DNS cache size
conf-dir=/etc/dnsmasq.d     # Load additional configs
```

---

## Success Checklist

- [ ] NetworkManager disabled/masked
- [ ] systemd-resolved disabled/masked
- [ ] dnsmasq installed and running
- [ ] `/etc/resolv.conf` contains `nameserver 127.0.0.1`
- [ ] `/etc/resolv.conf` is immutable (`chattr +i`)
- [ ] dnsmasq.conf has `no-resolv` and `server=` directives
- [ ] Custom domain configured in `/etc/dnsmasq.d/`
- [ ] `dig whatever.poddle.uz` returns correct IP
- [ ] `dig google.com` works (internet DNS)
- [ ] Can access app via browser at `http://app.poddle.uz`

---

## Next Steps: HTTPS/TLS

For production, you'll want HTTPS. Options:

### Option 1: cert-manager + Let's Encrypt

Install cert-manager in K3s:

```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
```

Configure Let's Encrypt issuer (requires real domain).

### Option 2: Self-Signed Certificates

For local development:

```bash
# Generate self-signed cert
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout poddle.key -out poddle.crt \
  -subj "/CN=*.poddle.uz"

# Create Kubernetes secret
kubectl create secret tls poddle-tls \
  --cert=poddle.crt --key=poddle.key
```

Update Ingress:

```yaml
spec:
  tls:
    - hosts:
        - nginx-test.poddle.uz
      secretName: poddle-tls
```

### Option 3: Caddy Reverse Proxy

Run Caddy on your host to handle automatic HTTPS for local development.

---

## Conclusion

You now have a fully functional local DNS server with dnsmasq that:

- Resolves custom domains (`*.poddle.uz`) to your K3s cluster
- Forwards internet queries to Cloudflare/Google DNS
- Works seamlessly with KVM bridge networking
- Integrates with Kubernetes Ingress controllers

This setup is perfect for local PaaS development and testing!

**Remember:** The key to success with dnsmasq is understanding the DNS resolution chain and avoiding the loop problem by using `no-resolv` with explicit `server=` directives.

Happy coding! 🚀
