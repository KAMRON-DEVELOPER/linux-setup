#!/bin/bash
# ~/.config/waypaper/hook.sh
# This hook runs after waypaper changes the wallpaper

WALLPAPER="$1"

if [ -z "$WALLPAPER" ]; then
    echo "Error: No wallpaper path provided"
    exit 1
fi

echo "Generating colors from: $WALLPAPER"

# Run wallust to generate colors
wallust run "$WALLPAPER"

# Wait a moment for files to be written
sleep 0.2

# Reload Waybar to apply new colors
if pgrep -x waybar > /dev/null; then
    echo "Reloading Waybar..."
    killall waybar
    sleep 0.3
    waybar &
fi

# Reload Hyprland config to apply new colors
echo "Reloading Hyprland..."
hyprctl reload

# Alacritty will reload automatically due to live_config_reload = true

echo "Colors updated successfully!"
