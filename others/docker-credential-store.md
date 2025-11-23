# Docker Credential Storage with GPG and Pass

## Why We Do This

### The Problem
By default, Docker stores authentication tokens in **plain text** in `~/.docker/config.json`. This is a security risk because:
- Anyone with file access can steal your Docker Hub credentials
- Malware can easily read your tokens
- If you accidentally commit this file to git, your credentials are exposed

### The Solution
We use **pass** (the standard Unix password manager) combined with **GPG encryption** to store Docker credentials securely:
1. **GPG** encrypts your credentials with your private key
2. **pass** manages the encrypted passwords in `~/.password-store/`
3. **docker-credential-pass** acts as a bridge between Docker and pass

When you try to push to Docker Hub, you'll be prompted for your GPG passphrase to decrypt the credentials - this is much more secure than storing tokens in plain text.

---

## Setup Steps

### 1. Generate a GPG Key
```bash
gpg --full-generate-key
```

**Settings:**
- Key type: `1` (RSA and RSA)
- Key size: `4096` bits
- Expiration: `0` (does not expire) or set as needed
- Real name, email, and comment as prompted

### 2. Find Your GPG Key ID
```bash
gpg --list-secret-keys --keyid-format LONG
```

Look for the line starting with `sec`. The key ID is after the `/`:
```
sec   rsa4096/F0CF6767CDB76281 2025-11-23 [SC]
                ^^^^^^^^^^^^^^^^
                This is your KEY_ID
```

### 3. Initialize Pass with Your GPG Key
```bash
pass init YOUR_KEY_ID
```

Example:
```bash
pass init F0CF6767CDB76281
```

This creates `~/.password-store/` where encrypted passwords will be stored.

### 4. Install Docker Credential Helper
```bash
yay -S docker-credential-pass
```

### 5. Configure Docker to Use Pass
Edit `~/.docker/config.json`:
```bash
nvim ~/.docker/config.json
```

Add or modify the `credsStore` field:
```json
{
  "auths": {
    "https://index.docker.io/v1/": {}
  },
  "credsStore": "pass"
}
```

### 6. Login to Docker
```bash
docker login
```

Your credentials will now be encrypted and stored in `~/.password-store/docker-credential-helpers/`.

---

## How It Works

```
┌─────────────┐
│ docker push │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│ docker-credential-pass  │ ◄─── Bridge between Docker and pass
└──────┬──────────────────┘
       │
       ▼
┌─────────────┐
│    pass     │ ◄─── Password manager
└──────┬──────┘
       │
       ▼
┌─────────────┐
│     GPG     │ ◄─── Asks for passphrase, decrypts credentials
└─────────────┘
```

1. When you run `docker push`, Docker needs your credentials
2. Docker asks `docker-credential-pass` for the credentials
3. `docker-credential-pass` asks `pass` to retrieve them
4. `pass` uses GPG to decrypt the credentials
5. GPG prompts you for your passphrase (this is the prompt you see)
6. After you enter the passphrase, credentials are decrypted and used

---

## What Gets Stored Where

### Before (Insecure)
`~/.docker/config.json`:
```json
{
  "auths": {
    "https://index.docker.io/v1/": {
      "auth": "dXNlcm5hbWU6cGFzc3dvcmQ="  ← Your token in base64 (not encrypted!)
    }
  }
}
```

### After (Secure)
`~/.docker/config.json`:
```json
{
  "auths": {
    "https://index.docker.io/v1/": {}  ← No credentials here!
  },
  "credsStore": "pass"  ← Points to pass
}
```

Actual credentials are in:
```
~/.password-store/docker-credential-helpers/aHR0cHM6Ly9pbmRleC5kb2NrZXIuaW8vdjEv.gpg
                                            ↑
                                            Encrypted with GPG
```

---

## Troubleshooting

### If Docker doesn't prompt for passphrase
Your GPG agent might be caching the passphrase. Clear it with:
```bash
echo RELOADAGENT | gpg-connect-agent
```

### If you get "gpg: decryption failed: No secret key"
Reinitialize pass:
```bash
pass init $(gpg --list-secret-keys --keyid-format LONG | grep sec | awk '{print $2}' | cut -d'/' -f2)
```

### To test pass manually
```bash
# Store a test password
pass insert test/mypassword

# Retrieve it (will prompt for GPG passphrase)
pass test/mypassword
```

---

## Security Benefits

✅ Credentials encrypted with strong GPG key  
✅ Passphrase required to access credentials  
✅ Can't accidentally leak tokens in config files  
✅ Works system-wide (not just Docker - pass can store anything)  
✅ Can use different passphrases for different keys  

---

## Notes

- The GPG passphrase prompt you see is a **security feature**, not a bug
- You can configure `gpg-agent` to cache the passphrase for a period of time
- This same setup works for other tools (git, npm, etc.) that support credential helpers
- Your previous Arch installation probably had this configured, which is why Docker "just worked"