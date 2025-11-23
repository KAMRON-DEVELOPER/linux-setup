# SOME

QEMU: This is the emulator. It can emulate a full computer system (CPU, memory, storage, peripherals) in software.

KVM (Kernel-based Virtual Machine): This is a Linux kernel module that allows a user-space program like QEMU to utilize the hardware virtualization extensions built into modern CPUs (Intel VT-x or AMD-V).

Libvirt: This is a management toolkit and API. Think of it as the friendly boss for QEMU. Instead of writing complex QEMU commands, you use libvirt tools like virsh (command-line) or virt-install to manage your VMs, storage, and networks.

KVM Bridge vs. Docker Bridge

This is a fantastic question. The key difference is the network layer they operate on.

    KVM Bridge (Layer 2): The bridge we are creating (br0) operates at the Data Link Layer (Layer 2) of the OSI model. It deals with MAC addresses. This is why it acts like a physical switch, making VMs appear as separate physical devices on your LAN.

    Docker's Default Bridge (Layer 3): Docker's default docker0 bridge operates at the Network Layer (Layer 3). It creates a private, internal subnet (e.g., 172.17.0.0/16) inside your host. Docker then acts like a router, using Network Address Translation (NAT) to forward traffic from containers to the outside world. Containers on this network can't be reached directly from your LAN without explicit port mapping (-p 8080:80).

Enable nested virtualization (optional)

For the current session

Intel:

sudo modprobe -r kvm_intel
sudo modprobe kvm_intel nested=1

AMD:

sudo modprobe -r kvm_amd
sudo modprobe kvm_amd nested=1

Persistent nested virtualization

Intel:

echo "options kvm_intel nested=1" | sudo tee /etc/modprobe.d/kvm-intel.conf

AMD:

echo "options kvm_amd nested=1" | sudo tee /etc/modprobe.d/kvm-amd.conf

# Linux VM Networking & IOMMU Notes

Check for Virtualization Support
lscpu | grep Virtualization
You should see VT-x for Intel or AMD-V for AMD CPUs.
Alternatively, check for the presence of the vmx or svm flags:
egrep -c '(vmx|svm)' /proc/cpuinfo
If the result is greater than 0, your CPU supports virtualization. 2. Enable Virtualization in BIOS/UEFI
Reboot your system and enter the BIOS/UEFI settings. Look for options like “Intel Virtualization Technology” or “SVM Mode” and ensure they are enabled.

Installing QEMU, KVM, and Virt-Manager
Arch Linux makes it simple to install the necessary packages via the pacman package manager.
Update Your System
sudo pacman -Syu 2. Install Required Packages
Run the following to install QEMU, KVM, and management tools:
sudo pacman -S qemu virt-manager virt-viewer dnsmasq vde2 bridge-utils openbsd-netcat
These packages include:

    qemu: The main QEMU emulator.
    virt-manager: A graphical tool for managing virtual machines.
    virt-viewer: A simple viewer for virtual machines.
    dnsmasq: Provides DHCP and DNS services to VMs.
    vde2, bridge-utils, openbsd-netcat: Network bridging utilities.

Step 3: Verify KVM Installation

To check if KVM is installed and configured correctly, run the following command:

lsmod | grep kvm

If the output shows kvm and kvm_intel or kvm_amd, it means that KVM is successfully installed on your Arch Linux machine.

Ensure that your kernel includes KVM modules

zgrep CONFIG_KVM /proc/config.gz

    y = Yes (always installed)
    m = Loadable module

Install QEMU, libvirt, viewers, and tools

