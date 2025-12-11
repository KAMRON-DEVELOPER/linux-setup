#!/bin/bash

# Define the volatile config file
OPACITY_FILE="$HOME/.config/alacritty/opacity.toml"

# Default opacity if file doesn't exist yet
current_opacity="1.0"

# Read current opacity if file exists
if [[ -f "$OPACITY_FILE" ]]; then
    # Extract only the number
    val=$(grep -oP '(?<=opacity = )[0-9.]+' "$OPACITY_FILE" 2>/dev/null)
    if [[ -n "$val" ]]; then
        current_opacity="$val"
    fi
fi

# Determine next opacity value (cycle: 1.0 -> 0.6 -> 0.8 -> 1.0)
# Using bc for floating point comparison
if (( $(echo "$current_opacity <= 0.6" | bc -l) )); then
    new_opacity="0.8"
elif (( $(echo "$current_opacity <= 0.8" | bc -l) )); then
    new_opacity="1.0"
else
    new_opacity="0.6"
fi

# Write the new opacity to the separate file
# We overwrite the whole file to ensure clean TOML syntax
echo "[window]" > "$OPACITY_FILE"
echo "opacity = $new_opacity" >> "$OPACITY_FILE"

# Send notification
if command -v notify-send &> /dev/null; then
    notify-send "Alacritty Opacity" "Changed to $new_opacity" -t 1000 -h string:x-canonical-private-synchronous:alacritty-opacity
fi
