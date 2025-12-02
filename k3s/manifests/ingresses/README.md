# K3s Monitoring & Ingress Setup

Complete K3s cluster setup with Traefik ingress controller, Prometheus monitoring stack, and Grafana dashboards secured with TLS certificates and basic authentication.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Accessing Services](#accessing-services)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Cleanup](#cleanup)

## Overview

This configuration provides a production-ready monitoring and ingress setup for K3s with the following components:

**Infrastructure:**

- **Traefik** - Kubernetes-native ingress controller with automatic HTTPS
- **Cert-Manager** - Automated certificate management with multiple issuers
- **MetalLB** - Bare-metal load balancer for on-premises clusters

**Monitoring Stack:**

- **Prometheus** - Metrics collection and time-series database
- **Grafana** - Visualization and analytics dashboards
- **Alertmanager** - Alert routing and management
- **Node Exporter** - Hardware and OS metrics
- **Kube State Metrics** - Kubernetes cluster state metrics

**Security:**

- Wildcard TLS certificate for `*.poddle.uz`
- Multiple certificate issuers (Let's Encrypt, Vault, Self-Signed)
- HTTP Basic Authentication for sensitive dashboards
- Automatic HTTPS redirect

## Prerequisites

Ensure you have the following installed and configured:

- **K3s cluster** (v1.24+)
- **kubectl** configured to access your cluster
- **Helm** (v3+)
- **apache2-utils** or **httpd-tools** for generating htpasswd files
- **DNS configuration** with wildcard entry `*.poddle.uz` pointing to your cluster's load balancer IP

### Installed Helm Charts

The following Helm repositories should be configured:

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add cilium https://helm.cilium.io/
helm repo add traefik https://traefik.github.io/charts
helm repo add metallb https://metallb.github.io/metallb
helm repo add jetstack https://charts.jetstack.io
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update
```

## Quick Start

### 1. Create Authentication Secrets

Install htpasswd utility if not already installed:

```bash
# Arch
sudo yay -S apache-tools

# Debian/Ubuntu
sudo apt install apache2-utils

# RHEL/CentOS/Fedora
sudo yum install httpd-tools
```

Generate authentication credentials for each service:

```bash
# Traefik Dashboard
htpasswd -c traefik-auth admin
kubectl create secret generic traefik-dashboard-auth \
  --from-file=users=traefik-auth \
  -n traefik

# Prometheus
htpasswd -c prometheus-auth admin
kubectl create secret generic prometheus-auth \
  --from-file=users=prometheus-auth \
  -n monitoring

# Grafana (optional - Grafana has built-in authentication)
htpasswd -c grafana-auth admin
kubectl create secret generic grafana-auth \
  --from-file=users=grafana-auth \
  -n monitoring

# Clean up local files
rm -f traefik-auth prometheus-auth grafana-auth
```

### 2. Deploy Ingress Resources

Apply all ingress configurations:

```bash
kubectl apply -f traefik-dashboard-ingress.yaml
kubectl apply -f prometheus-ingress.yaml
kubectl apply -f grafana-ingress.yaml
```

### 3. Verify Deployment

Check certificate status:

```bash
kubectl get certificates -A
```

Expected output:

```bash
NAME                             READY   SECRET                      AGE
nginx-certificate                True    nginx-tls-secret            47h
wildcard-poddle-uz-certificate   True    wildcard-poddle-uz-secret   47h
```

Verify ingress resources:

```bash
kubectl get ingress -A
```

## Configuration

### Directory Structure

```bash
.
├── charts/
│   ├── cilium-manifests/
│   ├── metallb-manifests/
│   ├── prometheus-manifests/
│   └── traefik-manifests/
├── example/
│   ├── nginx-certificate.yaml
│   ├── nginx-deployment.yaml
│   ├── nginx-ingress.yaml
│   └── nginx-service.yaml
├── manifests/
│   ├── certificates/
│   ├── cluster-issuers/
│   ├── cluster-roles/
│   ├── issuers/
│   ├── service-accounts/
│   ├── vault/
│   └── vault-secrets-operator.yaml
├── traefik-dashboard-ingress.yaml
├── prometheus-ingress.yaml
├── grafana-ingress.yaml
└── README.md
```

### Available Certificate Issuers

The cluster has multiple ClusterIssuers configured:

| Issuer | Purpose | Use Case |
|--------|---------|----------|
| `vault-k8s-ci` | Vault PKI backend | Internal certificates with Vault |
| `vault-token-ci` | Vault token auth | Alternative Vault authentication |
| `letsencrypt-production-ci` | Let's Encrypt production | Public-facing services |
| `letsencrypt-staging-ci` | Let's Encrypt staging | Testing ACME flow |
| `selfsigned-ci` | Self-signed certificates | Local development |

Current configuration uses `vault-k8s-ci` for Grafana and the wildcard certificate for all services.

### Wildcard Certificate

All services use the wildcard certificate `wildcard-poddle-uz-secret` which covers `*.poddle.uz`:

```bash
kubectl describe certificate wildcard-poddle-uz-certificate
```

To reissue or modify, edit:

```bash
kubectl edit certificate wildcard-poddle-uz-certificate
```

## Accessing Services

### Service Endpoints

| Service | URL | Authentication | Default Credentials |
|---------|-----|----------------|---------------------|
| Traefik Dashboard | <https://traefik.poddle.uz> | Basic Auth | Set during secret creation |
| Prometheus | <https://prometheus.poddle.uz> | Basic Auth | Set during secret creation |
| Grafana | <https://grafana.poddle.uz> | Basic Auth + Built-in | See below |

### Grafana Credentials

Retrieve the Grafana admin password:

```bash
kubectl get secret prometheus-grafana -n monitoring \
  -o jsonpath="{.data.admin-password}" | base64 --decode && echo
```

Default username: `admin`

### Basic Auth Credentials

The basic authentication credentials are the ones you set when creating the htpasswd files. If you followed the quick start with username `admin`, you'll be prompted for the password you entered.

## Security

### TLS/HTTPS Configuration

All ingress resources are configured with:

- Automatic HTTPS via Traefik
- TLS termination using wildcard certificate
- HTTP to HTTPS redirect (configured in Traefik)

### Basic Authentication

Each service has a dedicated Kubernetes Secret for basic auth:

- `traefik-dashboard-auth` (namespace: traefik)
- `prometheus-auth` (namespace: monitoring)
- `grafana-auth` (namespace: monitoring)

### Best Practices

1. **Change default passwords** - Update Grafana admin password after first login
2. **Rotate credentials regularly** - Regenerate htpasswd secrets periodically
3. **Use strong passwords** - Minimum 12 characters with mixed case, numbers, and symbols
4. **Limit access** - Consider network policies to restrict dashboard access to specific IPs
5. **Monitor access logs** - Review Traefik logs for unauthorized access attempts

### Optional: Disable Basic Auth

To access services without basic auth (relying only on built-in authentication):

1. Remove the middleware annotation from the ingress:

   ```yaml
   # traefik.ingress.kubernetes.io/router.middlewares: monitoring-prometheus-auth@kubernetescrd
   ```

2. Apply the updated ingress:

   ```bash
   kubectl apply -f prometheus-ingress.yaml
   ```

## Troubleshooting

### Certificate Issues

Check certificate status and events:

```bash
# View certificate details
kubectl describe certificate wildcard-poddle-uz-certificate

# Check certificate requests
kubectl get certificaterequests -A

# View cert-manager logs
kubectl logs -n cert-manager deploy/cert-manager
```

### Ingress Not Working

Verify ingress configuration:

```bash
# Check ingress resources
kubectl get ingress -A

# Describe specific ingress
kubectl describe ingress grafana -n monitoring

# View Traefik logs
kubectl logs -n traefik deploy/traefik -f
```

### DNS Resolution

Test DNS resolution from your local machine:

```bash
nslookup traefik.poddle.uz
nslookup prometheus.poddle.uz
nslookup grafana.poddle.uz
```

All should resolve to your cluster's load balancer IP.

### Authentication Issues

Verify secrets exist and contain correct data:

```bash
# List secrets
kubectl get secrets -n monitoring
kubectl get secrets -n traefik

# View secret contents (base64 encoded)
kubectl get secret prometheus-auth -n monitoring -o yaml
```

### Service Connectivity

Test if services are accessible within the cluster:

```bash
# Port-forward to test direct service access
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# Access via localhost
curl http://localhost:3000
curl http://localhost:9090
```

### Common Issues

**Problem:** 404 Not Found on Traefik dashboard

**Solution:** Ensure Traefik dashboard is enabled in Traefik configuration:

```bash
kubectl get configmap -n traefik traefik -o yaml
```

Look for `dashboard: true` in the Traefik configuration.

**Problem:** Certificate not ready

**Solution:** Check cert-manager can access the issuer:

```bash
kubectl get clusterissuer vault-k8s-ci -o yaml
kubectl describe certificaterequest -A
```

**Problem:** Basic auth not working

**Solution:** Verify the middleware is correctly referenced:

```bash
kubectl get middleware -n monitoring
kubectl describe middleware prometheus-auth -n monitoring
```

## Cleanup

### Remove Ingress Resources

```bash
kubectl delete -f traefik-dashboard-ingress.yaml
kubectl delete -f prometheus-ingress.yaml
kubectl delete -f grafana-ingress.yaml
```

### Remove Authentication Secrets

```bash
kubectl delete secret traefik-dashboard-auth -n traefik
kubectl delete secret prometheus-auth -n monitoring
kubectl delete secret grafana-auth -n monitoring
```

### Remove Certificates (Optional)

```bash
kubectl delete certificate wildcard-poddle-uz-certificate
kubectl delete certificate nginx-certificate
```

### Complete Teardown

To remove all monitoring and ingress components:

```bash
# Remove Prometheus stack
helm uninstall prometheus -n monitoring

# Remove Traefik
helm uninstall traefik -n traefik

# Remove cert-manager
helm uninstall cert-manager -n cert-manager

# Remove namespaces
kubectl delete namespace monitoring
kubectl delete namespace traefik
kubectl delete namespace cert-manager
```

---

## Additional Resources

- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Cert-Manager Documentation](https://cert-manager.io/docs/)
- [K3s Documentation](https://docs.k3s.io/)

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review Kubernetes events: `kubectl get events -A`
3. Check pod logs: `kubectl logs -n <namespace> <pod-name>`

---

**Last Updated:** December 2024  
**Cluster Version:** K3s v1.28+
