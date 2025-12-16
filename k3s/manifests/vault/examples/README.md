# Vault Static Secret Examples

This directory contains examples for using HashiCorp Vault with Kubernetes to manage secrets.

## Prerequisites

- Vault server running and accessible
- Vault Secrets Operator installed in your Kubernetes cluster
- `kubectl` configured to access your cluster
- `vault` CLI installed and configured

## Setup Steps

### 1. Create Namespace

```bash
kubectl create ns user-n2232kn234jk34335
```

### 2. Configure Vault Connection

Apply the VaultConnection resource to configure how to connect to your Vault instance:

```bash
kubectl apply -f vault-connection.yaml
```

Verify the connection:

```bash
kubectl get vaultconnection -n user-n2232kn234jk34335
```

### 3. Configure Vault Authentication

Apply the VaultAuth resource to set up Kubernetes authentication:

```bash
kubectl apply -f vault-auth.yaml
```

Verify the auth configuration:

```bash
kubectl get vaultauth -n user-n2232kn234jk34335
```

### 4. Store Secrets in Vault

Create secrets in Vault that will be synced to Kubernetes:

```bash
vault kv put kvv2/user-n2232kn234jk34335/deployments/ae72517d-4a1b-463a-ac04-a18daed67a9a \
  REDIS_USERNAME="default" \
  REDIS_PASSWORD="password"
```

Verify the secret was stored:

```bash
vault kv get kvv2/user-n2232kn234jk34335/deployments/ae72517d-4a1b-463a-ac04-a18daed67a9a
```

### 5. Create VaultStaticSecret

Apply the VaultStaticSecret resource to sync the Vault secret to Kubernetes:

```bash
kubectl apply -f vault-static-secret.yaml
```

## Testing

### Check VaultStaticSecret Status

```bash
kubectl get vaultstaticsecret -n user-n2232kn234jk34335
```

### Verify Kubernetes Secret Creation

Check that the secret was created:

```bash
kubectl get secret redis-secrets -n user-n2232kn234jk34335
```

### View Secret Data

Decode and view the secret values:

```bash
# View REDIS_PASSWORD
kubectl get secret redis-secrets -n user-n2232kn234jk34335 \
  -o jsonpath='{.data.REDIS_PASSWORD}' | base64 -d

# View REDIS_USERNAME
kubectl get secret redis-secrets -n user-n2232kn234jk34335 \
  -o jsonpath='{.data.REDIS_USERNAME}' | base64 -d

# View all secret data in JSON format
kubectl get secret redis-secrets -n user-n2232kn234jk34335 \
  -o json | jq -r '.data | map_values(@base64d)'
```

## Testing Secret Updates

### Update Secret in Vault

Modify the secret in Vault:

```bash
vault kv patch kvv2/user-n2232kn234jk34335/deployments/ae72517d-4a1b-463a-ac04-a18daed67a9a \
  REDIS_PASSWORD=newpassword
```

### Check Secret Version

View metadata to confirm the update:

```bash
vault kv metadata get kvv2/user-n2232kn234jk34335/deployments/ae72517d-4a1b-463a-ac04-a18daed67a9a
```

### Watch Secret Sync

Monitor the Kubernetes secret to see when it updates (refreshAfter is set to 10s):

```bash
watch -n 1 '
kubectl get secret redis-secrets \
  -n user-n2232kn234jk34335 \
  -o jsonpath="{.data.REDIS_PASSWORD}" 2>/dev/null | base64 -d
'
```

The secret should update within 10 seconds due to the `refreshAfter: 10s` setting in the VaultStaticSecret spec.

## Troubleshooting

### Check VaultStaticSecret Events

```bash
kubectl describe vaultstaticsecret vault-static-secret -n user-n2232kn234jk34335
```

### Check Vault Secrets Operator Logs

```bash
kubectl logs -n vault-secrets-operator-system -l app.kubernetes.io/name=vault-secrets-operator
```

### Verify Service Account Permissions

Ensure the default service account has the correct role binding:

```bash
kubectl get serviceaccount default -n user-n2232kn234jk34335
```

## Cleanup

Remove all resources:

```bash
kubectl delete -f vault-static-secret.yaml
kubectl delete -f vault-auth.yaml
kubectl delete -f vault-connection.yaml
kubectl delete ns user-n2232kn234jk34335
```

Delete secrets from Vault:

```bash
vault kv metadata delete kvv2/user-n2232kn234jk34335/deployments/ae72517d-4a1b-463a-ac04-a18daed67a9a
```

## Notes

- The `refreshAfter: 10s` setting means secrets are synced every 10 seconds
- The `_raw` field in the Kubernetes secret contains the full Vault response metadata
- Secrets are stored in the `kvv2` mount which is KV version 2
- The tenant-role must be configured in Vault with appropriate policies
