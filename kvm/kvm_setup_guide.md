# KVM Setup Guide with Bridge Networking

A comprehensive guide for setting up KVM virtual machines with bridged networking for clustering and multi-VM scenarios.

## Table of Contents
- [Why Bridge Networking?](#why-bridge-networking)
- [Initial Setup](#initial-setup)
- [Bridge Network Configuration](#bridge-network-configuration)
- [VM Creation Workflow](#vm-creation-workflow)
- [Essential Commands](#essential-commands)
- [Troubleshooting](#troubleshooting)

---

## Why Bridge Networking?

**NAT vs Bridge:**
- **NAT (default)**: VMs get internal IPs (192.168.122.x) and share host's IP via NAT
  - ❌ VMs can't be accessed directly from LAN
  - ❌ Doesn't work for clustering scenarios (k3s, Docker Swarm, etc.)
  - ✅ Simple setup, no network configuration needed

- **Bridge**: VMs get IPs from your LAN DHCP server
  - ✅ VMs appear as physical machines on your network
  - ✅ Perfect for clustering, multi-node setups
  - ✅ Direct access from any device on LAN
  - ⚠️ Requires bridge configuration on host

---

## Initial Setup

### Install Required Packages

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y qemu-kvm libvirt-daemon-system libvirt-clients bridge-utils \
                    virt-manager virtinst cloud-image-utils

# Fedora/RHEL
sudo dnf install -y qemu-kvm libvirt virt-install bridge-utils cloud-utils
```

### Enable and Start libvirtd

```bash
sudo systemctl enable --now libvirtd
sudo systemctl status libvirtd
```

### Add User to libvirt Group

```bash
sudo usermod -aG libvirt $USER
sudo usermod -aG kvm $USER
# Log out and back in for group changes to take effect
```

---

## Bridge Network Configuration

### Step 1: Create Bridge Interface on Host

Create or edit `/etc/netplan/01-netcfg.yaml` (Ubuntu) or equivalent:

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    # Your physical interface (check with 'ip a')
    enp0s31f6:
      dhcp4: false
      dhcp6: false
  bridges:
    br0:
      interfaces: [enp0s31f6]
      dhcp4: true
      # Or static IP:
      # addresses: [192.168.1.100/24]
      # gateway4: 192.168.1.1
      # nameservers:
      #   addresses: [8.8.8.8, 8.8.4.4]
```

Apply the configuration:

```bash
sudo netplan apply
# Verify bridge created
ip a show br0
brctl show
```

### Step 2: Create libvirt Bridge Network

Create `vmbridge.xml`:

```xml
<network>
  <name>vmbridge</name>
  <forward mode='bridge'/>
  <bridge name='br0'/>
</network>
```

Define and start the network:

```bash
virsh net-define vmbridge.xml
virsh net-start vmbridge
virsh net-autostart vmbridge

# Verify
virsh net-list --all
```

Expected output:
```
 Name       State    Autostart   Persistent
---------------------------------------------
 default    active   yes         yes
 vmbridge   active   yes         yes
```

---

## VM Creation Workflow

### Step 1: Prepare Cloud-Init Files

#### Directory Structure
```bash
mkdir -p /var/lib/libvirt/images/{k3s,templates}
cd /var/lib/libvirt/images
```

#### Download Ubuntu Cloud Image
```bash
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img \
     -O templates/jammy-server-cloudimg-amd64.img
```

#### Create user-data.yml
```yaml
#cloud-config
preserve_hostname: false
users:
  - name: kamronbek
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh-authorized-keys:
      - ssh-ed25519 AAAAC3Nza... your-key-here
ssh_pwauth: true
disable_root: false
chpasswd:
  list: |
    kamronbek:password
  expire: false
package_update: true
package_upgrade: true
package_reboot_if_required: true
packages:
  - curl
  - vim
  - qemu-guest-agent
runcmd:
  - [systemctl, enable, --now, qemu-guest-agent]
final_message: "VM is ready!"
```

#### Create network-config.yml
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

**Note**: Route metrics ensure proper interface priority. Lower metric = higher priority.

#### Create Meta-Data Files

**k3s/k3s-server-meta-data.yml:**
```yaml
instance-id: k3s-server-01
local-hostname: k3s-server
```

**k3s/k3s-agent-meta-data.yml:**
```yaml
instance-id: k3s-agent-001
local-hostname: k3s-agent
```

### Step 2: Generate Cloud-Init ISO

```bash
# For server
cloud-localds --network-config=network-config.yml \
  k3s/k3s-server-seed.iso \
  user-data.yml \
  k3s/k3s-server-meta-data.yml

# For agent
cloud-localds --network-config=network-config.yml \
  k3s/k3s-agent-seed.iso \
  user-data.yml \
  k3s/k3s-agent-meta-data.yml
```

### Step 3: Create VM Disk Images

```bash
# Create server disk (20GB, backed by cloud image)
qemu-img create -f qcow2 -F qcow2 \
  -b /var/lib/libvirt/images/templates/jammy-server-cloudimg-amd64.img \
  /var/lib/libvirt/images/k3s/k3s-server.qcow2 20G

# Create agent disk
qemu-img create -f qcow2 -F qcow2 \
  -b /var/lib/libvirt/images/templates/jammy-server-cloudimg-amd64.img \
  /var/lib/libvirt/images/k3s/k3s-agent.qcow2 20G
```

**Key Points:**
- `-b`: Backing file (base image) - saves space
- `-f qcow2`: Output format (copy-on-write)
- `-F qcow2`: Backing file format
- `20G`: Virtual disk size (only grows as needed)

### Step 4: Create and Start VMs

```bash
# Create server VM
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

# Create agent VM
sudo virt-install \
  --name k3s-agent \
  --memory 4096 \
  --vcpus 2 \
  --disk path=/var/lib/libvirt/images/k3s/k3s-agent.qcow2,format=qcow2,bus=virtio \
  --disk path=/var/lib/libvirt/images/k3s/k3s-agent-seed.iso,device=cdrom \
  --os-variant ubuntu22.04 \
  --import \
  --network network=vmbridge,model=virtio \
  --graphics none \
  --noautoconsole
```

---

## Essential Commands

### VM Management

```bash
# List all VMs
virsh list --all

# Start VM
virsh start <vm-name>

# Stop VM (graceful)
virsh shutdown <vm-name>

# Force stop VM
virsh destroy <vm-name>

# Restart VM
virsh reboot <vm-name>

# Enable autostart
virsh autostart <vm-name>

# Disable autostart
virsh autostart --disable <vm-name>

# Delete VM (keeps disks)
virsh undefine <vm-name>

# Delete VM and remove all storage
virsh undefine <vm-name> --remove-all-storage

# Connect to VM console
virsh console <vm-name>
# Exit console: Ctrl+] or Ctrl+5
```

### VM Information

```bash
# Show VM info
virsh dominfo <vm-name>

# Show VM IP address
virsh domifaddr <vm-name>

# Show VM disk info
virsh domblklist <vm-name>

# Show VM network interfaces
virsh domiflist <vm-name>

# Export VM XML configuration
virsh dumpxml <vm-name> > vm-config.xml
```

### Network Management

```bash
# List networks
virsh net-list --all

# Show network details
virsh net-info <network-name>

# Show DHCP leases (for NAT networks)
virsh net-dhcp-leases default

# Start network
virsh net-start <network-name>

# Stop network
virsh net-destroy <network-name>

# Enable network autostart
virsh net-autostart <network-name>

# Delete network
virsh net-undefine <network-name>
```

### Disk Management

```bash
# List storage pools
virsh pool-list --all

# Show disk image info
qemu-img info /path/to/disk.qcow2

# Resize disk (must be offline)
qemu-img resize /path/to/disk.qcow2 +10G

# Convert disk formats
qemu-img convert -f qcow2 -O raw source.qcow2 destination.raw

# Check disk for errors
qemu-img check /path/to/disk.qcow2

# Create snapshot
virsh snapshot-create-as <vm-name> snapshot1 "Description"

# List snapshots
virsh snapshot-list <vm-name>

# Restore snapshot
virsh snapshot-revert <vm-name> snapshot1

# Delete snapshot
virsh snapshot-delete <vm-name> snapshot1
```

### Host Bridge Inspection

```bash
# Show bridge details
brctl show

# Modern alternative
bridge link show

# Show bridge MAC addresses
brctl showmacs br0

# Show network interfaces
ip link show
ip addr show
```

---

## Troubleshooting

### Common Issues

#### 1. Disk Already in Use Error
```
ERROR: Disk /path/to/disk.qcow2 is already in use by other guests
```

**Solution:**
```bash
# List all VMs using the disk
virsh list --all

# Remove the old VM definition
virsh undefine old-vm-name --remove-all-storage

# Or just override the check
virt-install ... --check path_in_use=off
```

#### 2. VMs Not Getting IP Addresses

**Check:**
```bash
# Verify bridge is up
ip link show br0

# Check VM network attachment
virsh domiflist <vm-name>

# Verify network is active
virsh net-list --all

# Check DHCP server on your router
```

**Inside VM (via console):**
```bash
virsh console <vm-name>
# Then inside VM:
ip a
sudo dhclient -v
```

#### 3. Can't Connect to VM Console

```bash
# Ensure qemu-guest-agent is installed and running (in VM)
sudo apt install qemu-guest-agent
sudo systemctl enable --now qemu-guest-agent

# Alternative: use SSH instead
ssh user@<vm-ip>
```

#### 4. Permission Denied Errors

```bash
# Fix ownership of image directory
sudo chown -R libvirt-qemu:kvm /var/lib/libvirt/images/

# Fix SELinux context (RHEL/Fedora)
sudo chcon -t virt_image_t /var/lib/libvirt/images/path/to/disk.qcow2
```

#### 5. Bridge Not Working After Reboot

```bash
# Check bridge configuration
ip link show br0

# Restart networking
sudo netplan apply  # Ubuntu
sudo systemctl restart NetworkManager  # Fedora

# Restart libvirt network
virsh net-destroy vmbridge
virsh net-start vmbridge
```

### Performance Tips

1. **Use virtio drivers** for disk and network (already in examples)
2. **Allocate appropriate resources**: Don't over-provision
3. **Use backing files** for template-based VMs (saves disk space)
4. **Enable KVM acceleration**: Check with `egrep -c '(vmx|svm)' /proc/cpuinfo` (should be > 0)

### Useful Monitoring

```bash
# Watch VM resource usage
virt-top

# Check host CPU info
lscpu | grep Virtualization

# Verify KVM modules loaded
lsmod | grep kvm

# Show all VM processes
ps aux | grep qemu
```

---

## Quick Reference: Complete Workflow

```bash
# 1. Setup (one-time)
sudo apt install qemu-kvm libvirt-daemon-system cloud-image-utils
sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt $USER

# 2. Configure bridge (edit netplan, apply)
sudo netplan apply
virsh net-define vmbridge.xml
virsh net-start vmbridge
virsh net-autostart vmbridge

# 3. Download base image
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

# 4. Create cloud-init ISO
cloud-localds --network-config=network-config.yml seed.iso user-data.yml meta-data.yml

# 5. Create VM disk
qemu-img create -f qcow2 -F qcow2 -b base-image.img vm-disk.qcow2 20G

# 6. Create VM
sudo virt-install \
  --name myvm \
  --memory 4096 \
  --vcpus 2 \
  --disk path=vm-disk.qcow2,format=qcow2,bus=virtio \
  --disk path=seed.iso,device=cdrom \
  --os-variant ubuntu22.04 \
  --import \
  --network network=vmbridge,model=virtio \
  --graphics none \
  --noautoconsole

# 7. Check status
virsh list
virsh domifaddr myvm
```

---

## Additional Resources

- **libvirt docs**: https://libvirt.org/docs.html
- **cloud-init docs**: https://cloudinit.readthedocs.io/
- **Ubuntu cloud images**: https://cloud-images.ubuntu.com/
- **KVM networking guide**: https://wiki.libvirt.org/page/Networking

---

**Pro Tip**: Keep your cloud-init files, network configs, and scripts in version control for easy VM reproduction!