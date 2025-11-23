# Complete KVM/QEMU Virtualization Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Quick Start Guide](#quick-start-guide)
3. [Understanding Core Concepts](#understanding-core-concepts)
4. [Prerequisites & Verification](#prerequisites--verification)
5. [Installation](#installation)
6. [System Configuration](#system-configuration)
7. [Network Setup](#network-setup)
8. [VM Management](#vm-management)
9. [K3s Cluster Setup](#k3s-cluster-setup)
10. [Docker Swarm Setup](#docker-swarm-setup)
11. [Useful Commands Reference](#useful-commands-reference)

---

## Introduction

This guide covers complete setup of KVM (Kernel-based Virtual Machine) virtualization on Arch Linux, including bridge networking for LAN-accessible VMs, and deploying production-ready Kubernetes (K3s) and Docker Swarm clusters.

**What you'll learn:**
- Set up KVM with optimal performance
- Configure bridge networking for VMs on your LAN
- Deploy a 3-node K3s Kubernetes cluster
- Deploy a 3-node Docker Swarm cluster
- Manage VMs efficiently with libvirt tools

---

## Quick Start Guide

### 30-Minute Setup Path

```bash
# 1. Verify CPU virtualization support
lscpu | grep Virtualization

# 2. Install core packages
sudo pacman -S qemu-full libvirt virt-manager virt-install bridge-utils

# 3. Enable libvirt (modular daemons - recommended)
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket virtstoraged.socket virtproxyd.socket

# 4. Add your user to libvirt group
sudo usermod -aG libvirt $USER

# 5. Set default connection to system mode
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.bashrc

# 6. Reboot to apply changes
sudo reboot

# 7. After reboot, verify installation
virsh list --all
```

**That's it!** You now have a working KVM setup. Continue reading for network bridge setup and cluster deployments.

---

## Understanding Core Concepts

### What is QEMU, KVM, and Libvirt?

**QEMU (Quick Emulator)**
- Software emulator that can simulate entire computer systems
- Emulates CPU, memory, storage, and peripherals
- Can run without hardware acceleration (but slower)

**KVM (Kernel-based Virtual Machine)**
- Linux kernel module that provides hardware virtualization
- Uses CPU extensions (Intel VT-x or AMD-V) for near-native performance
- QEMU + KVM = Fast virtualization

**Libvirt**
- Management toolkit and API for virtualization
- Provides tools like `virsh` (CLI) and `virt-manager` (GUI)
- Simplifies VM creation and management instead of complex QEMU commands

### Network Bridge Concepts

**KVM Bridge (Layer 2 - Data Link)**
- Operates at OSI Layer 2 (MAC addresses)
- Acts like a physical network switch
- VMs appear as separate devices on your LAN
- Each VM gets its own IP from your router's DHCP
- Example: `br0` bridge

**Docker Bridge (Layer 3 - Network)**
- Operates at OSI Layer 3 (IP addresses)
- Creates private subnet (e.g., 172.17.0.0/16)
- Uses NAT to route traffic
- Containers need port mapping (-p) to be accessed from LAN
- Example: `docker0` bridge

---

## Prerequisites & Verification

### Check CPU Virtualization Support

```bash
# Method 1: Check for virtualization flags
lscpu | grep Virtualization
# Expected output: "Virtualization: VT-x" (Intel) or "Virtualization: AMD-V" (AMD)

# Method 2: Count virtualization flags
egrep -c '(vmx|svm)' /proc/cpuinfo
# If output > 0, virtualization is supported
# vmx = Intel VT-x
# svm = AMD-V
```

### Enable Virtualization in BIOS/UEFI

1. Reboot your system and enter BIOS/UEFI (usually Del, F2, or F12)
2. Look for settings:
   - **Intel**: "Intel Virtualization Technology" or "VT-x"
   - **AMD**: "SVM Mode" or "AMD-V"
3. Enable the option and save changes

### Verify Kernel KVM Support

```bash
# Check if KVM modules are available in kernel
zgrep CONFIG_KVM /proc/config.gz
# Output meanings:
# y = Built-in (always available)
# m = Loadable module (needs to be loaded)
```

---

## Installation

### Update System

```bash
# Always update before installing new packages
sudo pacman -Syu
```

### Install Core Packages

```bash
# Complete installation with all necessary tools
sudo pacman -S qemu-full qemu-img libvirt virt-install virt-manager virt-viewer \
  edk2-ovmf dnsmasq swtpm guestfs-tools libosinfo tuned bridge-utils
```

**Package Explanations:**
- `qemu-full` - Complete QEMU emulator with all architectures
- `qemu-img` - Tool for creating and managing disk images
- `libvirt` - Virtualization management API and daemon
- `virt-install` - CLI tool to create VMs
- `virt-manager` - GUI application for managing VMs
- `virt-viewer` - GUI console to connect to running VMs
- `edk2-ovmf` - UEFI firmware for VMs (needed for modern OSes)
- `dnsmasq` - Lightweight DNS/DHCP server for VM networks
- `swtpm` - Software TPM emulator (for Windows 11, BitLocker, etc.)
- `guestfs-tools` - Tools for accessing and modifying VM disks offline
- `libosinfo` - Database of OS information for optimal VM settings
- `tuned` - System performance tuning daemon
- `bridge-utils` - Tools for managing network bridges

### Verify KVM Installation

```bash
# Check if KVM modules are loaded
lsmod | grep kvm
# Expected output: kvm_intel (Intel) or kvm_amd (AMD)
```

If no output, load the module manually:
```bash
# For Intel
sudo modprobe kvm_intel

# For AMD
sudo modprobe kvm_amd
```

---

## System Configuration

### Enable Nested Virtualization (Optional)

Nested virtualization allows VMs to run their own VMs (useful for testing hypervisors).

**Temporary (current session only):**
```bash
# Intel
sudo modprobe -r kvm_intel  # Remove module
sudo modprobe kvm_intel nested=1  # Reload with nested enabled

# AMD
sudo modprobe -r kvm_amd
sudo modprobe kvm_amd nested=1
```

**Persistent (survives reboots):**
```bash
# Intel
echo "options kvm_intel nested=1" | sudo tee /etc/modprobe.d/kvm-intel.conf

# AMD
echo "options kvm_amd nested=1" | sudo tee /etc/modprobe.d/kvm-amd.conf

# Reboot to apply
sudo reboot
```

### Enable IOMMU (For PCI Passthrough)

**What is IOMMU?**
- Input/Output Memory Management Unit
- Allows passing physical hardware (GPU, NIC, USB controller) directly to VMs
- Required for GPU passthrough, high-performance networking

**Enable in BIOS/UEFI:**
1. Reboot and enter BIOS
2. Find and enable:
   - **Intel**: "Intel VT-d"
   - **AMD**: "AMD IOMMU" or "AMD-Vi"

**Configure in GRUB:**
```bash
# Edit GRUB configuration
sudo nvim /etc/default/grub

# Add to GRUB_CMDLINE_LINUX (inside the quotes):
# Intel:
GRUB_CMDLINE_LINUX="intel_iommu=on iommu=pt"

# AMD:
GRUB_CMDLINE_LINUX="amd_iommu=on iommu=pt"

# The 'iommu=pt' parameter enables passthrough mode for better performance

# Regenerate GRUB configuration
sudo grub-mkconfig -o /boot/grub/grub.cfg

# Reboot
sudo reboot
```

**Verify IOMMU is enabled:**
```bash
dmesg | grep -e DMAR -e IOMMU
# Should show IOMMU initialization messages
```

### Enable Libvirt Daemon

**Choose between Modular or Monolithic daemons:**

**Option 1: Modular Daemons (Recommended - Modern Approach)**

Modular daemons split functionality into separate services for better resource usage.

```bash
# Enable all modular daemons
for drv in qemu interface network nodedev nwfilter secret storage; do
  sudo systemctl enable virt${drv}d.service
  sudo systemctl enable virt${drv}d{,-ro,-admin}.socket
done
```

**Minimal modular setup (sufficient for most users):**
```bash
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket \
  virtstoraged.socket virtproxyd.socket
```

**What each daemon does:**
- `virtqemud` - Manages QEMU/KVM virtual machines
- `virtnetworkd` - Handles virtual networks (NAT, bridge, DNS/DHCP)
- `virtstoraged` - Manages storage pools and volumes
- `virtproxyd` - Compatibility layer (makes tools think it's old libvirtd)

**Option 2: Monolithic Daemon (Traditional)**

Single daemon handles everything (older approach, but simpler).

```bash
sudo systemctl enable --now libvirtd.service
```

### Optimize Host with TuneD

TuneD automatically optimizes system settings for virtualization workloads.

```bash
# 1. Enable TuneD daemon
sudo systemctl enable --now tuned.service

# 2. Check current profile
tuned-adm active
# Output: Current active profile: balanced

# 3. List available profiles
tuned-adm list

# 4. Switch to virtual-host profile (optimized for KVM)
sudo tuned-adm profile virtual-host

# 5. Verify profile is active
tuned-adm active
# Output: Current active profile: virtual-host

# 6. Verify system settings match profile
sudo tuned-adm verify
# Should show: "Verification succeeded"
```

**What virtual-host profile does:**
- Disables transparent hugepages
- Optimizes CPU governor for performance
- Adjusts I/O scheduler for better VM disk performance
- Tunes network parameters

### Grant User Access to Libvirt

```bash
# 1. Add current user to libvirt group
sudo usermod -aG libvirt $USER

# 2. Set default connection to system mode
# Add to ~/.bashrc or ~/.zshrc:
echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.bashrc

# 3. Apply changes (or logout/login)
source ~/.bashrc

# 4. Verify connection mode
virsh uri
# Should output: qemu:///system
```

**Connection Modes Explained:**
- **Session mode** (`qemu:///session`):
  - Per-user VMs
  - No root required
  - Uses SLIRP networking (slow)
  - Limited functionality
- **System mode** (`qemu:///system`):
  - System-wide VMs
  - Requires libvirt group membership
  - Full networking capabilities
  - Recommended for most users

### Set ACL Permissions for VM Storage

By default, only root can create VMs in `/var/lib/libvirt/images/`. We'll grant your user access using ACLs.

```bash
# 1. Check current permissions
sudo getfacl /var/lib/libvirt/images/

# 2. Remove existing ACL permissions (clean slate)
sudo setfacl -R -b /var/lib/libvirt/images/

# 3. Grant read/write/execute permissions to your user
sudo setfacl -R -m "u:${USER}:rwX" /var/lib/libvirt/images/
# Capital 'X' = execute only on directories, not files

# 4. Set default ACL for new files/directories
sudo setfacl -m "d:u:${USER}:rwx" /var/lib/libvirt/images/
# This ensures new VMs inherit these permissions

# 5. Verify permissions
sudo getfacl /var/lib/libvirt/images/
# Should show your username with rwx permissions
```

---

## Network Setup

### Understanding VM Network Options

**Default NAT Network (virbr0)**
- VMs on private subnet (192.168.122.0/24)
- Can access internet through host NAT
- NOT accessible from LAN
- Good for: Development, testing

**Bridge Network (br0)**
- VMs appear as physical devices on LAN
- Get IP from router's DHCP
- Accessible from any device on network
- Good for: Servers, production services
- **Note**: Doesn't work with WiFi (only Ethernet)

### Create Bridge Network

#### Method 1: Using NetworkManager (nmcli)

Most desktop Linux distributions use NetworkManager.

```bash
# 1. Find your Ethernet interface name
sudo nmcli device status
# Look for 'ethernet' type (e.g., enp2s0, eth0, eno1)

# 2. Create bridge interface
sudo nmcli connection add type bridge con-name bridge0 ifname bridge0

# 3. Attach Ethernet interface to bridge
sudo nmcli connection add type ethernet slave-type bridge \
  con-name 'Bridge connection 1' ifname enp2s0 master bridge0
# Replace 'enp2s0' with your interface name

# 4. Configure bridge to auto-connect slave interfaces
sudo nmcli connection modify bridge0 connection.autoconnect-slaves 1

# 5. Activate bridge
sudo nmcli connection up bridge0

# 6. Verify bridge is active
sudo nmcli device status
# bridge0 should show as 'connected'

# 7. Check bridge has an IP address
ip addr show bridge0
```

#### Method 2: Using systemd-networkd

Alternative method for systemd-based networking.

```bash
# 1. Create bridge device
sudo tee /etc/systemd/network/br0.netdev > /dev/null << EOF
[NetDev]
Name=br0
Kind=bridge
EOF

# 2. Configure bridge network
sudo tee /etc/systemd/network/br0.network > /dev/null << EOF
[Match]
Name=br0

[Network]
DHCP=yes
EOF

# 3. Attach Ethernet to bridge
sudo tee /etc/systemd/network/enp2s0.network > /dev/null << EOF
[Match]
Name=enp2s0

[Network]
Bridge=br0
EOF
# Replace 'enp2s0' with your interface name

# 4. Restart networking
sudo systemctl restart systemd-networkd

# 5. Verify bridge
ip addr show br0
```

### Configure Bridge in Libvirt

```bash
# 1. Create bridge network XML definition
cat > /tmp/vmbridge.xml << EOF
<network>
  <name>vmbridge</name>
  <forward mode='bridge'/>
  <bridge name='bridge0'/>
</network>
EOF

# 2. Define the network in libvirt
sudo virsh net-define /tmp/vmbridge.xml
# Output: Network vmbridge defined from /tmp/vmbridge.xml

# 3. Start the network
sudo virsh net-start vmbridge

# 4. Enable autostart on boot
sudo virsh net-autostart vmbridge

# 5. Verify network is active
virsh net-list --all
# vmbridge should show as 'active' with 'yes' for autostart

# 6. Clean up temporary file
rm /tmp/vmbridge.xml
```

### Remove Bridge Network (If Needed)

```bash
# Stop and remove libvirt bridge network
sudo virsh net-destroy vmbridge
sudo virsh net-undefine vmbridge

# Remove NetworkManager bridge
sudo nmcli connection up 'Wired connection 1'
sudo nmcli connection del bridge0
sudo nmcli connection del 'Bridge connection 1'
```

---

## VM Management

### Create a Virtual Machine

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
  --location 'http://us.archive.ubuntu.com/ubuntu/dists/jammy/main/installer-amd64/' \
  --extra-args 'console=ttyS0,115200n8 serial'
```

**Parameter Explanations:**
- `--name` - VM name (used with virsh commands)
- `--ram` - Memory in MB (2048 = 2GB)
- `--vcpus` - Number of virtual CPU cores
- `--disk` - Disk image path and size in GB
- `--os-variant` - OS type for optimal settings (list with: `osinfo-query os`)
- `--network` - Network to connect to (vmbridge for LAN access)
- `--graphics none` - No GUI (headless server)
- `--console pty,target_type=serial` - Serial console access
- `--location` - Network installation source
- `--extra-args` - Kernel boot parameters for serial console

### List Available OS Variants

```bash
# Show all supported operating systems
osinfo-query os

# Search for specific OS
osinfo-query os | grep -i ubuntu
```

### Common VM Operations

```bash
# List all VMs (running and stopped)
virsh list --all

# Start a VM
virsh start vm-name

# Connect to VM console (Ctrl+] to exit)
virsh console vm-name

# Shutdown VM gracefully
virsh shutdown vm-name

# Force stop VM (like pulling power plug)
virsh destroy vm-name

# Reboot VM
virsh reboot vm-name

# Pause VM (suspend to RAM)
virsh suspend vm-name

# Resume paused VM
virsh resume vm-name

# Delete VM (keeps disk image)
virsh undefine vm-name

# Delete VM and its disk
virsh undefine vm-name --remove-all-storage

# Get VM information
virsh dominfo vm-name

# Get VM IP address (after it boots)
virsh domifaddr vm-name

# Edit VM configuration
virsh edit vm-name
```

### Clone VMs

```bash
# Clone VM (automatically creates new disk)
virt-clone --original source-vm --name new-vm --auto-clone

# Clone with specific disk location
virt-clone \
  --original source-vm \
  --name new-vm \
  --file /var/lib/libvirt/images/new-vm.qcow2
```

### Snapshot Management

```bash
# Create snapshot
virsh snapshot-create-as vm-name snapshot-name

# List snapshots
virsh snapshot-list vm-name

# Revert to snapshot
virsh snapshot-revert vm-name snapshot-name

# Delete snapshot
virsh snapshot-delete vm-name snapshot-name
```

---

## K3s Cluster Setup

### Overview

We'll create a 3-node Kubernetes cluster using K3s:
- 1 Master node (control plane)
- 2 Worker nodes

### Step 1: Create VMs

```bash
# Create master node
virt-install \
--name ubuntu-base \
--ram 1024 \
--vcpus 1 \
--disk path=/var/lib/libvirt/images/ubuntu-base.qcow2,size=10 \
--os-variant ubuntu22.04 \
--network network=vmbridge \
--graphics none --console pty,target_type=serial \
--location 'http://archive.ubuntu.com/ubuntu/dists/jammy/main/installer-amd64/' \
--extra-args 'console=ttyS0,115200n8 serial'


```

```bash
# Create master node
virt-install \
  --name k3s-master \
  --ram 2048 \
  --vcpus 2 \
  --disk path=/var/lib/libvirt/images/k3s-master.qcow2,size=20 \
  --os-variant ubuntu22.04 \
  --network network=vmbridge \
  --graphics none \
  --console pty,target_type=serial \
  --location 'http://us.archive.ubuntu.com/ubuntu/dists/jammy/main/installer-amd64/' \
  --extra-args 'console=ttyS0,115200n8 serial'

# After master is installed and running, clone for workers
virsh shutdown k3s-master
virt-clone --original k3s-master --name k3s-worker1 --auto-clone
virt-clone --original k3s-master --name k3s-worker2 --auto-clone

# Start all VMs
virsh start k3s-master
virsh start k3s-worker1
virsh start k3s-worker2
```

### Step 2: Install K3s on Master

```bash
# Connect to master node
virsh console k3s-master

# On master node:
# Install K3s server
curl -sfL https://get.k3s.io | sh -

# Wait for K3s to be ready
sudo k3s kubectl get nodes

# Get node token (needed for workers)
sudo cat /var/lib/rancher/k3s/server/node-token
# Copy this token - you'll need it for workers

# Get master IP address
ip addr show | grep inet
# Note the IP address (e.g., 192.168.1.100)

# Exit console: Ctrl+]
```

### Step 3: Join Worker Nodes

```bash
# Connect to worker1
virsh console k3s-worker1

# On worker1:
# Set variables (replace with your values)
export K3S_URL="https://192.168.1.100:6443"
export K3S_TOKEN="your-token-from-master"

# Install K3s agent
curl -sfL https://get.k3s.io | K3S_URL=$K3S_URL K3S_TOKEN=$K3S_TOKEN sh -

# Exit: Ctrl+]

# Repeat for worker2
virsh console k3s-worker2
# Run same commands as worker1
```

### Step 4: Verify Cluster

```bash
# Connect to master
virsh console k3s-master

# Check all nodes are ready
sudo k3s kubectl get nodes

# Should show:
# NAME          STATUS   ROLES                  AGE   VERSION
# k3s-master    Ready    control-plane,master   5m    v1.27.x
# k3s-worker1   Ready    <none>                 2m    v1.27.x
# k3s-worker2   Ready    <none>                 2m    v1.27.x

# Deploy a test application
sudo k3s kubectl create deployment nginx --image=nginx --replicas=3
sudo k3s kubectl expose deployment nginx --port=80 --type=NodePort

# Check deployment
sudo k3s kubectl get pods
sudo k3s kubectl get services
```

### Step 5: Access from Host

```bash
# Copy kubeconfig from master to host
virsh domifaddr k3s-master  # Get master IP

# On your host:
mkdir -p ~/.kube
scp user@master-ip:/etc/rancher/k3s/k3s.yaml ~/.kube/config

# Edit config to use master IP instead of localhost
sed -i 's/127.0.0.1/master-ip/g' ~/.kube/config

# Install kubectl on host
sudo pacman -S kubectl

# Test access
kubectl get nodes
```

### K3s Useful Commands

```bash
# On master:
sudo k3s kubectl get all --all-namespaces
sudo k3s kubectl get nodes -o wide
sudo k3s kubectl describe node node-name

# Drain node for maintenance
sudo k3s kubectl drain node-name --ignore-daemonsets

# Uncordon node
sudo k3s kubectl uncordon node-name

# Delete node from cluster
sudo k3s kubectl delete node node-name

# Uninstall K3s
# On workers:
/usr/local/bin/k3s-agent-uninstall.sh

# On master:
/usr/local/bin/k3s-uninstall.sh
```

---

## Docker Swarm Setup

### Overview

We'll create a 3-node Docker Swarm cluster:
- 1 Manager node
- 2 Worker nodes

### Step 1: Create VMs

```bash
# Create manager node
virt-install \
  --name swarm-manager \
  --ram 2048 \
  --vcpus 2 \
  --disk path=/var/lib/libvirt/images/swarm-manager.qcow2,size=20 \
  --os-variant ubuntu22.04 \
  --network network=vmbridge \
  --graphics none \
  --console pty,target_type=serial \
  --location 'http://us.archive.ubuntu.com/ubuntu/dists/jammy/main/installer-amd64/' \
  --extra-args 'console=ttyS0,115200n8 serial'

# Clone for workers
virsh shutdown swarm-manager
virt-clone --original swarm-manager --name swarm-worker1 --auto-clone
virt-clone --original swarm-manager --name swarm-worker2 --auto-clone

# Start all VMs
virsh start swarm-manager
virsh start swarm-worker1
virsh start swarm-worker2
```

### Step 2: Install Docker on All Nodes

```bash
# Connect to each VM and run:
virsh console swarm-manager  # Then swarm-worker1, swarm-worker2

# On each node:
# Update and install Docker
sudo apt update
sudo apt install -y docker.io

# Start and enable Docker
sudo systemctl enable --now docker

# Add user to docker group
sudo usermod -aG docker $USER

# Verify Docker is running
docker version

# Exit: Ctrl+]
```

### Step 3: Initialize Swarm on Manager

```bash
# Connect to manager
virsh console swarm-manager

# Initialize swarm
docker swarm init --advertise-addr <manager-ip>

# Example output:
# Swarm initialized: current node (xxx) is now a manager.
# To add a worker to this swarm, run the following command:
#     docker swarm join --token SWMTKN-xxx <manager-ip>:2377
# To add a manager to this swarm, run 'docker swarm join-token manager'

# Copy the join command - you'll need it for workers

# Get manager IP if needed
ip addr show | grep inet
```

### Step 4: Join Workers to Swarm

```bash
# Connect to worker1
virsh console swarm-worker1

# Run the join command from manager output:
docker swarm join --token SWMTKN-xxx <manager-ip>:2377

# Should see: "This node joined a swarm as a worker."
# Exit: Ctrl+]

# Repeat for worker2
virsh console swarm-worker2
# Run same join command
```

### Step 5: Verify Swarm

```bash
# Connect to manager
virsh console swarm-manager

# List all nodes
docker node ls

# Should show:
# ID            HOSTNAME         STATUS  AVAILABILITY  MANAGER STATUS
# xxx *         swarm-manager    Ready   Active        Leader
# yyy           swarm-worker1    Ready   Active        
# zzz           swarm-worker2    Ready   Active

# Deploy a test service
docker service create \
  --name web \
  --replicas 3 \
  --publish 8080:80 \
  nginx

# Check service
docker service ls
docker service ps web

# Scale service
docker service scale web=5

# Check running containers across cluster
docker node ps $(docker node ls -q)
```

### Docker Swarm Useful Commands

```bash
# On manager node:

# Node management
docker node ls                    # List all nodes
docker node inspect node-name     # Detailed node info
docker node update --availability drain node-name  # Drain node
docker node update --availability active node-name # Activate node
docker node rm node-name         # Remove node

# Service management
docker service create --name app --replicas 3 image
docker service ls                # List services
docker service ps service-name   # List service tasks
docker service logs service-name # View service logs
docker service scale service-name=5  # Scale service
docker service update --image new-image service-name  # Update image
docker service rm service-name   # Remove service

# Stack management (Docker Compose for Swarm)
docker stack deploy -c docker-compose.yml stack-name
docker stack ls                  # List stacks
docker stack services stack-name # List stack services
docker stack ps stack-name       # List stack tasks
docker stack rm stack-name       # Remove stack

# Network management
docker network create --driver overlay my-network
docker network ls
docker network inspect network-name

# Secrets management
echo "password" | docker secret create db_password -
docker secret ls
docker secret inspect secret-name

# Leave swarm
# On worker:
docker swarm leave

# On manager:
docker swarm leave --force
```

### Example Docker Stack Deployment

```bash
# Create docker-compose.yml on manager:
cat > docker-compose.yml << EOF
version: '3.8'

services:
  web:
    image: nginx:latest
    ports:
      - "8080:80"
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
    networks:
      - webnet

  visualizer:
    image: dockersamples/visualizer
    ports:
      - "8081:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    deploy:
      placement:
        constraints: [node.role == manager]
    networks:
      - webnet

networks:
  webnet:
    driver: overlay
EOF

# Deploy stack
docker stack deploy -c docker-compose.yml myapp

# Access:
# - Web app: http://manager-ip:8080
# - Visualizer: http://manager-ip:8081
```

---

## Useful Commands Reference

### VM Management

```bash
# List VMs
virsh list --all                 # All VMs
virsh list --state-running       # Only running VMs
virsh list --inactive            # Only stopped VMs

# VM power operations
virsh start vm-name              # Start VM
virsh shutdown vm-name           # Graceful shutdown
virsh destroy vm-name            # Force stop
virsh reboot vm-name             # Reboot
virsh reset vm-name              # Hard reset

# VM information
virsh dominfo vm-name            # Basic info
virsh domifaddr vm-name          # IP addresses
virsh domblklist vm-name         # Disk list
virsh dumpxml vm-name            # Full XML configuration

# Console and display
virsh console vm-name            # Serial console (Ctrl+] to exit)
virt-viewer vm-name              # Graphical console

# VM lifecycle
virsh undefine vm-name           # Remove VM (keeps disk)
virsh undefine vm-name --remove-all-storage  # Remove VM and disks

# Cloning
virt-clone --original vm --name new-vm --auto-clone
```

### Network Management

```bash
# List networks
virsh net-list --all

# Network operations
virsh net-start network-name     # Start network
virsh net-destroy network-name   # Stop network
virsh net-autostart network-name # Enable autostart
virsh net-undefine network-name  # Remove network

# Network information
virsh net-info network-name
virsh net-dumpxml network-name
virsh net-dhcp-leases network-name  # Show DHCP leases
```

### Storage Management

```bash
# List storage pools
virsh pool-list --all

# Pool operations
virsh pool-start pool-name
virsh pool-destroy pool-name
virsh pool-autostart pool-name
virsh pool-undefine pool-name

# Create disk image
qemu-img create -f qcow2 /path/to/disk.qcow2 20G

# Get disk info
qemu-img info /path/to/disk.qcow2

# Convert disk format
qemu-img convert -f qcow2 -O raw input.qcow2 output.raw

# Resize disk
qemu-img resize /path/to/disk.qcow2 +10G
```

### Snapshot Management

```bash
# Create snapshot
virsh snapshot-create-as vm-name snapshot-name "Description"

# List snapshots
virsh snapshot-list vm-name

# Get snapshot info
virsh snapshot-info vm-name snapshot-name

# Revert to snapshot
virsh snapshot-revert vm-name snapshot-name

# Delete snapshot
virsh snapshot-delete vm-name snapshot-name

# Delete all snapshots
virsh snapshot-list vm-name --name | xargs -I {} virsh snapshot-delete vm-name {}
```

### Performance Monitoring

```bash
# CPU stats
virsh domstats vm-name --cpu-total

# Memory stats
virsh domstats vm-name --balloon

# Disk I/O stats
virsh domstats vm-name --block

# Network stats
virsh domstats vm-name --net

# All stats
virsh domstats vm-name

# Real-time monitoring
virt-top  # Top-like interface for VMs
```

### Troubleshooting

```bash
# View libvirt logs
sudo journalctl -u libvirtd -f
sudo journalctl -u virtqemud -f

# VM logs
sudo tail -f /var/log/libvirt/qemu/vm-name.log

# Verify VM XML configuration
virsh dumpxml vm-name | less

# Test VM console connectivity
virsh console vm-name --force

# Check QEMU process
ps aux | grep qemu

# Verify permissions
ls -l /var/lib/libvirt/images/
sudo getfacl /var/lib/libvirt/images/
```

---

## Best Practices

### Security
- Always use bridge networking only on trusted networks
- Keep VMs updated with security patches
- Use SSH keys instead of passwords for VM access
- Implement firewall rules on VMs
- Use separate storage for sensitive data

### Performance
- Allocate appropriate CPU and RAM (don't over-provision)
- Use virtio drivers for better disk and network performance
- Enable CPU host-passthrough for near-native performance
- Use qcow2 format with preallocation for production VMs
- Place VM disks on fast storage (SSD/NVMe)

### Backup
- Take regular snapshots before major changes
- Backup VM disk images and XML configurations
- Test restore procedures periodically
- Consider using external backup tools (Borg, Restic)

### Monitoring
- Monitor host resource usage (CPU, RAM, disk)
- Set up alerts for critical thresholds
- Log VM console output for troubleshooting
- Use `virt-top` for real-time monitoring

---

## Troubleshooting Guide

### VM Won't Start
```bash
# Check error messages
sudo journalctl -u virtqemud -n 50

# Verify XML is valid
virsh dumpxml vm-name | xmllint --format -

# Check permissions
ls -l /var/lib/libvirt/images/vm-disk.qcow2
```

### No Network Connectivity
```bash
# Verify bridge is up
ip link show bridge0
sudo nmcli device status

# Check VM network interface
virsh domiflist vm-name

# Verify network is active
virsh net-list --all
```

### Can't Connect to Console
```bash
# Force console connection
virsh console vm-name --force

# Check if VM has serial console configured
virsh dumpxml vm-name | grep console
```

### Permission Denied Errors
```bash
# Fix ACL permissions
sudo setfacl -R -m "u:${USER}:rwX" /var/lib/libvirt/images/

# Verify group membership
groups | grep libvirt

# Reboot if just added to group
sudo reboot
```

---

## Additional Resources

- [Arch Wiki - KVM](https://wiki.archlinux.org/title/KVM)
- [Arch Wiki - Libvirt](https://wiki.archlinux.org/title/Libvirt)
- [K3s Documentation](https://docs.k3s.io/)
- [Docker Swarm Documentation](https://docs.docker.com/engine/swarm/)
- [Libvirt Documentation](https://libvirt.org/docs.html)
- [QEMU Documentation](https://www.qemu.org/docs/master/)

---

**Document Version:** 1.0  
**Last Updated:** 2025-10-04  
**Author:** System Administrator Guide
