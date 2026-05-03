# Local Kubernetes Cluster with HTTPS using K3s and Traefik

This guide shows how to run a local K3s cluster with Traefik ingress and secure HTTPS using self-signed certificates via `mkcert`.

---

## 1. Prerequisites

- Arch Linux host
- KVM/QEMU for VMs
- K3s installed on server node
- `kubectl` installed locally
- `mkcert` installed on host

```bash
sudo pacman -S mkcert
mkcert -install

2. Generate Local Certificates

Create a certificate for your local domain (example: test.poddle.uz):

mkcert test.poddle.uz

This will generate two files:

test.poddle.uz.pem       # Public certificate
test.poddle.uz-key.pem   # Private key

Create a Kubernetes TLS secret in the cluster:

kubectl create secret tls whoami-tls \
  --cert=test.poddle.uz.pem \
  --key=test.poddle.uz-key.pem \
  -n default

3. Deploy Example Service

Create a simple "whoami" deployment:

apiVersion: apps/v1
kind: Deployment
metadata:
  name: whoami
  labels:
    app: whoami
spec:
  replicas: 2
  selector:
    matchLabels:
      app: whoami
  template:
    metadata:
      labels:
        app: whoami
    spec:
      containers:
        - name: whoami
          image: traefik/whoami
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: whoami
spec:
  selector:
    app: whoami
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: whoami-ingress
  annotations:
    kubernetes.io/ingress.class: "traefik"
spec:
  tls:
    - hosts:
        - test.poddle.uz
      secretName: whoami-tls
  rules:
    - host: test.poddle.uz
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: whoami
                port:
                  number: 80

Apply it:

kubectl apply -f whoami.yaml

4. Test HTTPS Access

curl -k https://test.poddle.uz

    -k is required because this is a self-signed certificate. For production, you would use a real domain and ACME (Let's Encrypt) for automatic certificates.

5. Notes

    Your ~/.kube/config on the host can be updated with the server's kubeconfig for local kubectl access:

scp user@k3s-server:/etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config

    Traefik is installed by default with K3s and automatically manages ingress.

    For production HTTPS, make sure your domain is publicly reachable and use --tls-san on K3s install.


```
