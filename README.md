# Arch setup with Gnome and Hyprland

This is very minimal setup.

## Package Installations

Commands:

```bash
sudo pacman -S gnome-shell gdm gnome-control-center gnome-tweaks \
  extension-manager firefox telegram-desktop zed evince eog \
  ttf-jetbrains-mono-nerd ttf-hack-nerd ttf-meslo-nerd noto-fonts-emoji
```

Start gdm service:

```bash
sudo systemctl enable –now gdm.service
```

If you want to just start the gnome on demand:

```bash
sudo systemctl set-default multi-user.target
sudo systemctl start gdm
sudo systemctl stop gdm
```

## Docker on Arch Linux

[Docker Arch Wiki](https://wiki.archlinux.org/title/Docker)

```bash
sudo pacman -S docker docker-compose docker-buildx
sudo systemctl enable --now docker.service
sudo usermod -aG docker $USER
newgrp docker
```

verify the status:

```bash
docker info
```

### Configure Docker to use the Helper

[GNOME/Keyring](https://wiki.archlinux.org/title/GNOME/Keyring)

```bash
sudo pacman -S gnome-keyring seahorse
yay -S docker-credential-secretservice
```

Initialize the Default Keyring

Because you need to generate setup credentials from scratch, gnome-keyring won't
work out-of-the-box until a default vault exists for it to store things in.

* Launch `seahorse` (usually appears as Passwords and Keys in your application launcher).
* Click the `+` button in the top left (or **File** > **New**) and select **Password Keyring**.
* Name the new keyring `login` (lowercase). This is the standard naming convention.
* **Important**: When prompted for a password, enter your **current Linux user password**.
  This ensures that if you are using a display manager (like SDDM, GDM, or greetd/tuigreet with PAM),
  the keyring will unlock automatically when you log into your system.
* Once created, right-click the new `login` keyring in the sidebar and select **Set as Default**.

#### Start the Keyring Daemon in Hyprland

If you boot directly from a TTY or your login manager doesn't initialize DBus
secret components automatically, you need to tell Hyprland to start the daemon
so the Secret Service API is available to Docker.

Add this line to your `~/.config/hyprland/hyprland.conf`:

```conf
exec-once = gnome-keyring-daemon --start --components=secrets
```

#### Configure Docker

Now you need to tell Docker to route its credential management to the
Secret Service API rather than defaulting to pass or a plain-text file.

Edit or create your Docker config file at `~/.docker/config.json`:

```json
{
  "credsStore": "secretservice"
}
```

*(Docker will automatically prefix this value with docker-credential- and execute
the docker-credential-secretservice binary under the hood).*

#### Verify the Setup

Test your configuration by authenticating with Docker:

```bash
docker login
```

## Yay setup

[Follow the instruction on Github$](https://github.com/jguer/yay)

```bash
sudo pacman -S --needed git base-devel && \
  git clone https://aur.archlinux.org/yay-bin.git && cd yay-bin && makepkg -si
```

```bash
yay -S visual-studio-code-bin visual-studio-code-insiders-bin
```

## INSTALLS

```bash
yay -S aaa
sudo pacman -S aaa

```
