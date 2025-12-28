# KVM/QEMU Virtualization Setup Guide

## Prerequisites

### Verify Kernel KVM Support

#### Check if KVM modules are available

```bash
zgrep CONFIG_KVM /proc/config.gz
```

> [!CAUTION]
> y = Built-in, m = Loadable module

#### Check if modules are loaded

```bash
lsmod | grep kvm
```

> [!CAUTION]
> Should show: kvm_intel or kvm_amd

### Hardware Requirements

#### Check CPU virtualization support

```bash
lscpu | grep Virtualization
```

> [!CAUTION]
> Should show: VT-x (Intel) or AMD-V (AMD)

#### Count virtualization flags

```bash
egrep -c '(vmx|svm)' /proc/cpuinfo
```

> [!CAUTION]
> If > 0, virtualization is supported

**Enable in BIOS/UEFI:**

1. Reboot and enter BIOS (usually `Del`, `F2`, or `F12`)
2. Find and enable:
   - **Intel**: "Intel Virtualization Technology" or "VT-x"
   - **AMD**: "SVM Mode" or "AMD-V"
   - **Optional**: "Intel VT-d" or "AMD IOMMU" (for PCI passthrough)

---

## Installation

```bash
sudo pacman -S qemu-full qemu-img libvirt virt-install virt-manager virt-viewer \
edk2-ovmf swtpm guestfs-tools libosinfo tuned bridge-utils cloud-image-utils dnsmasq
```

**Package Explanations:**

- `qemu-full` - Complete QEMU emulator
- `qemu-img` - aaa
- `libvirt` - VM management API and daemon
- `virt-install` - CLI tool for creating VMs
- `virt-manager` - GUI for managing VMs
- `virt-viewer` - aaa
- `bridge-utils` - Network bridge management
- `cloud-image-utils` - Cloud-init ISO creation
- `edk2-ovmf` - UEFI firmware for VMs
- `swtpm` - aaa
- `guestfs-tools` - Offline VM disk manipulation
- `libosinfo` - aaa
- `tuned` - System performance optimization
- `bridge-utils` - aaa
- `dnsmasq` - Lightweight DNS/DHCP server

### Configure

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

#### Add current user to libvirt group

```bash
sudo usermod -aG libvirt,kvm $USER
```

#### Set system mode as default

```bash
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.bashrc
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.zshrc
source ~/.bashrc
source ~/.zshrc
```

#### Verify KVM

```bash
virsh uri
# Should output: qemu:///system
```

```bash
groups | grep libvirt
# Should show libvirt in your groups
```

```bash
virsh list --all
lsmod | grep kvm
```

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

---

## Network Configuration

### Step 1: Create Bridge Interface using `systemd-networkd`

#### Create bridge device

```bash
sudo tee /etc/systemd/network/10-br0.netdev > /dev/null << 'EOF'
[NetDev]
Name=br0
Kind=bridge
EOF
```

#### Configure bridge network

##### (DHCP)

```bash
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network]
DHCP=yes
EOF
```

##### Static IP

> [!WARNING]
> Don't set Address to `Address=192.168.31.1/24`, because usually 192.168.31.1 reserved in routers
>
###### PC Static IP

```bash
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network]
DHCP=no

# Set your static IP (CIDR notation)
Address=192.168.31.2/24

# Set your Router IP
Gateway=192.168.1.1

# Set DNS (Google/Cloudflare or your local DNS)
DNS=1.1.1.1
DNS=8.8.8.8
DNS=4.4.4.4
DNS=8.8.4.4
EOF
```

###### LAPTOP Static IP

> [!NOTE]
> When you disable `NetworkManager` and `systemd-resolved` just `systemd-networkd` itself uses default DNS even you set PC.
> Also you have many options, setting nameserver statically or letting `systemd-resolved` to handle.

```bash
sudo tee /etc/systemd/network/10-br0.network > /dev/null << 'EOF'
[Match]
Name=br0

[Network]
DHCP=no

# Set your static IP (CIDR notation)
Address=192.168.31.3/24

# Set your Router IP
Gateway=192.168.1.1

# Set DNS (Google/Cloudflare or your local DNS)
DNS=192.168.31.2 # set dns server, in this case we use PC dnsmasq
DNS=1.1.1.1
DNS=8.8.8.8
DNS=4.4.4.4
DNS=8.8.4.4
EOF
```

Option A - Static /etc/resolv.conf

```bash
sudo tee /etc/resolv.conf <<EOF
nameserver 192.168.31.2
EOF
```

