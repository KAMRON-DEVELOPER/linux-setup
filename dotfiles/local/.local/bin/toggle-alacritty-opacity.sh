#!/bin/bash

# Alacritty config file location
CONFIG_FILE="$HOME/.config/alacritty/alacritty.toml"

# Check if config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Alacritty config not found at $CONFIG_FILE"
    exit 1
fi

# Get current opacity value
current_opacity=$(grep -oP '(?<=opacity = )[0-9.]+' "$CONFIG_FILE" 2>/dev/null)

# If no opacity found, default to 1.0
if [[ -z "$current_opacity" ]]; then
    current_opacity="1.0"
fi

# Determine next opacity value (cycle through 0.6, 0.8, 1.0)
if (( $(echo "$current_opacity <= 0.6" | bc -l) )); then
    new_opacity="0.8"
elif (( $(echo "$current_opacity <= 0.8" | bc -l) )); then
    new_opacity="1.0"
else
    new_opacity="0.6"
fi

# Update the opacity in the config file
if grep -q "opacity = " "$CONFIG_FILE"; then
    # Opacity line exists, replace it
    sed -i "s/opacity = [0-9.]*/opacity = $new_opacity/" "$CONFIG_FILE"
else
    # Opacity line doesn't exist, add it under [window] section
    if grep -q "^\[window\]" "$CONFIG_FILE"; then
        # [window] section exists, add opacity after it
        sed -i "/^\[window\]/a opacity = $new_opacity" "$CONFIG_FILE"
    else
        # No [window] section, create it
        echo -e "\n[window]\nopacity = $new_opacity" >> "$CONFIG_FILE"
    fi
fi

# Send notification (optional, requires dunst or similar)
if command -v notify-send &> /dev/null; then
    notify-send "Alacritty Opacity" "Changed to $new_opacity" -t 1000
fi

echo "Alacritty opacity changed to $new_opacity"