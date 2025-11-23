# My Dotfiles

Personal dotfiles for Arch Linux with Hyprland, managed with [GNU Stow](https://www.gnu.org/software/stow/).

## What's Included

| Package | Contents |
|---------|----------|
| `config` | alacritty, hypr, nvim, wallust, waybar, waypaper, wofi |
| `local` | Fonts (JetBrainsMono, FiraCode, CascadiaCode, Hack, etc.) |
| `tmux` | tmux configuration |
| `zsh` | zsh configuration |
| `meta` | Package lists for backup/restore |

## Installation

### Prerequisites

```bash
sudo pacman -S stow git
```

### Clone and Stow

```bash
git clone https://github.com/YOUR_USERNAME/my-dotfiles.git ~/Documents/my-dotfiles
cd ~/Documents/my-dotfiles

# Stow all packages
stow -v -t ~ config
stow -v -t ~ local
stow -v -t ~ tmux
stow -v -t ~ zsh

# Refresh font cache
fc-cache -fv
```

### Handling Conflicts

If you have existing configs, back them up first:

```bash
mv ~/.config/nvim ~/.config/nvim.backup
mv ~/.zshrc ~/.zshrc.backup
# Then stow again
```

## Restoring Packages

```bash
# Official packages
sudo pacman -S --needed - < meta/packages.txt

# AUR packages (using yay)
yay -S --needed - < meta/aur-packages.txt
```

## Updating Package Lists

```bash
pacman -Qe | awk '{print $1}' > meta/packages.txt
pacman -Qmq > meta/aur-packages.txt
```

## Uninstall

```bash
cd ~/Documents/my-dotfiles
stow -D -t ~ config local tmux zsh
```

## Android SDK (Manual Installation)

Manual setup without Android Studio. The environment variables are already configured in `.zshrc`.

### Download Command Line Tools

Download the latest "Command line tools only" from:
https://developer.android.com/studio#command-line-tools-only

```bash
mkdir -p ~/Android/Sdk/cmdline-tools
cd ~/Downloads
unzip commandlinetools-linux-*_latest.zip
mv cmdline-tools ~/Android/Sdk/cmdline-tools/latest
```

### Install SDK Components

```bash
source ~/.zshrc
sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

# Optional: emulator
sdkmanager "emulator" "system-images;android-34;google_apis;x86_64"
```

### Create AVD (Optional)

```bash
avdmanager create avd -n pixel_6 -k "system-images;android-34;google_apis;x86_64" -d "pixel_6"
emulator -avd pixel_6
```

## Structure

```
my-dotfiles/
├── config/
│   └── .config/
│       ├── alacritty/
│       ├── hypr/
│       ├── nvim/
│       ├── wallust/
│       ├── waybar/
│       ├── waypaper/
│       └── wofi/
├── local/
│   └── .local/
│       └── share/
│           └── fonts/
├── meta/
│   ├── packages.txt
│   └── aur-packages.txt
├── tmux/
│   └── .tmux.conf
├── zsh/
│   └── .zshrc
└── README.md
```
