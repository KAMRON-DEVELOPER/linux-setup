# Vault KV setup with Kubernetes auth method

## Tenant setup

### This is the "Dynamic" policy. It uses the {{identity...}} template to lock the user into their own namespace

```bash
vault policy write tenant-policy tenant-policy.hcl
```

### Write role for tenant

> Vault secret policies to roles because it enforces least privilege, ensuring applications and users only access the > specific secrets and paths they need, rather than having broad access. Roles act as logical groupings for identities > (like apps or users), and policies define what actions (read, write, list) they can perform on specific secret paths > (e.g., kv/data/myapp/*), creating fine-grained authorization for secure, efficient secrets management.

```bash
vault write auth/kubernetes/role/tenant-role \
    bound_service_account_names=default \
    bound_service_account_namespaces="user-*" \
    policies=tenant-policy \
    ttl=24h
```

## Admin setup

```bash
vault policy write admin-policy admin-policy.hcl
```

### Write role for admin

```bash
vault write auth/kubernetes/role/compute-provisioner \
    bound_service_account_names=compute-provisioner \
    bound_service_account_namespaces=poddle-system \
    policies=admin-policy \
    ttl=24h
```
