# Clean Up Everything

```# Delete all certificates
kubectl delete certificate --all -n default

# Delete certificate requests (if any remain)

kubectl delete certificaterequest --all -n default

# Delete secrets containing certificates

kubectl delete secret nginx-tls-cert -n default 2>/dev/null || true
kubectl delete secret nginx-tls-secret -n default 2>/dev/null || true
kubectl delete secret wildcard-poddle-uz-secret -n default 2>/dev/null || true

# Delete nginx deployment, service, and ingress

kubectl delete deployment nginx-deployment -n default 2>/dev/null || true
kubectl delete deployment nginx -n default 2>/dev/null || true
kubectl delete service nginx-service -n default 2>/dev/null || true
kubectl delete service nginx -n default 2>/dev/null || true
kubectl delete ingress nginx-ingress -n default 2>/dev/null || true

# Verify everything is clean

echo "=== Checking cleanup ==="
kubectl get certificate -n default
kubectl get certificaterequest -n default
kubectl get deployment -n default
kubectl get service -n default
kubectl get ingress -n default
kubectl get secrets -n default | grep tls```