Then lock it so nothing overwrites it:

```bash
sudo chattr +i /etc/resolv.conf
```

Option B — proper networkd integration
Use systemd-resolved without stub resolver

```bash
sudo systemctl enable systemd-resolved --now
```

ping vault.poddle.uz
 └─ glibc resolver
     └─ /etc/resolv.conf
         └─ nameserver 127.0.0.53
             └─ systemd-resolved (ON THE LAPTOP)
                 └─ upstream DNS = 192.168.31.2
                     └─ dnsmasq (ON THE PC)
                         └─ authoritative answer: vault.poddle.uz → 192.168.31.2

### Attach Ethernet to bridge
>
> Replace enp2s0 with your corresponding interface

#### PS Attaching

```bash
sudo tee /etc/systemd/network/20-enp2s0.network > /dev/null << 'EOF'
[Match]
Name=enp2s0

[Network]
Bridge=br0
EOF
```

#### LAPTOP Attaching

```bash
sudo tee /etc/systemd/network/20-enp2s0f0.network > /dev/null << 'EOF'
[Match]
Name=enp2s0f0

[Network]
Bridge=br0
EOF
```

#### Restart networking

```bash
sudo systemctl restart systemd-networkd
```

#### Verify Bridge

```bash
ip addr show br0
```

### Step 2: Configure Bridge in Libvirt

#### 1. Create bridge network XML

```bash
cat > /tmp/vmbridge.xml << 'EOF'
<network>
  <name>vmbridge</name>
  <forward mode='bridge'/>
  <bridge name='br0'/>
</network>
EOF
```

#### 2. Define and start the network

```bash
sudo virsh net-define /tmp/vmbridge.xml
sudo virsh net-start vmbridge
sudo virsh net-autostart vmbridge
```

#### 3. Verify

```bash
virsh net-list --all
# Should show vmbridge as 'active' with autostart 'yes'
```

**Expected output:**

```bash
 Name       State    Autostart   Persistent
---------------------------------------------
 default    active   yes         yes
 vmbridge   active   yes         yes
```

#### 4. Cleanup

```bash
rm /tmp/vmbridge.xml
```

---

## DNS Setup (dnsmasq)

**Why dnsmasq?** For local PaaS development, you need custom domains like `*.poddle.uz` or `*.dev.local` to resolve to your VMs. This enables Kubernetes Ingress controllers to route traffic based on hostnames.

### Step 1: Disable Conflicting Services

> [!NOTE]
> Don't disable or stop `systemd-resolved` on the LAPTOP, because even it use own dns it send to PC DNS.

```bash
# Verify what's using port 53
sudo lsof -i :53
```

```bash
# Disable systemd-resolved
sudo systemctl stop systemd-resolved
sudo systemctl disable systemd-resolved
sudo systemctl mask systemd-resolved

# If using systemd-networkd instead of NetworkManager:
sudo systemctl stop NetworkManager
sudo systemctl disable NetworkManager
sudo systemctl mask NetworkManager
```

```bash
# Verify port 53 is free
sudo lsof -i :53  # Should return nothing
```

### Step 2: Configure dnsmasq on PC

#### Edit main configuration

```bash
sudo neovim /etc/dnsmasq.conf
sudo vim /etc/dnsmasq.conf
sudo nano /etc/dnsmasq.conf
```

**Minimal working configuration:**

```conf
# Bind to localhost and bridge
port=53
# listen-address=127.0.0.1 # Don't do that, it only listen to localhost, eventually VM's can't reach to host dns server
listen-address=192.168.31.3
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

or

```bash
sudo tee /etc/systemd/network/20-enp2s0f0.network > /dev/null << 'EOF'
# Bind to localhost and bridge
port=53
# listen-address=127.0.0.1 # Don't do that, it only listen to localhost, eventually VM's can't reach to host dns server
listen-address=192.168.31.3
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
EOF
```

### Step 3: Add Custom Domain Rules

```bash
sudo nvim /etc/dnsmasq.d/local.conf
sudo vim /etc/dnsmasq.d/local.conf
sudo nano /etc/dnsmasq.d/local.conf
```

```conf
# Resolve *.poddle.uz to your k3s-server VM
address=/.poddle.uz/192.168.31.10 # put there traefik load balancer IP
address=/vault.poddle.uz/192.168.31.2
```

### Step 4: Configure System DNS

> [!NOTE]
> This is mandatory for PC, because we need to point to dnsmasq manually

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
```
