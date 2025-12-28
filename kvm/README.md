# KVM/QEMU Virtualization Setup Guide

A complete guide for setting up KVM virtualization with bridge networking, cloud-init automation, and local DNS for running Kubernetes clusters and containerized workloads.

## 📋 Table of Contents

- [Overview](#overview)
- [What You'll Build](#what-youll-build)
- [Prerequisites](#prerequisites)
- [Quick Start (30 Minutes)](#quick-start-30-minutes)
- [Core Concepts](#core-concepts)
- [Installation](#installation)
- [Network Configuration](#network-configuration)
- [DNS Setup (dnsmasq)](#dns-setup-dnsmasq)
- [System Configuration](#system-configuration)
- [VM Management](#vm-management)
- [Automated VM Creation (kvm.py)](#automated-vm-creation-kvmpy)
- [Cloud-Init Workflow](#cloud-init-workflow)
- [Cluster Deployments](#cluster-deployments)
- [Troubleshooting](#troubleshooting)
- [Command Reference](#command-reference)

---

## Overview

This guide covers production-ready KVM setup on Arch Linux (adaptable to other distros) with:

- **Bridge networking** for LAN-accessible VMs
- **Local DNS (dnsmasq)** for custom domain resolution
- **Cloud-init automation** for rapid VM provisioning
- **K3s Kubernetes** and **Docker Swarm** cluster setups
- **Automated tooling** (kvm.py) for streamlined workflows

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Host System                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   dnsmasq    │  │ systemd-     │  │   libvirt    │   │
│  │   :53        │  │ networkd     │  │   (KVM)      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
│         │                  │                  │         │
│         └──────────────────┴──────────────────┘         │
│                            │                            │
│                     ┌─────────────┐                     │
│                     │             │                     │
│                     │  br0 Bridge │                     │
│                     │ 192.168.x.x │                     │
│                     └──────┬──────┘                     │
└────────────────────────────┼────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼────┐         ┌─────▼────┐        ┌─────▼────┐
   │  VM 1    │         │   VM 2   │        │   VM 3    │
   │ k3s-     │         │  k3s-    │        │  Other    │
   │ server   │         │  agent   │        │  Service  │
   │ (Traefik)│         │           │       │           │
   └───────── ┘         └──────────┘        └────────── ┘
        │
        └─ *.poddle.uz → Ingress Controller
```

**DNS Flow:** `app.poddle.uz` → dnsmasq → 192.168.x.x (VM IP) → Traefik → Pod

---

## What You'll Build

After completing this guide, you'll have:

✅ KVM hypervisor with hardware acceleration  
✅ Bridge networking (VMs accessible on your LAN)  
✅ Local DNS server (custom domain resolution like `*.dev.local`)  
✅ Cloud-init automation for rapid VM provisioning  
✅ Automated VM creation script (`kvm.py`)  
✅ Ready-to-deploy K3s or Docker Swarm clusters

---

## Prerequisites

### Hardware Requirements

```bash
# Check CPU virtualization support
lscpu | grep Virtualization
# Should show: VT-x (Intel) or AMD-V (AMD)

# Count virtualization flags
egrep -c '(vmx|svm)' /proc/cpuinfo
# If > 0, virtualization is supported
```

**Enable in BIOS/UEFI:**

1. Reboot and enter BIOS (usually `Del`, `F2`, or `F12`)
2. Find and enable:
   - **Intel**: "Intel Virtualization Technology" or "VT-x"
   - **AMD**: "SVM Mode" or "AMD-V"
   - **Optional**: "Intel VT-d" or "AMD IOMMU" (for PCI passthrough)

### Software Requirements

- Linux kernel with KVM support
- Ethernet connection (bridge networking doesn't work with WiFi)
- At least 8GB RAM (16GB+ recommended for clusters)
- 50GB+ free disk space

---

## Quick Start (30 Minutes)

```bash
# 1. Update system
sudo pacman -Syu  # Arch
# sudo apt update && sudo apt upgrade  # Ubuntu

# 2. Install packages
sudo pacman -S qemu-full qemu-img libvirt virt-manager virt-install \
  virt-viewer bridge-utils dnsmasq cloud-utils edk2-ovmf libosinfo tuned

# 3. Enable libvirt (modular daemons)
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket \
  virtstoraged.socket virtproxyd.socket

# 4. Add user to groups
sudo usermod -aG libvirt,kvm $USER

# 5. Set system mode as default
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.bashrc
source ~/.bashrc

# 6. Reboot to apply all changes
sudo reboot

# After reboot, verify
virsh list --all
lsmod | grep kvm
```

---

## Core Concepts

### QEMU, KVM, and Libvirt

| Component   | Purpose        | Role                                             |
| ----------- | -------------- | ------------------------------------------------ |
| **QEMU**    | Emulator       | Simulates entire computer in software            |
| **KVM**     | Kernel module  | Provides hardware acceleration (uses VT-x/AMD-V) |
| **Libvirt** | Management API | Simplifies VM management (virsh, virt-manager)   |

**Together:** QEMU + KVM = Fast VMs, Libvirt = Easy management

### Network Bridges Explained

#### KVM Bridge (Layer 2 - Our Setup)

```
┌─────────────────────────────────────────┐
│           Physical Network              │
│              (Your LAN)                 │
└───────────┬─────────────────────────────┘
            │
    ┌───────▼────────┐
    │  Router DHCP   │
    │  192.168.x.1   │
    └───────┬────────┘
            │
    ┌───────▼────────┐
    │   br0 Bridge   │  ← Acts like a network switch
    │ (on your host) │
    └───┬────┬───┬───┘
        │    │   │
     Host  VM1  VM2  ← Each gets IP from router
```

**Characteristics:**

- ✅ VMs appear as separate physical devices
- ✅ Accessible from any device on LAN
- ✅ Perfect for servers, clusters, production
- ⚠️ Only works with Ethernet (not WiFi)

#### Docker Bridge (Layer 3 - For Comparison)

```
┌─────────────────┐
│   Host System   │
│  192.168.x.100  │
└─────────┬───────┘
          │
  ┌───────▼────────┐
  │  docker0       │  ← Creates private subnet
  │  172.17.0.1    │     with NAT
  └───┬────┬───┬───┘
      │    │   │
    C1   C2  C3  ← Private IPs (172.17.0.x)
```

**Characteristics:**

- ✅ Simple, no network config needed
- ❌ Containers not directly accessible from LAN
- ❌ Requires port mapping (-p 8080:80)

---

## Installation

### Verify Kernel KVM Support

```bash
# Check if KVM modules are available
zgrep CONFIG_KVM /proc/config.gz
# y = Built-in, m = Loadable module

# Check if modules are loaded
lsmod | grep kvm
# Should show: kvm_intel or kvm_amd
```

### Install Core Packages

<details>
<summary><b>Arch Linux</b></summary>

```bash
sudo pacman -S qemu-full qemu-img libvirt virt-install virt-manager \
  virt-viewer edk2-ovmf dnsmasq swtpm guestfs-tools libosinfo tuned \
  bridge-utils cloud-image-utils
```

</details>

<details>
<summary><b>Ubuntu/Debian</b></summary>

```bash
sudo apt install qemu-kvm libvirt-daemon-system libvirt-clients \
  bridge-utils virt-manager virtinst cloud-image-utils dnsmasq \
  ovmf guestfs-tools libosinfo-bin tuned
```

</details>

<details>
<summary><b>Fedora/RHEL</b></summary>

```bash
sudo dnf install qemu-kvm libvirt virt-install virt-manager bridge-utils \
  cloud-utils dnsmasq edk2-ovmf guestfs-tools libosinfo tuned
```

</details>

**Package Explanations:**

- `qemu-full` - Complete QEMU emulator
- `libvirt` - VM management API and daemon
- `virt-install` - CLI tool for creating VMs
- `virt-manager` - GUI for managing VMs
- `bridge-utils` - Network bridge management
- `cloud-image-utils` - Cloud-init ISO creation
- `edk2-ovmf` - UEFI firmware for VMs
- `dnsmasq` - Lightweight DNS/DHCP server
- `guestfs-tools` - Offline VM disk manipulation
- `tuned` - System performance optimization

---

## Network Configuration

### Step 1: Create Bridge Interface

<details>
<summary><b>Method 1: NetworkManager (nmcli) - Recommended for Desktops</b></summary>

```bash
# 1. Find your Ethernet interface
sudo nmcli device status
# Look for 'ethernet' type (e.g., enp2s0, eth0, eno1)

# 2. Create bridge
sudo nmcli connection add type bridge con-name bridge0 ifname bridge0

# 3. Attach Ethernet to bridge
sudo nmcli connection add type ethernet slave-type bridge \
  con-name 'Bridge connection 1' ifname enp2s0 master bridge0
# Replace 'enp2s0' with your interface name

# 4. Configure auto-connect for slaves
sudo nmcli connection modify bridge0 connection.autoconnect-slaves 1

# 5. Activate bridge
sudo nmcli connection up bridge0

# 6. Verify
sudo nmcli device status
ip addr show bridge0
```

</details>

<details>
<summary><b>Method 2: systemd-networkd - Recommended for Servers</b></summary>

```bash
# 1. Create bridge device
sudo tee /etc/systemd/network/10-br0.netdev > /dev/null << 'EOF'
[NetDev]
Name=br0
Kind=bridge
EOF

# 2. Configure bridge network (DHCP)
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network]
DHCP=yes
EOF

# 2. The bridge configuration to use a Static IP
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network] 
DHCP=no

# Set your static IP (CIDR notation)
Address=192.168.1.30/24

# Set your Router IP
Gateway=192.168.1.1

# Set DNS (Google/Cloudflare or your local DNS)
DNS=8.8.8.8
DNS=1.1.1.1
EOF

# 3. Attach Ethernet to bridge
# Replace enp2s0 with your interface
sudo tee /etc/systemd/network/20-enp2s0.network > /dev/null << 'EOF'
[Match]
Name=enp2s0

[Network]
Bridge=br0
EOF

# 4. Restart networking
sudo systemctl restart systemd-networkd

# 5. Verify
ip addr show br0
```

**For static IP instead of DHCP:**

```ini
[Network]
Address=192.168.1.100/24
Gateway=192.168.1.1
DNS=8.8.8.8
DNS=8.8.4.4
```

</details>

<details>
<summary><b>Method 3: Netplan - Ubuntu Server</b></summary>

```bash
# Edit or create /etc/netplan/01-netcfg.yaml
sudo nano /etc/netplan/01-netcfg.yaml
```

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp2s0: # Your interface name
      dhcp4: false
      dhcp6: false
  bridges:
    br0:
      interfaces: [enp2s0]
      dhcp4: true
      # Or for static IP:
      # addresses: [192.168.1.100/24]
      # gateway4: 192.168.1.1
      # nameservers:
      #   addresses: [8.8.8.8, 8.8.4.4]
```

```bash
# Apply configuration
sudo netplan apply

# Verify
ip addr show br0
```

</details>

### Step 2: Configure Bridge in Libvirt

```bash
# 1. Create bridge network XML
cat > /tmp/vmbridge.xml << 'EOF'
<network>
  <name>vmbridge</name>
  <forward mode='bridge'/>
  <bridge name='br0'/>
</network>
EOF

# 2. Define and start the network
sudo virsh net-define /tmp/vmbridge.xml
sudo virsh net-start vmbridge
sudo virsh net-autostart vmbridge

# 3. Verify
virsh net-list --all
# Should show vmbridge as 'active' with autostart 'yes'

# 4. Cleanup
rm /tmp/vmbridge.xml
```

**Expected output:**

```bash
 Name       State    Autostart   Persistent
---------------------------------------------
 default    active   yes         yes
 vmbridge   active   yes         yes
```

---

## DNS Setup (dnsmasq)

**Why dnsmasq?** For local PaaS development, you need custom domains like `*.poddle.uz` or `*.dev.local` to resolve to your VMs. This enables Kubernetes Ingress controllers to route traffic based on hostnames.

### Understanding the DNS Problem

**The Port 53 Conflict:**

| Service              | Purpose             | Port 53?                       |
| -------------------- | ------------------- | ------------------------------ |
| systemd-resolved     | System DNS resolver | ✅ Uses                        |
| NetworkManager       | Network management  | ✅ Uses (via built-in dnsmasq) |
| dnsmasq (standalone) | Custom DNS server   | ✅ Needs                       |

**Solution:** Only ONE service can use port 53. For our setup:

- ✅ Keep **systemd-networkd** (manages br0 bridge)
- ✅ Keep **dnsmasq** (our custom DNS)
- ❌ Disable **NetworkManager** (if using systemd-networkd)
- ❌ Disable **systemd-resolved** (replaced by dnsmasq)

### Step 1: Disable Conflicting Services

```bash
# Verify what's using port 53
sudo lsof -i :53

# Disable systemd-resolved
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
sudo systemctl mask systemd-resolved

# If using systemd-networkd instead of NetworkManager:
sudo systemctl stop NetworkManager
sudo systemctl disable NetworkManager
sudo systemctl mask NetworkManager

# Verify port 53 is free
sudo lsof -i :53  # Should return nothing
```

### Step 2: Configure dnsmasq

```bash
# Edit main configuration
sudo nano /etc/dnsmasq.conf
```

**Minimal working configuration:**

```conf
# Bind to localhost and bridge
port=53
# listen-address=127.0.0.1 # Don't do that, it only listen to localhost, eventually VM's can't reach to host dns server
listen-address=192.168.31.53
interface=br0

# Don't forward queries for non-routed addresses
domain-needed
bogus-priv

# CRITICAL: Don't read /etc/resolv.conf (prevents DNS loop)
no-resolv

# Explicitly configure upstream DNS servers
server=1.1.1.1
server=8.8.8.8
server=4.4.4.4
server=8.8.4.4

# Enable DNS caching
cache-size=1000

# Load additional configs
conf-dir=/etc/dnsmasq.d/,*.conf
```

### Step 3: Add Custom Domain Rules

```bash
# Create custom domain configuration
sudo nano /etc/dnsmasq.d/local.conf
```

```conf
# Resolve *.poddle.uz to your k3s-server VM
address=/.poddle.uz/192.168.31.207
address=/vault.poddle.uz/192.168.31.53

# Additional domains
address=/.dev.local/192.168.31.207
address=/.test.local/192.168.31.207
```

**Syntax:**

- `address=/.domain.tld/IP` - Wildcard (all subdomains)
- `address=/specific.domain.tld/IP` - Specific host only

### Step 4: Configure System DNS

```bash
# Remove existing resolv.conf (might be symlink)
sudo chattr -i /etc/resolv.conf  # Remove immutable flag if set
sudo rm -f /etc/resolv.conf

# Create new resolv.conf pointing to dnsmasq
echo "nameserver 127.0.0.1" | sudo tee /etc/resolv.conf

# Make it immutable (prevents other services from overwriting)
sudo chattr +i /etc/resolv.conf

# Verify
cat /etc/resolv.conf
lsattr /etc/resolv.conf  # Should show 'i' flag
```

### Step 5: Start dnsmasq

```bash
# Enable and start
sudo systemctl enable dnsmasq
sudo systemctl start dnsmasq

# Check status
sudo systemctl status dnsmasq
```

**✅ Good output:**

```
   using nameserver 1.1.1.1#53
   using nameserver 8.8.8.8#53
```

**❌ Bad output (DNS loop problem):**

```
   ignoring nameserver 127.0.0.1 - local interface
```

If you see this, ensure `no-resolv` is in `/etc/dnsmasq.conf`.

### Step 6: Test DNS Resolution

```bash
# Test custom domain
dig test.poddle.uz

# Expected output:
# ;; ANSWER SECTION:
# test.poddle.uz.   0   IN   A   192.168.31.207
#
# ;; Query time: 0 msec
# ;; SERVER: 127.0.0.1#53(127.0.0.1)

# Test internet domain
dig google.com

# Should resolve correctly via upstream servers
```

---

## System Configuration

### Enable Libvirt Daemon

**Choose between Modular (recommended) or Monolithic daemons:**

#### Option 1: Modular Daemons (Recommended)

Better resource usage, more granular control.

```bash
# Enable all modular daemons
for drv in qemu interface network nodedev nwfilter secret storage; do
  sudo systemctl enable virt${drv}d.service
  sudo systemctl enable virt${drv}d{,-ro,-admin}.socket
done

# Or minimal setup (sufficient for most users):
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket \
  virtstoraged.socket virtproxyd.socket
```

**What each does:**

- `virtqemud` - Manages QEMU/KVM VMs
- `virtnetworkd` - Virtual networks (NAT, bridge)
- `virtstoraged` - Storage pools and volumes
- `virtproxyd` - Compatibility layer (makes tools work)

#### Option 2: Monolithic Daemon
>
> [!INFO]
> Single daemon, simpler but older approach.

```bash
sudo systemctl enable --now libvirtd.service
```

### Grant User Access

```bash
# Add current user to libvirt group
sudo usermod -aG libvirt,kvm $USER

# Set system mode as default
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.bashrc
source ~/.bashrc

# Verify
virsh uri
# Should output: qemu:///system

groups | grep libvirt
# Should show libvirt in your groups
```

**Connection Modes:**

- **Session** (`qemu:///session`): Per-user VMs, no root, limited networking
- **System** (`qemu:///system`): System-wide VMs, full features (recommended)

### Optimize Host with TuneD

TuneD optimizes system settings for virtualization workloads.

```bash
# Enable TuneD
sudo systemctl enable --now tuned.service

# Check current profile
tuned-adm active

# Switch to virtual-host profile
sudo tuned-adm profile virtual-host

# Verify
tuned-adm verify
```

**virtual-host profile optimizations:**

- Disables transparent hugepages
- Sets CPU governor to performance
- Optimizes I/O scheduler for VM disk performance
- Tunes network parameters

### Set Storage ACL Permissions

Grant your user access to VM storage directory.

```bash
# Check current permissions
sudo getfacl /var/lib/libvirt/images/

# Remove existing ACLs
sudo setfacl -R -b /var/lib/libvirt/images/

# Grant read/write/execute to your user
sudo setfacl -R -m "u:${USER}:rwX" /var/lib/libvirt/images/

# Set default ACL for new files/directories
sudo setfacl -m "d:u:${USER}:rwx" /var/lib/libvirt/images/

# Verify
sudo getfacl /var/lib/libvirt/images/
```

### Enable IOMMU (Optional - For PCI Passthrough)

**What is IOMMU?**

- Allows passing physical hardware (GPU, NIC, USB controller) directly to VMs
- Required for GPU passthrough, high-performance networking

**Enable in BIOS:**

1. Reboot and enter BIOS
2. Find and enable:
   - **Intel**: "Intel VT-d"
   - **AMD**: "AMD IOMMU" or "AMD-Vi"

**Configure in GRUB:**

```bash
# Edit GRUB config
sudo nano /etc/default/grub

# Add to GRUB_CMDLINE_LINUX:
# Intel:
GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"

# AMD:
GRUB_CMDLINE_LINUX="amd_iommu=on iommu=pt"

# Regenerate GRUB config
sudo grub-mkconfig -o /boot/grub/grub.cfg

# Reboot
sudo reboot

# Verify after reboot
dmesg | grep -e DMAR -e IOMMU
```

---

## VM Management

### Manual VM Creation

**Basic VM creation with virt-install:**

```bash
virt-install \
  --name my-ubuntu-vm \
  --ram 2048 \
  --vcpus 2 \
  --disk path=/var/lib/libvirt/images/my-ubuntu-vm.qcow2,size=20 \
  --os-variant ubuntu22.04 \
  --network network=vmbridge \
  --graphics none \
  --console pty,target_type=serial \
  --location 'http://archive.ubuntu.com/ubuntu/dists/jammy/main/installer-amd64/' \
  --extra-args 'console=ttyS0,115200n8 serial'
```

**Find OS variants:**

```bash
osinfo-query os | grep -i ubuntu
```

### Essential VM Commands

```bash
# List all VMs
virsh list --all

# Start VM
virsh start vm-name

# Connect to console (Ctrl+] to exit)
virsh console vm-name

# Shutdown gracefully
virsh shutdown vm-name

# Force stop
virsh destroy vm-name

# Delete VM (keeps disk)
virsh undefine vm-name

# Delete VM and all storage
virsh undefine vm-name --remove-all-storage

# Get VM IP
virsh domifaddr vm-name
virsh domifaddr vm-name --source agent  # More reliable
```

---

## Automated VM Creation (kvm.py)

The `kvm.py` script automates the entire VM creation process with cloud-init.

### Features

- ✅ Interactive VM configuration
- ✅ Automatic SSH key generation
- ✅ Cloud-init integration
- ✅ Support for multiple base images (Ubuntu 20.04, 22.04, 24.04)
- ✅ Automatic network configuration
- ✅ Image caching (downloads once, reuses)

### Directory Structure

```bash
~/Documents/kvm/
├── images/           # Base cloud images
├── keys/             # SSH keys (auto-generated)
├── seeds/            # Cloud-init ISOs
├── templates/        # (Optional) Custom cloud-init templates
├── vms/              # VM disk images
└── kvm.py           # The automation script
```

### Usage Example
>
> don't forget to install PyYAML. ```~ ❯ pip install PyYAML```

```bash
cd ~/Documents/kvm
python kvm.py
```

> or add this to ```~/.zshrc```

```bash
# KVM tools
if [[ -d "$HOME/Documents/linux-setup/kvm" ]]; then
  export PATH="$HOME/Documents/linux-setup/kvm:$PATH"
fi
```

**Interactive prompts:**

```
🔥 Select base image:
  1. ubuntu-20.04
  2. ubuntu-22.04
  3. ubuntu-24.04
Enter number: 2

VM name [test-vm]: k3s-server
Hostname [k3s-server]: k3s-server
Username [ubuntu]: kamronbek
Password: ****

🔑 SSH Key Configuration:
  1. Generate new key
  2. Use existing key
  3. Skip SSH key
Choice [1]: 1

Memory (MB) [2048]: 4096
vCPUs [2]: 2
Disk size [20G]: 20G

Network [default]: vmbridge

✅ Create VM? [y/N]: y
```

**Result:**

- VM created and started
- SSH key saved to `keys/k3s-server_id_ed25519`
- Cloud-init configures everything on first boot
- Get IP with: `virsh domifaddr k3s-server --source agent`

### Script Integration

Move `kvm.py` to your repo:

```bash
# From your linux-setup repo root
mkdir -p kvm
cp ~/Documents/kvm/kvm.py kvm/
git add kvm/kvm.py
git commit -m "Add automated VM creation script"
```

**Usage from repo:**

```bash
cd ~/Documents/linux-setup/kvm
python kvm.py
```

---

## Cloud-Init Workflow

Cloud-init automates VM configuration on first boot.

### Directory Structure for Manual Setup

```bash
/var/lib/libvirt/images/
├── templates/
│   └── jammy-server-cloudimg-amd64.img  # Base image
└── k3s/
    ├── k3s-server.qcow2              # VM disk (linked to base)
    ├── k3s-server-seed.iso           # Cloud-init config
    ├── k3s-server-meta-data.yml      # VM identity
    ├── user-data.yml                 # Common config
    └── network-config.yml            # Network settings
```

### Step 1: Download Base Image

```bash
mkdir -p /var/lib/libvirt/images/templates
cd /var/lib/libvirt/images/templates

# Ubuntu 22.04
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

# Ubuntu 24.04
wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
```

### Step 2: Create Cloud-Init Files

**user-data.yml** (common configuration):

```yaml
#cloud-config
preserve_hostname: false
users:
  - name: kamronbek
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh-authorized-keys:
      - ssh-ed25519 AAAAC3NzaC... your-key-here

ssh_pwauth: true
disable_root: false

chpasswd:
  list: |
    kamronbek:yourpassword
  expire: false

package_update: true
package_upgrade: true
packages:
  - curl
  - vim
  - qemu-guest-agent

runcmd:
  - systemctl enable --now qemu-guest-agent

final_message: "VM is ready!"
```

**network-config.yml**:

```yaml
version: 2
ethernets:
  enp1s0:
    dhcp4: true
    dhcp4-overrides:
      route-metric: 100
  eth0:
    dhcp4: true
    dhcp4-overrides:
      route-metric: 200
```

**k3s-server-meta-data.yml**:

```yaml
instance-id: k3s-server-01
local-hostname: k3s-server
```

### Step 3: Generate Cloud-Init ISO

```bash
cd /var/lib/libvirt/images/k3s

cloud-localds --network-config=../network-config.yml \
  k3s-server-seed.iso \
  ../user-data.yml \
  k3s-server-meta-data.yml
```

### Step 4: Create VM Disk

```bash
# Create disk backed by cloud image (saves space)
qemu-img create -f qcow2 -F qcow2 \
  -b /var/lib/libvirt/images/templates/jammy-server-cloudimg-amd64.img \
  /var/lib/libvirt/images/k3s/k3s-server.qcow2 20G
```

**Key parameters:**

- `-f qcow2` - Output format (copy-on-write)
- `-F qcow2` - Backing file format
- `-b <base>` - Backing file (base image)
- `20G` - Virtual size (only grows as needed)

### Step 5: Create VM

```bash
sudo virt-install \
  --name k3s-server \
  --memory 4096 \
  --vcpus 2 \
  --disk path=/var/lib/libvirt/images/k3s/k3s-server.qcow2,format=qcow2,bus=virtio \
  --disk path=/var/lib/libvirt/images/k3s/k3s-server-seed.iso,device=cdrom \
  --os-variant ubuntu22.04 \
  --import \
  --network network=vmbridge,model=virtio \
  --graphics none \
  --noautoconsole
```

### Step 6: Access VM

```bash
# Wait 30-60 seconds for cloud-init to finish

# Get IP address
virsh domifaddr k3s-server --source agent

# SSH into VM
ssh kamronbek@<vm-ip>
# Or with specific key:
ssh -i ~/path/to/key kamronbek@<vm-ip>
```

---

## Cluster Deployments

### K3s Kubernetes Cluster

**Architecture:** 1 master + 2 workers

#### Step 1: Create VMs

```bash
# Use kvm.py to create:
python kvm.py
# Create: k3s-server (4GB RAM, 2 vCPUs)

python kvm.py
# Create: k3s-worker1 (4GB RAM, 2 vCPUs)

python kvm.py
# Create: k3s-worker2 (4GB RAM, 2 vCPUs)
```

#### Step 2: Install K3s on Master

```bash
# SSH into master
ssh kamronbek@<k3s-server-ip>

# Install K3s server
curl -sfL https://get.k3s.io | sh -

# Wait for node to be ready
sudo k3s kubectl get nodes

# Get node token (save this!)
sudo cat /var/lib/rancher/k3s/server/node-token
```

#### Step 3: Join Worker Nodes

```bash
# SSH into worker1
ssh kamronbek@<k3s-worker1-ip>

# Set variables
export K3S_URL="https://<k3s-server-ip>:6443"
export K3S_TOKEN="<token-from-master>"

# Install K3s agent
curl -sfL https://get.k3s.io | K3S_URL=$K3S_URL K3S_TOKEN=$K3S_TOKEN sh -

# Repeat for worker2
```

#### Step 4: Verify Cluster

```bash
# On master
sudo k3s kubectl get nodes

# Expected output:
# NAME          STATUS   ROLES                  AGE
# k3s-server    Ready    control-plane,master   5m
# k3s-worker1   Ready    <none>                 2m
# k3s-worker2   Ready    <none>                 2m
```

#### Step 5: Deploy Test Application

```yaml
# Create nginx-test.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-test
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
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
spec:
  selector:
    app: nginx
  ports:
    - port: 80
      targetPort: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: nginx-test
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

```bash
# Apply
sudo k3s kubectl apply -f nginx-test.yaml

# Check pods
sudo k3s kubectl get pods -w

# Check ingress
sudo k3s kubectl get ingress
```

#### Step 6: Test Application

**From your host (with dnsmasq configured):**

```bash
# Test DNS resolution
dig nginx-test.poddle.uz
# Should return k3s-server IP

# Test HTTP
curl http://nginx-test.poddle.uz
# Should show nginx welcome page

# Open in browser
firefox http://nginx-test.poddle.uz
```

### Docker Swarm Cluster

**Architecture:** 1 manager + 2 workers

#### Step 1: Create VMs

Use `kvm.py` to create 3 VMs:

- swarm-manager (4GB RAM, 2 vCPUs)
- swarm-worker1 (2GB RAM, 1 vCPU)
- swarm-worker2 (2GB RAM, 1 vCPU)

#### Step 2: Install Docker on All Nodes

```bash
# SSH into each VM and run:
sudo apt update
sudo apt install -y docker.io

# Enable Docker
sudo systemctl enable --now docker

# Add user to docker group
sudo usermod -aG docker $USER
```

#### Step 3: Initialize Swarm

```bash
# SSH into manager
ssh kamronbek@<swarm-manager-ip>

# Initialize swarm
docker swarm init --advertise-addr <swarm-manager-ip>

# Copy the join command shown
```

#### Step 4: Join Workers

```bash
# SSH into each worker and run the join command:
docker swarm join --token SWMTKN-xxx <manager-ip>:2377
```

#### Step 5: Verify Swarm

```bash
# On manager
docker node ls

# Expected output:
# ID            HOSTNAME         STATUS  AVAILABILITY  MANAGER STATUS
# xxx *         swarm-manager    Ready   Active        Leader
# yyy           swarm-worker1    Ready   Active
# zzz           swarm-worker2    Ready   Active
```

#### Step 6: Deploy Test Service

```bash
# Create and scale nginx service
docker service create \
  --name web \
  --replicas 3 \
  --publish 8080:80 \
  nginx

# Check service
docker service ls
docker service ps web

# Test
curl http://<any-node-ip>:8080
```

---

## Troubleshooting

### VM Won't Start

```bash
# Check logs
sudo journalctl -u virtqemud -n 50
sudo tail -f /var/log/libvirt/qemu/vm-name.log

# Verify VM XML is valid
virsh dumpxml vm-name | xmllint --format -

# Check disk permissions
ls -l /var/lib/libvirt/images/vm-disk.qcow2
```

### No Network Connectivity

```bash
# Verify bridge is up
ip link show br0
ip addr show br0

# Check VM network interface
virsh domiflist vm-name

# Verify network is active
virsh net-list --all

# Inside VM (via console)
virsh console vm-name
# Then: ip a, sudo dhclient -v
```

### DNS Issues

```bash
# Check dnsmasq is running
sudo systemctl status dnsmasq
sudo lsof -i :53

# Test DNS resolution
dig test.poddle.uz
dig google.com

# Check dnsmasq logs
sudo journalctl -u dnsmasq -f

# Verify resolv.conf
cat /etc/resolv.conf
lsattr /etc/resolv.conf  # Should show 'i' flag
```

### Can't Get VM IP

```bash
# Ensure qemu-guest-agent is installed in VM
virsh console vm-name
# Inside VM:
sudo apt install qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent

# Try different methods to get IP
virsh domifaddr vm-name
virsh domifaddr vm-name --source agent
virsh domifaddr vm-name --source arp

# Check DHCP leases on router
```

### Permission Denied

```bash
# Fix ACL permissions
sudo setfacl -R -m "u:${USER}:rwX" /var/lib/libvirt/images/

# Fix ownership
sudo chown -R libvirt-qemu:kvm /var/lib/libvirt/images/

# Verify group membership
groups | grep libvirt
# If not shown, logout/login or reboot
```

---

## Command Reference

### VM Management

```bash
# Lifecycle
virsh list --all                          # List all VMs
virsh start vm-name                       # Start VM
virsh shutdown vm-name                    # Graceful shutdown
virsh destroy vm-name                     # Force stop
virsh reboot vm-name                      # Reboot
virsh undefine vm-name                    # Delete VM (keep disk)
virsh undefine vm-name --remove-all-storage  # Delete VM + disk

# Information
virsh dominfo vm-name                     # VM details
virsh domifaddr vm-name                   # Get IP
virsh domifaddr vm-name --source agent    # Get IP (more reliable)
virsh domblklist vm-name                  # List disks
virsh domiflist vm-name                   # List network interfaces
virsh dumpxml vm-name                     # Full XML config

# Console
virsh console vm-name                     # Serial console (Ctrl+] to exit)
virt-viewer vm-name                       # Graphical console

# Cloning
virt-clone --original vm --name new-vm --auto-clone
```

### Network Management

```bash
# Networks
virsh net-list --all                      # List networks
virsh net-info network-name               # Network details
virsh net-start network-name              # Start network
virsh net-destroy network-name            # Stop network
virsh net-autostart network-name          # Enable autostart
virsh net-dhcp-leases default             # Show DHCP leases

# Bridge
ip link show br0                          # Show bridge
bridge link show                          # Show bridge ports
brctl show                                # Bridge details (deprecated)
```

### Disk Management

```bash
# Disk images
qemu-img info disk.qcow2                  # Image info
qemu-img create -f qcow2 disk.qcow2 20G   # Create image
qemu-img resize disk.qcow2 +10G           # Resize (offline only)
qemu-img convert -f qcow2 -O raw in.qcow2 out.raw  # Convert format

# Snapshots
virsh snapshot-create-as vm snap1 "Description"
virsh snapshot-list vm-name
virsh snapshot-revert vm-name snap1
virsh snapshot-delete vm-name snap1
```

### DNS (dnsmasq)

```bash
# Service
sudo systemctl restart dnsmasq
sudo systemctl status dnsmasq
sudo journalctl -u dnsmasq -f             # Live logs

# Testing
dig domain.tld                            # Test resolution
nslookup domain.tld                       # Alternative test
sudo lsof -i :53                          # Check port 53

# Configuration
sudo nano /etc/dnsmasq.conf               # Main config
sudo nano /etc/dnsmasq.d/custom.conf      # Additional rules
dnsmasq --test                            # Test config syntax
```

### Monitoring

```bash
# Resource usage
virt-top                                  # Top-like for VMs
virsh domstats vm-name                    # VM stats

# System
lscpu | grep Virtualization               # Check virtualization
lsmod | grep kvm                          # KVM modules loaded
egrep -c '(vmx|svm)' /proc/cpuinfo        # CPU features
```

---

## Best Practices

### Security

- Use SSH keys instead of passwords
- Keep VMs updated: `sudo apt update && sudo apt upgrade`
- Implement firewall rules on VMs
- Use separate storage for sensitive data
- Bridge networking only on trusted networks

### Performance

- Allocate appropriate CPU/RAM (don't over-provision)
- Use virtio drivers (disk and network)
- Place VM disks on SSD/NVMe storage
- Use qcow2 with preallocation for production
- Enable CPU host-passthrough if possible

### Backup

- Take snapshots before major changes
- Backup VM disk images and XML configs
- Test restore procedures periodically
- Consider external backup tools (Borg, Restic)

### Monitoring

- Monitor host resources (CPU, RAM, disk)
- Set up alerts for thresholds
- Use `virt-top` for real-time monitoring
- Log VM console output for debugging

---

## Additional Resources

- [Arch Wiki - KVM](https://wiki.archlinux.org/title/KVM)
- [Arch Wiki - Libvirt](https://wiki.archlinux.org/title/Libvirt)
- [K3s Documentation](https://docs.k3s.io/)
- [Docker Swarm Documentation](https://docs.docker.com/engine/swarm/)
- [Cloud-Init Documentation](https://cloudinit.readthedocs.io/)
- [Libvirt Networking Guide](https://wiki.libvirt.org/page/Networking)

---

## Repository Structure

```
linux-setup/
├── README.md                    # This file
├── kvm/
│   ├── kvm.py                  # Automated VM creation script
│   ├── examples/
│   │   ├── user-data.yml       # Sample cloud-init user data
│   │   ├── network-config.yml  # Sample network config
│   │   ├── meta-data.yml       # Sample meta data
│   │   └── vmbridge.xml        # Libvirt bridge network definition
│   └── example files/          # Additional examples
└── dotfiles/                   # Your dotfiles
```

---

**Version:** 1.0  
**Last Updated:** 2024-11-23  
**Maintained by:** kamronbek
