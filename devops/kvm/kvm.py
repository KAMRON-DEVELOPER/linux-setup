#!/usr/bin/env python3
"""
KVM Cloud-Init VM Manager
Automates creation of VMs with cloud-init configuration
Updates: Added Paste SSH Key and Static IP support
"""

import argparse
import hashlib
import os
import shutil
import signal
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import FrameType
from typing import Any, NoReturn

import yaml


class VMManager:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir: Path = Path(base_dir or os.path.expanduser("~/.kvm"))
        self.images_dir: Path = self.base_dir / "images"
        self.vms_dir: Path = self.base_dir / "vms"
        self.templates_dir: Path = self.base_dir / "templates"
        self.seeds_dir: Path = self.base_dir / "seeds"
        self.keys_dir: Path = self.base_dir / "keys"

        # Cloud image sources
        self.cloud_images: dict[str, str] = {
            "ubuntu-20.04": "https://cloud-images.ubuntu.com/focal/current/focal-server-cloudimg-amd64.img",
            "ubuntu-22.04": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
            "ubuntu-24.04": "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img",
        }

        # Track created resources for cleanup
        self.vm_name: str | None = None
        self.created_resources: list[Path] = []

        # Setup signal handlers for cleanup
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum: int, frame: FrameType | None) -> NoReturn:
        """Handle Ctrl+C and cleanup"""
        print("\n\n⚠️  Interrupted! Cleaning up...")
        self._cleanup()
        print("❌ Aborted")
        sys.exit(1)

    def _cleanup(self) -> None:
        """Remove all created resources"""
        if self.vm_name:
            try:
                result: subprocess.CompletedProcess[str] = subprocess.run(
                    ["virsh", "list", "--all", "--name"],
                    capture_output=True,
                    text=True,
                )
                if self.vm_name in result.stdout:
                    print(f"  Destroying VM: {self.vm_name}")
                    subprocess.run(
                        ["virsh", "destroy", self.vm_name],
                        capture_output=True,
                        stderr=subprocess.DEVNULL,
                    )
                    subprocess.run(
                        ["virsh", "undefine", self.vm_name],
                        capture_output=True,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception:
                pass

        for resource in reversed(self.created_resources):
            try:
                if resource.exists():
                    if resource.is_dir():
                        print(f"  Removing directory: {resource}")
                        shutil.rmtree(resource)
                    else:
                        print(f"  Removing file: {resource}")
                        resource.unlink()
            except Exception as e:
                print(f"  Warning: Could not remove {resource}: {e}")

    def setup_directories(self) -> None:
        """Create directory structure"""
        for d in [
            self.images_dir,
            self.vms_dir,
            self.templates_dir,
            self.seeds_dir,
            self.keys_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory structure created at: {self.base_dir}")

    def _fix_libvirt_permissions(self) -> bool:
        """Fix permissions for libvirt-qemu user access"""
        print("\n🔐 Checking libvirt permissions...")
        home_dir = Path.home()
        base_path = self.base_dir

        try:
            base_path.relative_to(home_dir)
            needs_permission = True
        except ValueError:
            needs_permission = False

        if not needs_permission:
            print("✓ VM directory is not under home, permissions should be OK")
            return True

        print(f"⚠️  VM files are under home directory: {home_dir}")
        print("   This requires granting libvirt-qemu user access")
        print("\n📝 Permission options:")
        print("   1. Add execute permission to home directory (recommended)")
        print("   2. Change ownership of VM files to libvirt-qemu")
        print("   3. Use ACLs to grant specific access")
        print("   4. Skip and try anyway")

        choice = self._prompt("Choose option", "1")

        if choice == "1":
            try:
                subprocess.run(
                    ["chmod", "o+x", str(home_dir)], check=True, capture_output=True
                )
                subprocess.run(
                    ["chmod", "-R", "o+rX", str(self.base_dir)],
                    check=True,
                    capture_output=True,
                )
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to set permissions: {e}")
                return False
        elif choice == "4":
            return True
        return False

    def list_available_images(self) -> dict[str, str]:
        """List available cloud images"""
        print("\n📦 Available Cloud Images:")
        for i, (name, _) in enumerate(self.cloud_images.items(), 1):
            downloaded: bool = (self.images_dir / f"{name}.img").exists()
            status: str = "✓ Downloaded" if downloaded else "⬜ Not downloaded"
            print(f"  {i}. {name:20s} {status}")
        return self.cloud_images

    def download_image(self, distro: str) -> bool:
        """Download cloud image if not exists"""
        if distro not in self.cloud_images:
            print(f"❌ Unknown distro: {distro}")
            return False

        url: str = self.cloud_images[distro]
        img_path: Path = self.images_dir / f"{distro}.img"

        if img_path.exists():
            print(f"✓ Image already exists: {img_path}")
            return True

        print(f"⬇️  Downloading {distro} from {url}...")
        try:
            urllib.request.urlretrieve(url, img_path)
            print(f"✓ Downloaded: {img_path}")
            return True
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False

    def list_ssh_keys(self, ssh_dir: Path) -> list[tuple[str, Path]]:
        """List available SSH keys in directory"""
        keys: list[tuple[str, Path]] = []
        if not ssh_dir.exists():
            return keys

        for pub_key in ssh_dir.glob("*.pub"):
            key_name: str = pub_key.stem
            private_key: Path = ssh_dir / key_name
            if private_key.exists():
                keys.append((key_name, private_key))
        return keys

    def generate_ssh_key(self, key_name: str, key_dir: Path) -> str:
        """Generate SSH key pair"""
        key_path: Path = key_dir / key_name

        if key_path.exists():
            with open(f"{key_path}.pub", "r") as f:
                return f.read().strip()

        print(f"🔑 Generating SSH key: {key_path}")
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "ed25519",
                "-f",
                str(key_path),
                "-N",
                "",
                "-C",
                key_name,
            ],
            check=True,
            capture_output=True,
        )
        self.created_resources.append(key_path)
        self.created_resources.append(Path(f"{key_path}.pub"))

        with open(f"{key_path}.pub", "r") as f:
            return f.read().strip()

    def create_user_data(self, config: dict[str, Any]) -> str:
        """Generate user-data using YAML"""
        ssh_keys: list[str] = config.get("ssh_keys", [])

        user_data: dict[str, Any] = {
            "preserve_hostname": False,
            "hostname": config["hostname"],
            "users": [
                {
                    "name": config["username"],
                    "groups": ["sudo"],
                    "shell": "/bin/bash",
                    "sudo": ["ALL=(ALL) NOPASSWD:ALL"],
                }
            ],
            "ssh_pwauth": config.get("ssh_password_auth", True),
            "disable_root": False,
            "chpasswd": {
                "list": f"{config['username']}:{config['password']}",
                "expire": False,
            },
            "package_update": True,
            "package_upgrade": config.get("auto_upgrade", False),
            "packages": ["curl", "vim", "qemu-guest-agent", "net-tools"],
            "runcmd": [
                ["systemctl", "enable", "--now", "qemu-guest-agent"],
            ],
            "final_message": f"VM {config['hostname']} is ready!",
        }

        if ssh_keys:
            user_data["users"][0]["ssh_authorized_keys"] = ssh_keys

        return "#cloud-config\n" + yaml.dump(
            user_data, default_flow_style=False, sort_keys=False
        )

    def create_meta_data(self, instance_id: str, hostname: str) -> str:
        """Generate meta-data using YAML"""
        meta_data: dict[str, Any] = {
            "instance-id": instance_id,
            "local-hostname": hostname,
        }
        return yaml.dump(meta_data, default_flow_style=False, sort_keys=False)

    def get_hostname_and_ip(self) -> tuple[str, str]:
        try:
            hostname: str = socket.gethostname()
            ip_address: str = socket.gethostbyname(hostname)
            return hostname, ip_address
        except socket.error as e:
            raise Exception(f"Error getting IP address: {e}")

    def create_network_config(self, config: dict[str, Any]) -> str:
        """Generate network-config YAML (Netplan V2)"""
        interface: str = config.get("network_interface", "enp1s0")
        ip_mode: str = config.get("ip_mode", "dhcp")  # dhcp or static
        
        ethernet_config: dict[str, Any] = {}

        if ip_mode == "static":
            # Static IP Configuration
            static_ip = config.get("static_ip")
            gateway = config.get("static_gateway")
            dns_servers = config.get("dns_servers", ["1.1.1.1", "8.8.8.8"])

            ethernet_config = {
                "dhcp4": False,
                "addresses": [static_ip],
                "nameservers": {
                    "addresses": dns_servers
                }
            }
            
            # Use 'routes' instead of 'gateway4' (deprecated in newer Netplan)
            if gateway:
                ethernet_config["routes"] = [
                    {"to": "default", "via": gateway}
                ]
        else:
            # DHCP Configuration
            ethernet_config = {"dhcp4": True}
            
            dns_option: str = config.get("dns_option", "default")
            
            if dns_option == "host":
                _, host_ip = self.get_hostname_and_ip()
                ethernet_config["dhcp4-overrides"] = {"use-dns": False}
                ethernet_config["nameservers"] = {"addresses": [host_ip, "1.1.1.1"]}
            elif dns_option == "custom":
                dns_servers = config.get("dns_servers", ["1.1.1.1", "8.8.8.8"])
                ethernet_config["dhcp4-overrides"] = {"use-dns": False}
                ethernet_config["nameservers"] = {"addresses": dns_servers}

        network_config: dict[str, Any] = {
            "version": 2,
            "ethernets": {
                interface: ethernet_config
            },
        }

        return yaml.dump(network_config, default_flow_style=False, sort_keys=False)

    def create_cloud_init_iso(self, vm_name: str, config: dict[str, Any]) -> Path:
        """Create cloud-init seed ISO"""
        vm_seed_dir: Path = self.seeds_dir / vm_name
        vm_seed_dir.mkdir(parents=True, exist_ok=True)
        self.created_resources.append(vm_seed_dir)

        user_data_path: Path = vm_seed_dir / "user-data"
        meta_data_path: Path = vm_seed_dir / "meta-data"
        network_config_path: Path = vm_seed_dir / "network-config"

        user_data_path.write_text(self.create_user_data(config))
        meta_data_path.write_text(
            self.create_meta_data(config["instance_id"], config["hostname"])
        )
        network_config_path.write_text(self.create_network_config(config))

        seed_iso: Path = self.seeds_dir / f"{vm_name}-seed.iso"
        cmd: list[str] = [
            "cloud-localds",
            "--network-config",
            str(network_config_path),
            str(seed_iso),
            str(user_data_path),
            str(meta_data_path),
        ]

        print(f"🔧 Creating cloud-init ISO: {seed_iso}")
        subprocess.run(cmd, check=True, capture_output=True)
        self.created_resources.append(seed_iso)
        return seed_iso

    def create_vm_disk(self, vm_name: str, base_image: str, size: str = "20G") -> Path:
        """Create VM disk with backing image"""
        vm_disk: Path = self.vms_dir / f"{vm_name}.qcow2"
        base_img_path: Path = self.images_dir / f"{base_image}.img"

        if not base_img_path.exists():
            raise FileNotFoundError(f"Base image not found: {base_img_path}")

        cmd: list[str] = [
            "qemu-img",
            "create",
            "-f",
            "qcow2",
            "-F",
            "qcow2",
            "-b",
            str(base_img_path),
            str(vm_disk),
            size,
        ]

        print(f"💾 Creating VM disk: {vm_disk} (size: {size})")
        subprocess.run(cmd, check=True, capture_output=True)
        self.created_resources.append(vm_disk)
        return vm_disk

    def create_vm(self, config: dict[str, Any]) -> None:
        """Create and start VM"""
        vm_name: str = config["vm_name"]
        self.vm_name = vm_name

        vm_disk: Path = self.create_vm_disk(
            vm_name, config["base_image"], config.get("disk_size", "20G")
        )
        seed_iso: Path = self.create_cloud_init_iso(vm_name, config)

        cmd: list[str] = [
            "sudo",
            "virt-install",
            "--name",
            vm_name,
            "--memory",
            str(config.get("memory", 2048)),
            "--vcpus",
            str(config.get("vcpus", 2)),
            "--disk",
            f"path={vm_disk},format=qcow2,bus=virtio",
            "--disk",
            f"path={seed_iso},device=cdrom",
            "--os-variant",
            config.get("os_variant", "ubuntu22.04"),
            "--import",
            "--network",
            f"network={config.get('network', 'default')},model=virtio",
            "--graphics",
            "none",
            "--noautoconsole",
        ]

        print(f"🚀 Creating VM: {vm_name}")
        subprocess.run(cmd, check=True)
        print(f"✓ VM created successfully: {vm_name}")
        self.created_resources.clear()
        self.vm_name = None

    def _prompt(self, message: str, default: str = "") -> str:
        if default:
            user_input: str = input(f"{message} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{message}: ").strip()

    def interactive_create(self) -> None:
        """Interactive VM creation"""
        print("\n" + "=" * 60)
        print("  KVM Cloud-Init VM Creator (Updated)")
        print("=" * 60)

        try:
            images: dict[str, str] = self.list_available_images()
            print("\n🔥 Select base image:")
            default_distro: str = "ubuntu-22.04"
            img_choice: str = self._prompt(
                "Enter number or distro name", default_distro
            )

            if img_choice.isdigit():
                distro_list: list[str] = list(images.keys())
                idx: int = int(img_choice) - 1
                if 0 <= idx < len(distro_list):
                    distro: str = distro_list[idx]
                else:
                    print("❌ Invalid number")
                    return
            else:
                distro = img_choice

            if distro not in images:
                print("❌ Invalid selection")
                return

            if not self.download_image(distro):
                return

            print("\n🖥️  VM Configuration:")
            vm_name: str = self._prompt("VM name", "test-vm")
            hostname: str = self._prompt("Hostname", vm_name)
            instance_id: str = (
                f"{vm_name}-{hashlib.md5(vm_name.encode()).hexdigest()[:8]}"
            )
            username: str = self._prompt("Username", "ubuntu")
            password: str = self._prompt("Password", "ubuntu")

            # --- SSH Logic Updated ---
            print("\n🔑 SSH Key Configuration:")
            ssh_dir: Path = Path.home() / ".ssh"
            available_keys: list[tuple[str, Path]] = self.list_ssh_keys(ssh_dir)
            
            # Build menu options
            print("  Available options:")
            opt_idx = 1
            if available_keys:
                for key_name, _ in available_keys:
                    print(f"    {opt_idx}. Use existing: {key_name}")
                    opt_idx += 1
            
            create_new_idx = opt_idx
            print(f"    {create_new_idx}. Create new key pair")
            opt_idx += 1
            
            paste_key_idx = opt_idx
            print(f"    {paste_key_idx}. Paste public key string")
            opt_idx += 1
            
            skip_idx = opt_idx
            print(f"    {skip_idx}. Skip SSH key")

            key_choice: str = self._prompt("Choice", "1")
            ssh_keys: list[str] = []
            key_path: Path | None = None

            if key_choice.isdigit():
                choice = int(key_choice)
                
                # Option: Use Existing
                if 1 <= choice <= len(available_keys):
                    key_name, key_path = available_keys[choice - 1]
                    with open(f"{key_path}.pub", "r") as f:
                        ssh_keys = [f.read().strip()]
                    print(f"✓ Using key: {key_name}")
                
                # Option: Create New
                elif choice == create_new_idx:
                    new_key_name = self._prompt("Key name", f"{vm_name}_id_ed25519")
                    key_path = ssh_dir / new_key_name
                    ssh_keys = [self.generate_ssh_key(new_key_name, ssh_dir)]
                    print(f"✓ Key saved to: {key_path}")
                
                # Option: Paste Key
                elif choice == paste_key_idx:
                    print("\n📋 Paste your public key below (ssh-rsa... or ssh-ed25519...):")
                    raw_key = input("Key: ").strip()
                    if raw_key:
                        ssh_keys = [raw_key]
                        print("✓ Key accepted")
                    else:
                        print("⚠️  No key pasted, skipping.")
                
                # Option: Skip
                elif choice == skip_idx:
                    print("⚠️  Skipping SSH key")

            # --- Network Configuration ---
            print("\n🔌 Network Configuration:")
            interface: str = self._prompt("Interface name", "enp1s0")

            print("\n🌐 IP Assignment:")
            print("  1. DHCP (Dynamic IP)")
            print("  2. Static IP")
            ip_mode_choice = self._prompt("Choice", "1")
            
            ip_mode = "dhcp"
            static_ip = ""
            static_gateway = ""
            dns_servers: list[str] = []
            dns_option = "default"

            if ip_mode_choice == "2":
                ip_mode = "static"
                print("\n📝 Static IP Settings:")
                static_ip = self._prompt("IP Address (CIDR format, e.g., 192.168.122.50/24)")
                static_gateway = self._prompt("Gateway (e.g., 192.168.122.1)")
                
                dns_input = self._prompt("DNS servers", "1.1.1.1, 8.8.8.8")
                dns_servers = [ip.strip() for ip in dns_input.split(",")]
            else:
                # DHCP Options
                print("  DNS Options for DHCP:")
                print("    1. Default (DHCP provided)")
                print("    2. Host machine as DNS")
                print("    3. Custom DNS")
                dns_sub_choice = self._prompt("Choice", "1")
                
                if dns_sub_choice == "2":
                    dns_option = "host"
                elif dns_sub_choice == "3":
                    dns_option = "custom"
                    dns_input = self._prompt("DNS servers", "1.1.1.1, 8.8.8.8")
                    dns_servers = [ip.strip() for ip in dns_input.split(",")]

            # Resources
            print("\n⚙️  Resources:")
            memory_str: str = self._prompt("Memory (MB)", "2048")
            vcpus_str: str = self._prompt("vCPUs", "2")
            disk_size: str = self._prompt("Disk size", "20G")
            
            # Network Selection
            try:
                result = subprocess.run(["virsh", "net-list", "--all"], capture_output=True, text=True)
                print(f"\n🌐 Available libvirt networks:\n{result.stdout}")
            except:
                pass
            network: str = self._prompt("Network", "default")

            config: dict[str, Any] = {
                "vm_name": vm_name,
                "hostname": hostname,
                "instance_id": instance_id,
                "username": username,
                "password": password,
                "ssh_keys": ssh_keys,
                "base_image": distro,
                "memory": int(memory_str),
                "vcpus": int(vcpus_str),
                "disk_size": disk_size,
                "network": network,
                "network_interface": interface,
                "os_variant": "ubuntu22.04" if "22.04" in distro else "ubuntu20.04",
                "ip_mode": ip_mode,
                "static_ip": static_ip,
                "static_gateway": static_gateway,
                "dns_option": dns_option,
                "dns_servers": dns_servers,
            }

            print("\n📋 Configuration Summary:")
            print(f"  VM Name: {vm_name} ({hostname})")
            print(f"  IP Mode: {ip_mode.upper()}")
            if ip_mode == "static":
                print(f"  Static IP: {static_ip}")
                print(f"  Gateway:   {static_gateway}")
            confirm: str = self._prompt("\n✓ Create VM? [y/N]", "y")
            
            if confirm.lower() == "y":
                if not self._fix_libvirt_permissions():
                    if self._prompt("Continue anyway? [y/N]", "n").lower() != "y":
                        self._cleanup()
                        return

                self.create_vm(config)
                print(f"\n✅ VM '{vm_name}' created successfully!")
                if ip_mode == "static":
                     print(f"Connect with: ssh {username}@{static_ip.split('/')[0]}")
                else:
                     print(f"Connect with: ssh {username}@<vm-ip>")
            else:
                self._cleanup()

        except KeyboardInterrupt:
            self._cleanup()
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            self._cleanup()
            raise

def main() -> None:
    parser = argparse.ArgumentParser(description="KVM Cloud-Init VM Manager")
    parser.add_argument("--base-dir", help="Base directory for VM files")
    parser.add_argument("--setup", action="store_true", help="Setup directory structure")
    parser.add_argument("--list-images", action="store_true", help="List available images")
    parser.add_argument("--download", help="Download specific image")
    args = parser.parse_args()

    manager = VMManager(args.base_dir)

    if args.setup:
        manager.setup_directories()
    elif args.list_images:
        manager.list_available_images()
    elif args.download:
        manager.download_image(args.download)
    else:
        manager.setup_directories()
        manager.interactive_create()

if __name__ == "__main__":
    main()