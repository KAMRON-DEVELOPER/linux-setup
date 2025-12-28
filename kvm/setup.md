# KVM/QEMU Virtualization Setup Guide

## Prerequisites

### Verify Kernel KVM Support

Check if KVM modules are available:

```bash
zgrep CONFIG_KVM /proc/config.gz
```

**Note:** `y` = Built-in, `m` = Loadable module

Check if modules are loaded:

```bash
lsmod | grep kvm
```

**Expected output:** `kvm_intel` or `kvm_amd`

### Hardware Requirements

Check CPU virtualization support:

```bash
lscpu | grep Virtualization
```

**Expected output:** VT-x (Intel) or AMD-V (AMD)

Count virtualization flags:

```bash
egrep -c '(vmx|svm)' /proc/cpuinfo
```

**Note:** If output > 0, virtualization is supported

#### Enable in BIOS/UEFI

1. Reboot and enter BIOS (usually `Del`, `F2`, or `F12`)
2. Find and enable:
   - **Intel:** "Intel Virtualization Technology" or "VT-x"
   - **AMD:** "SVM Mode" or "AMD-V"
   - **Optional:** "Intel VT-d" or "AMD IOMMU" (for PCI passthrough)

## Installation

```bash
sudo pacman -S qemu-full qemu-img libvirt virt-install virt-manager virt-viewer \
edk2-ovmf swtpm guestfs-tools libosinfo tuned bridge-utils cloud-image-utils dnsmasq
```

**Package Descriptions:**

- `qemu-full` - Complete QEMU emulator
- `qemu-img` - Disk image utility
- `libvirt` - VM management API and daemon
- `virt-install` - CLI tool for creating VMs
- `virt-manager` - GUI for managing VMs
- `virt-viewer` - VM display viewer
- `edk2-ovmf` - UEFI firmware for VMs
- `swtpm` - Software TPM emulator
- `guestfs-tools` - Offline VM disk manipulation
- `libosinfo` - OS information database
- `tuned` - System performance optimization
- `bridge-utils` - Network bridge management
- `cloud-image-utils` - Cloud-init ISO creation
- `dnsmasq` - Lightweight DNS/DHCP server

## Configuration

### Enable Libvirt Daemon

#### Option 1: Modular Daemons (Recommended)

Better resource usage and more granular control:

```bash
# Enable all modular daemons
for drv in qemu interface network nodedev nwfilter secret storage; do
  sudo systemctl enable virt${drv}d.service
  sudo systemctl enable virt${drv}d{,-ro,-admin}.socket
done

# Or minimal setup (sufficient for most users)
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket \
  virtstoraged.socket virtproxyd.socket
```

**What each daemon does:**

- `virtqemud` - Manages QEMU/KVM VMs
- `virtnetworkd` - Virtual networks (NAT, bridge)
- `virtstoraged` - Storage pools and volumes
- `virtproxyd` - Compatibility layer for legacy tools

#### Option 2: Monolithic Daemon

Single daemon, simpler but older approach:

```bash
sudo systemctl enable --now libvirtd.service
```

### Grant User Access

Add current user to required groups:

```bash
sudo usermod -aG libvirt,kvm $USER
```

Set system mode as default:

```bash
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.bashrc
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.zshrc
source ~/.bashrc  
source ~/.zshrc   
```

### Verify Installation

```bash
# Check URI
virsh uri
# Expected: qemu:///system

# Check group membership
groups | grep libvirt
# Expected: libvirt in your groups

# List VMs
virsh list --all

# Verify KVM modules
lsmod | grep kvm
```

### Optimize Host with TuneD

TuneD optimizes system settings for virtualization workloads:

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

**virtual-host profile benefits:**

- Disables transparent hugepages
- Sets CPU governor to performance mode
- Optimizes I/O scheduler for VM disk performance
- Tunes network parameters

## Network Configuration

### Create Bridge Interface

#### Create bridge device

```bash
sudo tee /etc/systemd/network/10-br0.netdev > /dev/null << 'EOF'
[NetDev]
Name=br0
Kind=bridge
EOF
```

#### Configure bridge network

Option A: DHCP

```bash
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network]
DHCP=yes
EOF
```

Option B: Static IP (Desktop)

```bash
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network]
DHCP=no
Address=192.168.31.2/24
Gateway=192.168.31.1
DNS=1.1.1.1
DNS=8.8.8.8
EOF
```

**Note:** Avoid using `.1` as it's typically reserved for routers

Option C: Static IP (Laptop)

