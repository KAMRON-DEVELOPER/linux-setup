# Observability Stack for Poddle PaaS

Complete guide for installing and configuring Grafana Tempo, Loki, and OpenTelemetry Collector.

---

## Prerequisites

- K3s cluster with Traefik, MetalLB, and Prometheus already installed
- `helm` CLI installed
- `kubectl` configured to access your cluster
- Grafana already running (via kube-prometheus-stack)

---

## Installation

### Step 1: Install Grafana Tempo

Create the values file if not already present:

```bash
# File: charts/grafana-manifests/tempo-values.yaml already exists
# Review the configuration:
cat charts/grafana-manifests/tempo-values.yaml
```

Install Tempo:

```bash
helm install tempo grafana/tempo \
  -n monitoring \
  -f charts/grafana-manifests/tempo-values.yaml
```

**Verify:**

```bash
kubectl get pods -n monitoring -l app.kubernetes.io/name=tempo
kubectl logs -n monitoring -l app.kubernetes.io/name=tempo --tail=50
```

---

### Step 2: Install Grafana Loki

The loki-stack chart is deprecated. Use the newer `loki` chart instead:

```bash
helm install loki grafana/loki \
  -n monitoring \
  -f charts/grafana-manifests/loki-stack-values.yaml
```

**Verify:**

```bash
kubectl get pods -n monitoring -l app.kubernetes.io/name=loki
kubectl logs -n monitoring -l app.kubernetes.io/name=loki --tail=50

# Check if Loki is ready
kubectl exec -n monitoring -it deployment/loki -- wget -qO- http://localhost:3100/ready
```

---

### Step 3: Install OpenTelemetry Collector

Install the collector:

```bash
helm install opentelemetry-collector open-telemetry/opentelemetry-collector \
  -n monitoring \
  -f charts/open-telemetry-manifests/opentelemetry-collector-values.yaml
```

**Verify:**

```bash
kubectl get pods -n monitoring -l app.kubernetes.io/name=opentelemetry-collector
kubectl logs -n monitoring -l app.kubernetes.io/name=opentelemetry-collector --tail=50

# Check if OTEL Collector is receiving data
kubectl port-forward -n monitoring svc/opentelemetry-collector 8888:8888
curl http://localhost:8888/metrics
```

---

### Step 4: Apply Traefik IngressRoutes

Update the IngressRoute manifest with your domain:

```bash
# Edit manifests/observability/observability-ingress.yaml
# Replace 'yourdomain.com' with 'poddle.uz'

# Apply the IngressRoutes
kubectl apply -f manifests/observability/observability-ingress.yaml
```

**Verify:**

```bash
kubectl get ingressroute -n monitoring
```

---

### Step 5: Configure Grafana Data Sources

Since Grafana is already installed via kube-prometheus-stack, add the new data sources:

#### Access Grafana

```bash
# Already exposed at: https://grafana.poddle.uz
# Credentials from manifests/ingresses/grafana-ingress.yaml:
# Username: admin
# Password: 1213
```

#### Add Tempo Data Source

1. Navigate to: **Configuration** → **Data Sources** → **Add data source**
2. Select **Tempo**
3. Configure:
   - **Name**: `Tempo`
   - **URL**: `http://tempo.monitoring.svc.cluster.local:3100`
4. Click **Save & Test**

#### Add Loki Data Source

1. Navigate to: **Configuration** → **Data Sources** → **Add data source**
2. Select **Loki**
3. Configure:
   - **Name**: `Loki`
   - **URL**: `http://loki.monitoring.svc.cluster.local:3100`
4. Click **Save & Test**

---

## Configuration Issues Fixed

### Issue 1: OpenTelemetry Collector Configuration

**Problem:** Your config has invalid exporter names.

**Fixed Configuration:**

```yaml
# charts/open-telemetry-manifests/opentelemetry-collector-values.yaml
config:
  exporters:
    # Changed from 'tempo' to 'otlp/tempo'
    otlp/tempo:
      endpoint: tempo.monitoring.svc.cluster.local:4317
      tls:
        insecure: true

    prometheusremotewrite:
      endpoint: http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090/api/v1/write

    loki:
      endpoint: http://loki.monitoring.svc.cluster.local:3100/loki/api/v1/push

  service:
    pipelines:
      traces:
        receivers: [otlp]
        processors: [memory_limiter, k8sattributes, resource, batch]
        exporters: [otlp/tempo, debug]  # Fixed: was 'tempo'
      
      metrics:
        receivers: [otlp, prometheus]
        processors: [memory_limiter, k8sattributes, resource, batch]
        exporters: [prometheusremotewrite]
      
      logs:
        receivers: [otlp]
        processors: [memory_limiter, k8sattributes, resource, batch]
        exporters: [loki, debug]
```