sudo pacman -S qemu-full qemu-img libvirt virt-install virt-manager virt-viewer \
edk2-ovmf dnsmasq swtpm guestfs-tools libosinfo tuned

    qemu-full - user-space KVM emulator, manages communication between hosts and VMs
    qemu-img - provides create, convert, modify, and snapshot, offline disk images
    libvirt - an open-source API, daemon, and tool for managing platform virtualization
    virt-install - CLI tool to create guest VMs
    virt-manager - GUI tool to create and manage guest VMs
    virt-viewer - GUI console to connect to running VMs
    edk2-ovmf - enables UEFI support for VMs
    dnsmasq - lightweight DNS forwarder and DHCP server
    swtpm - TPM (Trusted Platform Module) emulator for VMs
    guestfs-tools - provides a set of extended CLI tools for managing VMs
    libosinfo - a library for managing OS information for virtualization.
    tuned - system tuning service for linux allows us to optimise the hypervisor for speed.

## Enable the libvirt daemon

Monolithic vs modular daemons

    Here is the documentation(https://libvirt.org/daemons.html#architectural-options) detailing the difference between monolithic and modular daemons.
    Choose between option 1 and 2 and then do a reboot.

Option 1: Enable the modular daemon.
Option 1: Enable the modular daemon.

for drv in qemu interface network nodedev nwfilter secret storage; do
sudo systemctl enable virt${drv}d.service;
    sudo systemctl enable virt${drv}d{,-ro,-admin}.socket;
done

KVM + bridge networking + storage pools setup, the minimum daemons you’ll want are:
sudo systemctl enable --now virtqemud.socket virtnetworkd.socket virtstoraged.socket virtproxyd.socket
That’s the clean modular combo:

virtqemud → manages QEMU/KVM guests

virtnetworkd → handles NAT/bridge/dnsmasq virtual networks

virtstoraged → storage pools/volumes

virtproxyd → acts like the old libvirtd front-end so virsh and virt-manager don’t notice the change

Optional but often useful:

virtlockd and virtlogd (systemd usually pulls them in automatically as dependencies)

    loop through virtualization systemd services necessary for the libvirt modular daemon.

Option 2: Enable the monolithic daemon.

sudo systemctl enable libvirtd.service

---

## IOMMU (Intel VT-d / AMD-Vi)

- **What it is**: Input/Output Memory Management Unit
- **Why**:
  - Lets hypervisor safely remap device DMA memory
  - Required for **PCI passthrough** (e.g. GPU, NIC, USB controller directly to VM)
  - Without it, VMs can’t use devices like they were bare metal
- **Enable**:
  1. In BIOS/UEFI → enable `Intel VT-d` (or `AMD IOMMU`)
  2. Kernel parameter in GRUB:
     - Intel: `intel_iommu=on`
     - AMD: `amd_iommu=on`
  3. Check with:
     ```bash
     dmesg | grep -e DMAR -e IOMMU
     ```

`sudo nvim /etc/default/grub`

`GRUB_CMDLINE_LINUX="zswap.enabled=0 rootfstype=ext4 intel_iommu=on iommu=pt"`

`sudo grub-mkconfig -o /boot/grub/grub.cfg`

1. Open your GRUB config
   sudo vim/nvim /etc/default/grub
2. Add the following kernel module entries

# /etc/default/grub

GRUB_CMDLINE_LINUX="... intel_iommu=on iommu=pt" 3. Regenerate your grub.cfg file
sudo grub-mkconfig -o /boot/grub/grub.cfg
sudo reboot

---

## Optimise Host with TuneD

1. Enable TuneD daemon
   sudo systemctl enable --now tuned.service
2. Check active TuneD profile
   tuned-adm active
   > > Current active profile: balanced
   > > `balanced - generic profile not specialised for KVM, we will change this.`
3. List all TuneD profiles
   tuned-adm list
4. Set profile to virtual-host
   sudo tuned-adm profile virtual-host
5. Verify that TuneD profile
   tuned-adm active
6. sudo tuned-adm verify
   `Verification succeeded, current system settings match the preset profile. See TuneD log file ('/var/log/tuned/tuned/log') for details.`

## KVM Networking

#### Configure bridge interface

1. find the interface name of your ethernet connection
   `sudo nmcli device status`

2. sheet
   DEVICE TYPE STATE CONNECTION
   enp2s0 ethernet connected Wired connection 1
   lo loopback connected (externally) lo
   virbr0 bridge connected (externally) virbr0

3. create a bridge interface using nmcli
   sudo nmcli connection add type bridge con-name bridge0 ifname bridge0

4. connect the ethernet interface to the bridge
   sudo nmcli connection add type ethernet slave-type bridge con-name 'Bridge connection 1' ifname enp2s0 master bridge0

5. activate the newly created connection
   sudo nmcli connection up bridge0

6. enable connection.autoconnect-slaves parameter
   sudo nmcli connection modify bridge0 connection.autoconnect-slaves 1

7. reactivate the bridge and verify connection
   sudo nmcli connection up bridge0
   sudo nmcli device status

8. DEVICE TYPE STATE CONNECTION
   bridge0 bridge connected bridge0
   enp2s0 ethernet connected Wired connection 1
   lo loopback connected (externally) lo
   virbr0 bridge connected (externally) virbr0

#### Configure bridge network

1. create an XML file called nwbridge.xml.
   vim/nvim vmbridge.xml

2. post the following XML
<network>
  <!-- whatever name you like (vmbridge, lanbridge, host-bridge, nwbridge) -->
  <name>vmbridge</name>
  <forward mode='bridge'/>
  <bridge name='br0'/>
</network>

# ============================================
# 4. CREATE BRIDGE NETWORK
# ============================================
# Create bridge XML configuration
cat > /tmp/bridge.xml << EOF
<network>
  <name>br0</name>
  <forward mode="bridge"/>
  <bridge name="br0"/>
</network>
EOF

# Define and start the bridge network
sudo virsh net-define /tmp/bridge.xml
sudo virsh net-start br0
sudo virsh net-autostart br0


3. define the bridge network
   sudo virsh net-define --file vmbridge.xml

   > > > Network vmbridge defined from nwbridge.xml

4. start the bridge network
   sudo virsh net-start vmbridge

5. auto-start bridge network on boot
   sudo virsh net-autostart vmbridge

6. delete nwbridge.xml file
   rm vmbridge.xml

7. verify that vmbridge network exists
   sudo virsh net-list --all

8. Name State Autostart Persistent
sudo virsh net-autostart --network vmbridge
>>> Network vmbridge marked as autostarted

~ ❯ virsh net-list --all
 Name       State      Autostart   Persistent
-----------------------------------------------
 default    inactive   no          yes
 vmbridge   active     yes         yes

~ ❯

#### Removing bridge network and interface

If you want to revert the changes to your network, do the following:
sudo virsh net-destroy nwbridge
sudo virsh net-undefine nwbridge
sudo nmcli connection up 'Wired connection 1'
sudo nmcli connection del bridge0
sudo nmcli connection del 'Bridge connection 1'

## Libvirt connection modes

Libvirt has two methods for connecting to the KVM Hypervisor, Session and System.
In session mode, a regular user is connected to a per-user instance. Allowing each user to manage their own pool of virtual machines. This is also the default mode.
The advantage of this mode is, permissions are not an issue. As no root access is required.
The disadvantage is this mode uses QEMU User Networking (SLIRP). This is a user-space IP stack, which yields overhead resulting in poor networking performance.
And if you want to implement an option that requires root privileges. You will be unable to do so.

## System Mode

In the system mode you are granted access to all system resources.

### Granting system-wide access to regular user.

1. check current mode
   sudo virsh uri

   > > > qemu:///session

2. add the current user to the libvirt group
   sudo usermod -aG libvirt $USER

3. set env variable with the default uri and check
   echo 'export LIBVIRT_DEFAULT_URI="qemu:///system"' >> ~/.bashrc or ~/.zshrc
   sudo virsh uri

### Bridge Networking (Host + VM on LAN)

`By default all virtual machines will connect to the built-in default NAT network.
To make VMs accessible via the LAN you must create a network bridge.
Keep in mind that network bridges won't work with hosts running on Wireless NICs.`

Two common setups:

### A. systemd-networkd

1. `/etc/systemd/network/br0.netdev`

````ini
[NetDev]
Name=br0
Kind=bridge

2. `/etc/systemd/network/br0.network`

```ini
[Match]
Name=br0
[Network]
DHCP=yes

3. `/etc/systemd/network/enp2s0.network`

```ini
[Match]
Name=enp2s0
[Network]
Bridge=br0

4. `sudo systemctl restart systemd-networkd`

5. `ip addr show br0`


### 5. NetworkManager (nmcli)
```bash
nmcli connection add type bridge ifname br0 con-name br0
nmcli connection add type bridge-slave ifname enp2s0 master br0
nmcli connection modify br0 ipv4.method auto
nmcli connection up br0

# check
nmcli device status
ip addr show br0

Using the Bridge in Libvirt
When creating a VM:
In virt-manager GUI → Add Network Interface → “Bridge → br0”
Or in XML:
`virsh dumpxml myvm`
→ prints the VM config.
To change networking, you’d normally:
`virsh edit myvm`
and add the <interface> section.
<interface type='bridge'>
  <source bridge='br0'/>
  <model type='virtio'/>
</interface>


### Set ACL for the KVM images directory
check permissions on the images directory
sudo getfacl /var/lib/libvirt/images

getfacl: Removing leading '/' from absolute path names
# file : var/lib/libvirt/images/
# owner: root
# group: root
user::rwx
group::--x
other::--x

2. recursively remove existing ACL permissions
sudo setfacl -R -b /var/lib/libvirt/images/

3. recursively grant permission to the current user
sudo setfacl -R -m "u:${USER}:rwX" /var/lib/libvirt/images/
uppercase X states that execution permission only applied to child folders and not child files.

4. enable special permissions default ACL
sudo setfacl -m "d:u:${USER}:rwx" /var/lib/libvirt/images/
if this step is omitted, new dirs or files created within the images directory will not have this ACL set.

5. verify your ACL permissions within the images directory
sudo getfacl /var/lib/libvirt/images/

getfacl: Removing leading '/' from absolute path names
# file : var/lib/libvirt/images/
# owner: root
# group: root
user::rwx
user:tatum:rwx
group::--x
mask::rwx
other::--x
default:user::rwx
default:user:tatum:rwx
default:group::--x
default:mask::rwx
default:other::--x


````




# Create a VM
Now you can create a VM using virt-install and connect it directly to your LAN
virt-install \
--name k3s-master1 \
--ram 2048 \
--vcpus 2 \
--disk path=/var/lib/libvirt/images/k3s-node1.qcow2,size=20 \
--os-variant ubuntu22.04 \
--network network=vmbridge \
--graphics none --console pty,target_type=serial \
--location 'http://us.archive.ubuntu.com/ubuntu/dists/jammy/main/installer-amd64/' \
--extra-args 'console=ttyS0,115200n8 serial'

virt-install \
--name k3s-node1 \
--ram 1028 \
--vcpus 1 \
--disk path=/var/lib/libvirt/images/k3s-node1.qcow2,size=20 \
--os-variant ubuntu22.04 \
--network network=vmbridge \
--graphics none --console pty,target_type=serial \
--location 'http://us.archive.ubuntu.com/ubuntu/dists/jammy/main/installer-amd64/' \
--extra-args 'console=ttyS0,115200n8 serial'




# ============================================
# 8. USEFUL COMMANDS
# ============================================

# List all VMs
virsh list --all

# Start a VM
virsh start k3s-master

# Connect to VM console (Ctrl+] to exit)
virsh console k3s-master

# Stop VM gracefully
virsh shutdown k3s-master

# Force stop VM
virsh destroy k3s-master

# Delete VM (keeps disk)
virsh undefine k3s-master

# Get VM IP address (wait 30 sec after boot)
virsh domifaddr k3s-master

# Clone VM for workers
virt-clone --original k3s-master --name k3s-worker1 --auto-clone
virt-clone --original k3s-master --name k3s-worker2 --auto-clone



