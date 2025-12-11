#!/bin/bash

# Files
OPACITY_FILE="$HOME/.config/alacritty/opacity.toml"
MAIN_CONFIG="$HOME/.config/alacritty/alacritty.toml"

# Default opacity
current_opacity="1.0"

# Read current opacity if file exists
if [[ -f "$OPACITY_FILE" ]]; then
    val=$(grep -oP '(?<=opacity = )[0-9.]+' "$OPACITY_FILE" 2>/dev/null)
    if [[ -n "$val" ]]; then
        current_opacity="$val"
    fi
fi

# Determine next opacity (1.0 -> 0.6 -> 0.8 -> 1.0)
if (( $(echo "$current_opacity <= 0.6" | bc -l) )); then
    new_opacity="0.8"
elif (( $(echo "$current_opacity <= 0.8" | bc -l) )); then
    new_opacity="1.0"
else
    new_opacity="0.6"
fi

# 1. Write the new opacity to the separate file
echo "[window]" > "$OPACITY_FILE"
echo "opacity = $new_opacity" >> "$OPACITY_FILE"

# 2. Touch the main config to force Alacritty to reload imports
touch "$MAIN_CONFIG"

# Notification
if command -v notify-send &> /dev/null; then
    notify-send "Alacritty Opacity" "Changed to $new_opacity" -t 1000 -h string:x-canonical-private-synchronous:alacritty-opacity
fi
