#!/usr/bin/env python3
"""
KVM Cloud-Init VM Manager
Automates creation of VMs with cloud-init configuration
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
        # Delete VM if it was created
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

        # Delete created files
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

        # Get the path that needs permissions (usually home directory)
        home_dir = Path.home()
        base_path = self.base_dir

        # Check if base_dir is under home
        try:
            base_path.relative_to(home_dir)
            needs_permission = True
        except ValueError:
            # Not under home directory, might not need permission fix
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
            # Add execute permission to home directory
            print(f"\n🔧 Adding execute permission to: {home_dir}")
            print("   Running: chmod o+x ~")
            try:
                subprocess.run(
                    ["chmod", "o+x", str(home_dir)], check=True, capture_output=True
                )
                # Also ensure the .kvm directory is readable
                subprocess.run(
                    ["chmod", "-R", "o+rX", str(self.base_dir)],
                    check=True,
                    capture_output=True,
                )
                print("✓ Permissions updated successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to set permissions: {e}")
                return False

        elif choice == "2":
            # Change ownership
            print("\n🔧 Changing ownership of VM files to libvirt-qemu")
            try:
                # Get libvirt-qemu UID and GID
                result = subprocess.run(
                    ["id", "-u", "libvirt-qemu"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                qemu_uid = result.stdout.strip()

                result = subprocess.run(
                    ["id", "-g", "libvirt-qemu"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                qemu_gid = result.stdout.strip()

                # Change ownership of the base directory
                subprocess.run(
                    [
                        "sudo",
                        "chown",
                        "-R",
                        f"{qemu_uid}:{qemu_gid}",
                        str(self.base_dir),
                    ],
                    check=True,
                    capture_output=True,
                )
                print("✓ Ownership changed successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to change ownership: {e}")
                return False

        elif choice == "3":
            # Use ACLs
            print("\n🔧 Setting ACLs for libvirt-qemu user")
            try:
                # Check if setfacl is available
                subprocess.run(["which", "setfacl"], check=True, capture_output=True)

                # Set ACL on home directory
                subprocess.run(
                    ["setfacl", "-m", "u:libvirt-qemu:x", str(home_dir)],
                    check=True,
                    capture_output=True,
                )

                # Set ACL on .kvm directory recursively
                subprocess.run(
                    ["setfacl", "-R", "-m", "u:libvirt-qemu:rX", str(self.base_dir)],
                    check=True,
                    capture_output=True,
                )

                # Set default ACL for new files
                subprocess.run(
                    [
                        "setfacl",
                        "-R",
                        "-d",
                        "-m",
                        "u:libvirt-qemu:rX",
                        str(self.base_dir),
                    ],
                    check=True,
                    capture_output=True,
                )

                print("✓ ACLs set successfully")
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to set ACLs: {e}")
                print("   Make sure 'acl' package is installed")
                return False

        elif choice == "4":
            print("⚠️  Skipping permission fix, attempting to create VM anyway...")
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

        # Track for cleanup
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
            "package_upgrade": config.get("auto_upgrade", True),
            "package_reboot_if_required": True,
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
        """Retrieves the hostname & local IP address of the machine."""
        try:
            hostname: str = socket.gethostname()
            ip_address: str = socket.gethostbyname(hostname)
            return hostname, ip_address
        except socket.error as e:
            raise Exception(f"Error getting IP address: {e}")

    def create_network_config(self, config: dict[str, Any]) -> str:
        """Generate network-config YAML with DNS options"""
        dns_option: str = config.get("dns_option", "default")
        interface: str = config.get("network_interface", "enp1s0")

        network_config: dict[str, Any] = {
            "version": 2,
            "ethernets": {
                interface: {
                    "dhcp4": True,
                }
            },
        }

        # Configure DNS based on user choice
        if dns_option == "host":
            # Use host machine's DNS
            _, host_ip = self.get_hostname_and_ip()
            network_config["ethernets"][interface]["dhcp4-overrides"] = {
                "use-dns": False
            }
            network_config["ethernets"][interface]["nameservers"] = {
                "addresses": [host_ip, "1.1.1.1"]
            }
        elif dns_option == "custom":
            # Use custom DNS servers
            dns_servers: list[str] = config.get("dns_servers", ["1.1.1.1", "8.8.8.8"])
            network_config["ethernets"][interface]["dhcp4-overrides"] = {
                "use-dns": False
            }
            network_config["ethernets"][interface]["nameservers"] = {
                "addresses": dns_servers
            }
        # else: dns_option == "default" - use DHCP provided DNS (no override)

        return yaml.dump(network_config, default_flow_style=False, sort_keys=False)

    def create_cloud_init_iso(self, vm_name: str, config: dict[str, Any]) -> Path:
        """Create cloud-init seed ISO"""
        vm_seed_dir: Path = self.seeds_dir / vm_name
        vm_seed_dir.mkdir(parents=True, exist_ok=True)
        self.created_resources.append(vm_seed_dir)

        # Write cloud-init files
        user_data_path: Path = vm_seed_dir / "user-data"
        meta_data_path: Path = vm_seed_dir / "meta-data"
        network_config_path: Path = vm_seed_dir / "network-config"

        user_data_path.write_text(self.create_user_data(config))
        meta_data_path.write_text(
            self.create_meta_data(config["instance_id"], config["hostname"])
        )
        network_config_path.write_text(self.create_network_config(config))

        # Generate ISO
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

        # Create disk and seed
        vm_disk: Path = self.create_vm_disk(
            vm_name, config["base_image"], config.get("disk_size", "20G")
        )
        seed_iso: Path = self.create_cloud_init_iso(vm_name, config)

        # Build virt-install command
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

        # Clear cleanup list on success
        self.created_resources.clear()
        self.vm_name = None

    def _prompt(self, message: str, default: str = "") -> str:
        """Prompt user with default value"""
        if default:
            user_input: str = input(f"{message} [{default}]: ").strip()
            return user_input if user_input else default
        else:
            return input(f"{message}: ").strip()

    def interactive_create(self) -> None:
        """Interactive VM creation"""
        print("\n" + "=" * 60)
        print("  KVM Cloud-Init VM Creator")
        print("=" * 60)
        print("  (Press Ctrl+C anytime to abort and cleanup)")
        print("=" * 60)

        try:
            # List and select image
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

            # Download if needed
            if not self.download_image(distro):
                return

            # Collect VM details
            print("\n🖥️  VM Configuration:")
            default_vm_name: str = "test-vm"
            vm_name: str = self._prompt("VM name", default_vm_name)

            hostname: str = self._prompt("Hostname", vm_name)
            instance_id: str = (
                f"{vm_name}-{hashlib.md5(vm_name.encode()).hexdigest()[:8]}"
            )

            username: str = self._prompt("Username", "ubuntu")
            password: str = self._prompt("Password", "ubuntu")

            # SSH key configuration
            print("\n🔑 SSH Key Configuration:")
            ssh_dir: Path = Path.home() / ".ssh"
            available_keys: list[tuple[str, Path]] = self.list_ssh_keys(ssh_dir)

            if available_keys:
                print("  Available SSH keys in ~/.ssh:")
                for i, (key_name, _) in enumerate(available_keys, 1):
                    print(f"    {i}. {key_name}")
                print(f"    {len(available_keys) + 1}. Create new key")
                print(f"    {len(available_keys) + 2}. Skip SSH key")
                default_choice: str = "1"
            else:
                print("  No SSH keys found in ~/.ssh")
                print("    1. Create new key")
                print("    2. Skip SSH key")
                default_choice = "1"

            key_choice: str = self._prompt("Choice", default_choice)

            ssh_keys: list[str] = []
            key_path: Path | None = None

            if available_keys and key_choice.isdigit():
                choice_num: int = int(key_choice)
                if 1 <= choice_num <= len(available_keys):
                    # Use existing key
                    key_name: str
                    key_name, key_path = available_keys[choice_num - 1]
                    with open(f"{key_path}.pub", "r") as f:
                        ssh_keys = [f.read().strip()]
                    print(f"✓ Using key: {key_name}")
                elif choice_num == len(available_keys) + 1:
                    # Create new key
                    new_key_name: str = self._prompt(
                        "Key name", f"{vm_name}_id_ed25519"
                    )
                    key_path = ssh_dir / new_key_name
                    ssh_keys = [self.generate_ssh_key(new_key_name, ssh_dir)]
                    print(f"✓ Key saved to: {key_path}")
            elif not available_keys and key_choice == "1":
                # Create new key
                new_key_name = self._prompt("Key name", f"{vm_name}_id_ed25519")
                key_path = ssh_dir / new_key_name
                ssh_keys = [self.generate_ssh_key(new_key_name, ssh_dir)]
                print(f"✓ Key saved to: {key_path}")

            # Network interface configuration
            print("\n🔌 Network Interface:")
            print("  Common interface names:")
            print("    - enp1s0 (default for KVM VMs)")
            print("    - eth0 (older naming)")
            print("    - ens3 (some configurations)")
            interface: str = self._prompt("Interface name", "enp1s0")

            # DNS Configuration
            print("\n🌐 DNS Configuration:")
            print("  1. Use DHCP provided DNS (default)")
            print("  2. Use host machine as DNS server")
            print("  3. Use custom DNS servers")
            dns_choice: str = self._prompt("Choice", "1")

            host_ip: str | None = None
            dns_option: str = "default"
            dns_servers: list[str] = []

            if dns_choice == "2":
                dns_option = "host"
                _, host_ip = self.get_hostname_and_ip()
                print(f"  ✓ Will use host DNS: {host_ip}")
            elif dns_choice == "3":
                dns_option = "custom"
                dns_input: str = self._prompt(
                    "DNS servers (comma-separated)", "1.1.1.1,8.8.8.8"
                )
                dns_servers = [ip.strip() for ip in dns_input.split(",")]
                print(f"  ✓ Will use DNS: {', '.join(dns_servers)}")

            # Resources
            print("\n⚙️  Resources:")
            memory_str: str = self._prompt("Memory (MB)", "2048")
            vcpus_str: str = self._prompt("vCPUs", "2")
            disk_size: str = self._prompt("Disk size", "20G")

            # Network
            result: subprocess.CompletedProcess[str] = subprocess.run(
                ["virsh", "net-list", "--all"], capture_output=True, text=True
            )
            print(f"\n🌐 Available networks:\n{result.stdout}")
            network: str = self._prompt("Network", "default")

            # Create VM config
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
                "dns_option": dns_option,
                "dns_servers": dns_servers,
            }

            # Confirm
            print("\n📋 Configuration Summary:")
            print(f"  VM Name: {vm_name}")
            print(f"  Base Image: {distro}")
            print(
                f"  Resources: {memory_str}MB RAM, {vcpus_str} vCPUs, {disk_size} disk"
            )
            print(f"  User: {username}")
            print(f"  Network: {network}")
            print(f"  Interface: {interface}")
            if dns_option == "host" and host_ip:
                print(f"  DNS: Host machine ({host_ip})")
            elif dns_option == "custom":
                print(f"  DNS: {', '.join(dns_servers)}")
            else:
                print("  DNS: DHCP provided")

            confirm: str = self._prompt("\n✓ Create VM? [y/N]", "y")
            if confirm.lower() == "y":
                # Fix permissions before creating VM
                if not self._fix_libvirt_permissions():
                    print(
                        "\n⚠️  Permission setup failed. You may encounter access errors."
                    )
                    retry = self._prompt("Continue anyway? [y/N]", "n")
                    if retry.lower() != "y":
                        print("❌ Cancelled")
                        self._cleanup()
                        return

                self.create_vm(config)
                print(f"\n✅ VM '{vm_name}' created successfully!")
                print(f"\nConnect with: ssh {username}@<vm-ip>")
                if key_path:
                    print(f"Using key: ssh -i {key_path} {username}@<vm-ip>")

                print("\n⏳ Waiting for VM to boot and configure (30-60 seconds)...")
                print(
                    "💡 To get VM IP: virsh domifaddr --domain {vm_name} --source agent"
                )
                print("💡 Or check DHCP leases on your bridge network")
            else:
                print("❌ Cancelled")
                self._cleanup()

        except KeyboardInterrupt:
            # This is handled by signal handler but just in case
            print("\n\n⚠️  Interrupted! Cleaning up...")
            self._cleanup()
            print("❌ Aborted")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Error: {e}")
            self._cleanup()
            raise


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="KVM Cloud-Init VM Manager"
    )
    parser.add_argument("--base-dir", help="Base directory for VM files")
    parser.add_argument(
        "--setup", action="store_true", help="Setup directory structure"
    )
    parser.add_argument(
        "--list-images", action="store_true", help="List available images"
    )
    parser.add_argument("--download", help="Download specific image")

    args: argparse.Namespace = parser.parse_args()

    manager: VMManager = VMManager(args.base_dir)

    if args.setup:
        manager.setup_directories()
        return

    if args.list_images:
        manager.list_available_images()
        return

    if args.download:
        manager.download_image(args.download)
        return

    # Default: interactive mode
    manager.setup_directories()
    manager.interactive_create()


if __name__ == "__main__":
    main()
