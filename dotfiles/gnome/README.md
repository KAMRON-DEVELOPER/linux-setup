# GNOME Keybindings Backup

This directory contains GNOME keyboard shortcut configurations for quick restoration across systems.

## What's Included

- **Media keys** and custom shortcuts
- **Window manager** (Mutter) keybindings

> **Note:** Themes, extensions, app layouts, and other GNOME state are intentionally excluded to keep restores clean and portable.

---

## Export Keybindings

Media Keys & Custom Shortcuts

```bash
dconf dump /org/gnome/settings-daemon/plugins/media-keys/ > media-keys.dconf
dconf dump /org/gnome/settings-daemon/plugins/media-keys/ > ~/Documents/linux-setup/dotfiles/gnome/media-keys.dconf
```

Window Manager Shortcuts

```bash
dconf dump /org/gnome/desktop/wm/keybindings/ > keybindings.dconf
dconf dump /org/gnome/desktop/wm/keybindings/ > ~/Documents/linux-setup/dotfiles/gnome/keybindings.dconf
```

---

## Restore Keybindings

Media Keys & Custom Shortcuts

```bash
dconf load /org/gnome/settings-daemon/plugins/media-keys/ < media-keys.dconf
dconf load /org/gnome/settings-daemon/plugins/media-keys/ < ~/Documents/linux-setup/dotfiles/gnome/media-keys.dconf
```

Window Manager Shortcuts

```bash
dconf load /org/gnome/desktop/wm/keybindings/ < keybindings.dconf
dconf load /org/gnome/desktop/wm/keybindings/ < ~/Documents/linux-setup/dotfiles/gnome/keybindings.dconf
```

> **Important:** Log out and log back in after restoring for changes to take effect.

---

## Quick Restore (Both)

```bash
dconf load /org/gnome/settings-daemon/plugins/media-keys/ < media-keys.dconf
dconf load /org/gnome/settings-daemon/plugins/media-keys/ < ~/Documents/linux-setup/dotfiles/gnome/media-keys.dconf

dconf load /org/gnome/desktop/wm/keybindings/ < keybindings.dconf
dconf load /org/gnome/desktop/wm/keybindings/ < ~/Documents/linux-setup/dotfiles/gnome/keybindings.dconf
```