### Issue 2: Missing Prometheus Receiver Config

**Problem:** The prometheus receiver was defined but not configured properly.

**Fixed:** Added it to the receivers section (already in your config, but ensure it's there).

### Issue 3: IngressRoute Service Names

**Problem:** Service names in IngressRoutes may not match actual service names.

**Check actual service names:**

```bash
kubectl get svc -n monitoring | grep -E "tempo|loki|opentelemetry"
```

Update `manifests/observability/observability-ingress.yaml` with correct service names:

- Tempo: `tempo` (check with kubectl)
- Loki: `loki` (check with kubectl)
- OpenTelemetry Collector: `opentelemetry-collector` (check with kubectl)

---

## Local Development Setup

### Port-Forward Services for Local Development

Create a helper script:

```bash
#!/bin/bash
# File: scripts/dev-port-forward.sh

echo "🔌 Starting port-forwards for local development..."

# Kill existing port-forwards
pkill -f "kubectl port-forward" || true
sleep 2

# OpenTelemetry Collector (for sending traces/logs/metrics from host)
kubectl port-forward -n monitoring svc/opentelemetry-collector 4317:4317 4318:4318 > /tmp/otel-pf.log 2>&1 &
echo "✅ OTEL Collector: http://localhost:4317 (gRPC), http://localhost:4318 (HTTP)"

# Grafana (if you want to access locally without domain)
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80 > /tmp/grafana-pf.log 2>&1 &
echo "✅ Grafana: http://localhost:3000"

# Tempo (for debugging)
kubectl port-forward -n monitoring svc/tempo 3100:3100 > /tmp/tempo-pf.log 2>&1 &
echo "✅ Tempo: http://localhost:3100"

# Loki (for debugging)
kubectl port-forward -n monitoring svc/loki 3101:3100 > /tmp/loki-pf.log 2>&1 &
echo "✅ Loki: http://localhost:3101"

sleep 3
echo ""
echo "🎉 Port-forwards ready!"
echo ""
echo "Test connectivity:"
echo "  curl http://localhost:4318/v1/traces"
echo "  curl http://localhost:3100/ready"
echo "  curl http://localhost:3101/ready"
```

Make it executable:

```bash
chmod +x scripts/dev-port-forward.sh
./scripts/dev-port-forward.sh
```

### Environment Variables for Rust Services

Add to your `.env` or export:

```bash
# OpenTelemetry Configuration
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=compute-provisioner
SERVICE_VERSION=0.1.0
ENVIRONMENT=development
RUST_LOG=compute_provisioner=debug,shared=debug,tower_http=debug
```

---

## Debugging & Troubleshooting

### Check Installation Status

```bash
# List all releases in monitoring namespace
helm list -n monitoring

# Check all pods in monitoring namespace
kubectl get pods -n monitoring

# Expected pods:
# - tempo-*
# - loki-*
# - opentelemetry-collector-*
# - prometheus-*
# - grafana-*
```

### Check Service Endpoints

```bash
# List services
kubectl get svc -n monitoring

# Check if services are accessible
kubectl run curl-test --rm -i --tty --image=curlimages/curl -- sh

# Inside the pod:
curl http://tempo.monitoring.svc.cluster.local:3100/ready
curl http://loki.monitoring.svc.cluster.local:3100/ready
curl http://opentelemetry-collector.monitoring.svc.cluster.local:4318/v1/traces
```

### View Logs

```bash
# OTEL Collector logs
kubectl logs -n monitoring -l app.kubernetes.io/name=opentelemetry-collector -f

# Tempo logs
kubectl logs -n monitoring -l app.kubernetes.io/name=tempo -f

# Loki logs
kubectl logs -n monitoring -l app.kubernetes.io/name=loki -f
```

### Test OTEL Collector Ingestion

```bash
# Test sending a trace to OTEL Collector
curl -X POST http://localhost:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [{
          "key": "service.name",
          "value": {"stringValue": "test-service"}
        }]
      },
      "scopeSpans": [{
        "spans": [{
          "traceId": "5B8EFFF798038103D269B633813FC60C",
          "spanId": "EEE19B7EC3C1B174",
          "name": "test-span",
          "startTimeUnixNano": "1544712660000000000",
          "endTimeUnixNano": "1544712661000000000",
          "kind": 1
        }]
      }]
    }]
  }'

# Check OTEL Collector logs for the received trace
kubectl logs -n monitoring -l app.kubernetes.io/name=opentelemetry-collector --tail=20
```

### Check Data in Grafana

1. Go to **Explore**
2. Select **Tempo** data source
3. Run a query: `{service.name="test-service"}`
4. Select **Loki** data source
5. Run a query: `{namespace="monitoring"}`

---

## DNS Configuration for VM Access

Since your Rust services run on the host and need to access the cluster:

### Option 1: Use Port-Forwards (Recommended for Development)

Already covered in the "Local Development Setup" section above.

### Option 2: Add DNS Entries (For Production-like Setup)

Add to your dnsmasq configuration:

```bash
# On your host machine
sudo vim /etc/dnsmasq.conf

# Add these entries (replace with your MetalLB IP for opentelemetry-collector service)
address=/otel.poddle.uz/<METALLB_IP>
address=/tempo.poddle.uz/<METALLB_IP>
address=/loki.poddle.uz/<METALLB_IP>

# Restart dnsmasq
sudo systemctl restart dnsmasq

# Then from host, use:
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel.poddle.uz:4318
```

Get MetalLB IP:

```bash
kubectl get svc -n monitoring opentelemetry-collector -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

---

## Quick Reference

### Installed Components

```bash
# List all components
helm list -n monitoring

# Expected output:
# NAME                   NAMESPACE   CHART
# prometheus             monitoring  kube-prometheus-stack-79.9.0
# tempo                  monitoring  tempo-1.24.1
# loki                   monitoring  loki-6.49.0
# opentelemetry-collector monitoring  opentelemetry-collector-0.141.1
```

### Service URLs

| Service | Internal URL | External URL (via Traefik) |
|---------|-------------|----------------------------|
| Tempo | `http://tempo.monitoring.svc.cluster.local:3100` | `https://tempo.poddle.uz` |
| Loki | `http://loki.monitoring.svc.cluster.local:3100` | `https://loki.poddle.uz` |
| OTEL Collector (gRPC) | `http://opentelemetry-collector.monitoring.svc.cluster.local:4317` | - |
| OTEL Collector (HTTP) | `http://opentelemetry-collector.monitoring.svc.cluster.local:4318` | `https://otel.poddle.uz` |
| Grafana | `http://prometheus-grafana.monitoring.svc.cluster.local:80` | `https://grafana.poddle.uz` |
| Prometheus | `http://prometheus-kube-prometheus-prometheus.monitoring.svc.cluster.local:9090` | - |

### Common Commands

```bash
# Restart a service
kubectl rollout restart deployment/opentelemetry-collector -n monitoring
kubectl rollout restart deployment/tempo -n monitoring
kubectl rollout restart deployment/loki -n monitoring

# Upgrade a helm release
helm upgrade tempo grafana/tempo -n monitoring -f charts/grafana-manifests/tempo-values.yaml

# Uninstall (if needed)
helm uninstall tempo -n monitoring
helm uninstall loki -n monitoring
helm uninstall opentelemetry-collector -n monitoring

# Check PVC usage
kubectl get pvc -n monitoring

# View events
kubectl get events -n monitoring --sort-by='.lastTimestamp'
```

---

## Cleanup

To remove the entire observability stack:

```bash
# Uninstall helm releases
helm uninstall opentelemetry-collector -n monitoring
helm uninstall tempo -n monitoring
helm uninstall loki -n monitoring

# Remove IngressRoutes
kubectl delete -f manifests/observability/observability-ingress.yaml

# Remove PVCs (optional, this deletes data)
kubectl delete pvc -n monitoring -l app.kubernetes.io/name=tempo
kubectl delete pvc -n monitoring -l app.kubernetes.io/name=loki
```

---

## Next Steps

1. **Add Rust observability integration** - Update your Rust services to send telemetry
2. **Create dashboards** - Import or create custom Grafana dashboards
3. **Set up alerts** - Configure Prometheus alerts for your PaaS platform
4. **Configure retention** - Adjust data retention policies for Tempo and Loki
5. **Enable persistence** - Ensure PVCs are backed up if using production data
