# KVM/QEMU Virtualization Setup Guide

## Prerequisites

### Verify Kernel KVM Support

#### Check if KVM modules are available

```bash
zgrep CONFIG_KVM /proc/config.gz
```

> [!INFO]
> y = Built-in, m = Loadable module

#### Check if modules are loaded

```bash
lsmod | grep kvm
```

> [!INFO]
> Should show: kvm_intel or kvm_amd

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

---

## Installation

```bash
sudo pacman -S qemu-full qemu-img libvirt virt-install virt-manager virt-viewer \
edk2-ovmf swtpm guestfs-tools libosinfo tuned bridge-utils cloud-image-utils
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

### Configure

#### Enable libvirt (modular daemons)

```bash
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket \
  virtstoraged.socket virtproxyd.socket
```

#### Add user to groups

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

#### verify

```bash
virsh list --all
lsmod | grep kvm
```

---

## Network Configuration

### Create Bridge Interface using `systemd-networkd`

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
DNS=8.8.8.8
DNS=1.1.1.1
EOF
```

###### LAPTOP Static IP

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
DNS=8.8.8.8
DNS=1.1.1.1
EOF
```

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

#### Verify

```bash
ip addr show br0
```
