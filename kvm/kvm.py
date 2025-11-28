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
from types import FrameType
import urllib.request
from pathlib import Path
from typing import Any

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

    def _signal_handler(self, signum: int, frame: FrameType | None) -> None:
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
                result = subprocess.run(
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

    def list_available_images(self) -> dict[str, str]:
        """List available cloud images"""
        print("\n📦 Available Cloud Images:")
        for i, (name, _) in enumerate(self.cloud_images.items(), 1):
            downloaded: bool = (self.images_dir / f"{name}.img").exists()
            status: str = "✓ Downloaded" if downloaded else "⚬ Not downloaded"
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

    def generate_ssh_key(self, key_path: Path) -> str:
        """Generate SSH key pair"""
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
                "kvm-vm-key",
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
        """Generate user-data YAML"""
        ssh_keys: list[str] = config.get("ssh_keys", [])

        user_data = f"""
        #cloud-config
        preserve_hostname: false
        hostname: {config["hostname"]}
        users:
        - name: {config["username"]}
            groups: ["sudo"]
            shell: /bin/bash
            sudo: ["ALL=(ALL) NOPASSWD:ALL"]
        """

        if ssh_keys:
            user_data += "\n    ssh_authorized_keys:\n"
            for key in ssh_keys:
                user_data += f"      - {key}\n"

        user_data += f"""
        ssh_pwauth: {str(config.get("ssh_password_auth", True)).lower()}
        disable_root: false
        chpasswd:
        list: |
            {config["username"]}:{config["password"]}
        expire: false

        package_update: true
        package_upgrade: {str(config.get("auto_upgrade", True)).lower()}
        package_reboot_if_required: true
        packages:
        - curl
        - vim
        - qemu-guest-agent
        - net-tools

        runcmd:
        - [systemctl, enable, --now, qemu-guest-agent]

        final_message: "VM {config["hostname"]} is ready!"
        """
        return user_data

    def create_meta_data(self, instance_id: str, hostname: str) -> str:
        """Generate meta-data YAML"""
        return f"""
        instance-id: {instance_id}
        local-hostname: {hostname}
        """

    def get_hostname_and_ip(self) -> tuple[str, str]:
        """Retrieves the hostname & local IP address of the machine."""
        try:
            hostname: str = socket.gethostname()
            ip_address: str = socket.gethostbyname(hostname)
            return hostname, ip_address
        except socket.error as e:
            raise Exception(f"Error getting IP address: {e}")

    def create_network_config(self, config: dict[str, Any]) -> str:
        """Generate network-config YAML"""
        interface: str = config.get("network_interface", "enp1s0")

        data: dict[str, Any] = {
            "version": 2,
            "ethernets": {
                interface: {
                    "dhcp4": True,
                }
            },
        }

        return yaml.dump(data, sort_keys=False)

    def create_network_config_with_static_dns(
        self, config: dict[str, Any], static_dns_addr: str
    ) -> str:
        """Generate network-config YAML"""
        dns_servers: list[str] = config.get("dns_servers", [static_dns_addr, "1.1.1.1"])

        data: dict[str, Any] = {
            "version": 2,
            "ethernets": {
                "nic0": {
                    "match": {"driver": "virtio"},
                    "set-name": "nic0",
                    "dhcp4": True,
                    "dhcp4-overrides": {"use-dns": False},
                    "nameservers": {"addresses": dns_servers},
                }
            },
        }

        return yaml.dump(data, sort_keys=False)

        # def create_network_config_with_static_dns(self, config: dict[str, Any]) -> str:
        #     """Generate network-config YAML"""
        #     interface = config.get("network_interface", "enp1s0")
        #     dns_servers = config.get("dns_servers", ["192.168.31.247", "1.1.1.1"])

        #     data = {
        #         "version": 2,
        #         "ethernets": {
        #             interface: {
        #                 "dhcp4": True,
        #                 "dhcp4-overrides": {
        #                     "use-dns": False,
        #                 },
        #                 "nameservers": {"addresses": dns_servers},
        #             }
        #         },
        #     }

        return yaml.dump(data, sort_keys=False)

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
            print("\n📥 Select base image:")

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

            # SSH key
            print("\n🔑 SSH Key Configuration:")
            print("  1. Generate new key")
            print("  2. Use existing key")
            print("  3. Skip SSH key")
            key_choice: str = self._prompt("Choice", "1")

            ssh_keys: list[str] = []
            key_path: Path | None = None

            if key_choice == "1":
                key_path = self.keys_dir / f"{vm_name}_id_ed25519"
                ssh_keys = [self.generate_ssh_key(key_path)]
                print(f"✓ Key saved to: {key_path}")
            elif key_choice == "2":
                default_key: str = "~/.ssh/id_ed25519.pub"
                key_file: str = self._prompt("Path to public key", default_key)
                with open(os.path.expanduser(key_file), "r") as f:
                    ssh_keys = [f.read().strip()]

            # Resources
            print("\n⚙️  Resources:")
            memory_str: str = self._prompt("Memory (MB)", "2048")
            vcpus_str: str = self._prompt("vCPUs", "2")
            disk_size: str = self._prompt("Disk size", "20G")

            # Network
            result = subprocess.run(
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
                "os_variant": "ubuntu22.04" if "22.04" in distro else "ubuntu20.04",
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

            confirm: str = self._prompt("\n✓ Create VM? [y/N]", "y")
            if confirm.lower() == "y":
                self.create_vm(config)
                print(f"\n✅ VM '{vm_name}' created successfully!")
                print(f"\nConnect with: ssh {username}@<vm-ip>")
                if key_choice == "1" and key_path:
                    print(f"Using key: ssh -i {key_path} {username}@<vm-ip>")
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
    parser = argparse.ArgumentParser(description="KVM Cloud-Init VM Manager")
    parser.add_argument("--base-dir", help="Base directory for VM files")
    parser.add_argument(
        "--setup", action="store_true", help="Setup directory structure"
    )
    parser.add_argument(
        "--list-images", action="store_true", help="List available images"
    )
    parser.add_argument("--download", help="Download specific image")

    args = parser.parse_args()

    manager = VMManager(args.base_dir)

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