```bash
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network]
DHCP=no
Address=192.168.31.3/24
Gateway=192.168.31.1
DNS=192.168.31.2
DNS=1.1.1.1
DNS=8.8.8.8
EOF
```

For laptop DNS configuration, choose one approach:

**Static /etc/resolv.conf:**

```bash
sudo tee /etc/resolv.conf <<EOF
nameserver 192.168.31.2
EOF
sudo chattr +i /etc/resolv.conf
```

**Using systemd-resolved:**

```bash
sudo systemctl enable --now systemd-resolved
```

DNS resolution flow:

```text
Application → glibc resolver → /etc/resolv.conf → 127.0.0.53 
→ systemd-resolved (laptop) → 192.168.31.2 (PC dnsmasq)
```

### Attach Physical Interface to Bridge

Replace interface name with your actual interface (check with `ip link`).

**Desktop:**

```bash
sudo tee /etc/systemd/network/20-enp2s0.network > /dev/null << 'EOF'
[Match]
Name=enp2s0

[Network]
Bridge=br0
EOF
```

**Laptop:**

```bash
sudo tee /etc/systemd/network/20-enp2s0f0.network > /dev/null << 'EOF'
[Match]
Name=enp2s0f0

[Network]
Bridge=br0
EOF
```

Restart networking:

```bash
sudo systemctl restart systemd-networkd
```

Verify bridge:

```bash
ip addr show br0
```

### Configure Libvirt Bridge Network

Create bridge network definition:

```bash
cat > /tmp/vmbridge.xml << 'EOF'
<network>
  <name>vmbridge</name>
  <forward mode='bridge'/>
  <bridge name='br0'/>
</network>
EOF
```

Define and activate:

```bash
sudo virsh net-define /tmp/vmbridge.xml
sudo virsh net-start vmbridge
sudo virsh net-autostart vmbridge
```

Verify:

```bash
virsh net-list --all
```

**Expected output:**

```text
 Name       State    Autostart   Persistent
---------------------------------------------
 default    active   yes         yes
 vmbridge   active   yes         yes
```

Cleanup:

```bash
rm /tmp/vmbridge.xml
```

## DNS Setup with dnsmasq

**Purpose:** Enable custom domain resolution (e.g., `*.poddle.uz`) for local development with Kubernetes Ingress controllers.

### Disable Conflicting Services

**Note:** On laptops using the PC as DNS server, keep `systemd-resolved` running.

Check what's using port 53:

```bash
sudo lsof -i :53
```

On PC only:

```bash
# Disable systemd-resolved
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
sudo systemctl mask systemd-resolved

# If using systemd-networkd instead of NetworkManager
sudo systemctl stop NetworkManager
sudo systemctl disable NetworkManager
sudo systemctl mask NetworkManager
```

Verify port 53 is free:

```bash
sudo lsof -i :53  # Should return nothing
```

### Configure dnsmasq on PC

Edit configuration file:

```bash
sudo nano /etc/dnsmasq.conf
```

Add this configuration:

```conf
# Bind to bridge interface
port=53
listen-address=192.168.31.2
interface=br0

# Don't forward queries for non-routed addresses
domain-needed
bogus-priv

# Don't read /etc/resolv.conf (prevents DNS loop)
no-resolv

# Upstream DNS servers
server=1.1.1.1
server=8.8.8.8
server=4.4.4.4
server=8.8.4.4

# Enable DNS caching
cache-size=1000

# Load additional configs
conf-dir=/etc/dnsmasq.d/,*.conf
```

**Important:** Don't use `listen-address=127.0.0.1` - VMs need to reach the DNS server via the bridge interface.

### Add Custom Domain Rules

```bash
sudo nano /etc/dnsmasq.d/local.conf
```

```conf
# Wildcard domains for local services
address=/.poddle.uz/192.168.31.10
address=/vault.poddle.uz/192.168.31.2
```

### Configure System DNS (PC Only)

Point PC to local dnsmasq:

```bash
# Remove existing resolv.conf
sudo chattr -i /etc/resolv.conf
sudo rm -f /etc/resolv.conf

# Create new resolv.conf
echo "nameserver 127.0.0.1" | sudo tee /etc/resolv.conf

# Make immutable
sudo chattr +i /etc/resolv.conf
```

Verify:

```bash
cat /etc/resolv.conf
lsattr /etc/resolv.conf  # Should show 'i' flag
```

### Start dnsmasq

```bash
sudo systemctl enable --now dnsmasq
sudo systemctl status dnsmasq
```

### Test DNS Resolution

```bash
# Test custom domain
dig vault.poddle.uz

# Test wildcard
dig app.poddle.uz

# Test external domain
dig google.com
```
