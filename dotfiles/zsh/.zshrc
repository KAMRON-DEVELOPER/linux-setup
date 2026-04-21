setopt histignorealldups sharehistory

HISTSIZE=1000
SAVEHIST=1000

HISTFILE=~/.zsh_history

################################### CUSTOM ###########################################

# Bind Ctrl+Left to backward-word
bindkey '^[[1;5D' backward-word

# Bind Ctrl+Right to forward-word
bindkey '^[[1;5C' forward-word

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

# Powerlevel10k theme - check multiple installation locations
if [[ -f /usr/share/zsh-theme-powerlevel10k/powerlevel10k.zsh-theme ]]; then
  # Installed via package manager (yay/pacman)
  source /usr/share/zsh-theme-powerlevel10k/powerlevel10k.zsh-theme
elif [[ -f ~/powerlevel10k/powerlevel10k.zsh-theme ]]; then
  # Installed via git clone to home directory
  source ~/powerlevel10k/powerlevel10k.zsh-theme
elif [[ -f "${XDG_DATA_HOME:-$HOME/.local/share}/powerlevel10k/powerlevel10k.zsh-theme" ]]; then
  # Installed to XDG_DATA_HOME
  source "${XDG_DATA_HOME:-$HOME/.local/share}/powerlevel10k/powerlevel10k.zsh-theme"
fi

# Zsh plugins
if [[ -f /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh
fi

if [[ -f /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh ]]; then
  source /usr/share/zsh/plugins/zsh-autosuggestions/zsh-autosuggestions.zsh
fi

# Rust
if [[ -d "$HOME/.cargo/bin" ]]; then
  export PATH="$HOME/.cargo/bin:$PATH"
fi

# GO
if [[ -d "$HOME/go/bin" ]]; then
  export PATH="$HOME/go/bin:$PATH"
fi

# Pyenv
if [[ -d "$HOME/.pyenv" ]]; then
  export PYENV_ROOT="$HOME/.pyenv"
  [[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
  eval "$(pyenv init - zsh)"
  if command -v pyenv-virtualenv-init 1>/dev/null 2>&1; then
    eval "$(pyenv virtualenv-init -)"
  fi
fi

# Nvm node version manager
# Nvm from pacman
[ -s "/usr/share/nvm/init-nvm.sh" ] && source /usr/share/nvm/init-nvm.sh
# Nvm node version manager (manual installation)
if [[ -d "$HOME/.config/nvm" ]]; then
  export NVM_DIR="$HOME/.config/nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
  [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
fi
if [[ -d "$HOME/.nvm" ]]; then
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" # This loads nvm
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion" # This loads nvm bash_completion
fi

# Android SDK
if [[ -d "$HOME/Android/Sdk" ]]; then
  export ANDROID_HOME=$HOME/Android/Sdk
  export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin
  export PATH=$PATH:$ANDROID_HOME/platform-tools
  export PATH="$ANDROID_HOME/emulator:$PATH"
fi

# Java 17
if [[ -d "/usr/lib/jvm/java-17-openjdk" ]]; then
  export JAVA_HOME="/usr/lib/jvm/java-17-openjdk"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

# Flutter 
if [[ -d "$HOME/flutter" ]]; then
  export PATH="$HOME/flutter/bin:$PATH"
  export PATH="$PATH":"$HOME/.pub-cache/bin"
fi

# KVM tools
if [[ -d "$HOME/Documents/linux-setup/kvm" ]]; then
  export PATH="$HOME/Documents/linux-setup/kvm:$PATH"
fi

# Git add, commit, push
function acp() {
  git add .
  git commit -m "$1"
  git push
}

add-vault-config() {
  emulate -L zsh
  setopt pipefail

  local vault_keys_file="${1:-$HOME/certs/vault-keys.json}"
  if [[ ! -f "$vault_keys_file" ]]; then
    echo "Error: vault keys file not found: $vault_keys_file"
    return 1
  fi
  command -v jq >/dev/null || { echo "Error: jq not found"; return 1; }

  echo "Enter vault environment name (e.g., local, poddle-mvp, prod):"
  local vault_name; read vault_name
  [[ -z "$vault_name" ]] && { echo "Error: empty name"; return 1; }

  echo "Enter vault address (e.g., https://vault.poddle.uz):"
  local vault_addr; read vault_addr
  [[ -z "$vault_addr" ]] && { echo "Error: empty address"; return 1; }

  local token key1 key2 key3 key4 key5
  token="$(jq -r '.root_token' "$vault_keys_file")"
  key1="$(jq -r '.unseal_keys_b64[0]' "$vault_keys_file")"
  key2="$(jq -r '.unseal_keys_b64[1]' "$vault_keys_file")"
  key3="$(jq -r '.unseal_keys_b64[2]' "$vault_keys_file")"
  key4="$(jq -r '.unseal_keys_b64[3]' "$vault_keys_file")"
  key5="$(jq -r '.unseal_keys_b64[4]' "$vault_keys_file")"

  local vault_title="${(C)vault_name}"   # zsh capitalization

  mkdir -p "$HOME/.secrets.d"
  local out="$HOME/.secrets.d/vault-${vault_name}.zsh"

  cat > "$out" <<EOF
# ${vault_title} Vault (generated)
function vault-${vault_name}() {
  export VAULT_TOKEN="${token}"
  export VAULT_ADDR="${vault_addr}"
  echo "Switched to Vault ${vault_title}"
}

function vault-unseal-${vault_name}() {
  export UNSEAL_KEY1="${key1}"
  export UNSEAL_KEY2="${key2}"
  export UNSEAL_KEY3="${key3}"
  export UNSEAL_KEY4="${key4}"
  export UNSEAL_KEY5="${key5}"
}
EOF

  # Ensure ~/.secrets loads the directory (one-time append)
  if ! grep -q 'source \$HOME/\.secrets\.d/\*' "$HOME/.secrets" 2>/dev/null; then
    cat >> "$HOME/.secrets" <<'EOF'

# Load per-env secrets
for f in "$HOME/.secrets.d/"*.zsh(N); do
  source "$f"
done
EOF
  fi

  source "$HOME/.secrets"
  echo "✅ Wrote $out and reloaded ~/.secrets"

  echo -n "Delete $vault_keys_file? (y/N): "
  local delete_keys; read delete_keys
  if [[ "$delete_keys" == [Yy] ]]; then
    rm -f "$vault_keys_file"
    echo "🗑️ Deleted $vault_keys_file"
  fi
}

alias k="kubectl"

# Env vars
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_PICTURES_DIR="$HOME/Pictures/Screenshots"
export HYPRSHOT_DIR="$HOME/Pictures/Screenshots"
export LIBVIRT_DEFAULT_URI='qemu:///system'
export EDITOR=nvim
SYSTEMD_EDITOR=nvim
export VISUAL=nvim
export KUBE_EDITOR="nvim"
# export KUBECONFIG=~/.kube/config:~/.kube/config-local:~/.kube/config-poddle-mvp
export _JAVA_AWT_WM_NONREPARENTING=1
export GDK_BACKEND=wayland
# export QT_QPA_PLATFORM=wayland

# Load local secrets
[[ -f "$HOME/.secrets" ]] && source "$HOME/.secrets"
# if [[ -f "$HOME/.secrets" ]]; then
#   source "$HOME/.secrets"
# fi

autoload -U +X bashcompinit && bashcompinit
complete -o nospace -C /usr/bin/vault vault
. $(pack-cli completion --shell zsh)

typeset -g POWERLEVEL9K_INSTANT_PROMPT=quiet
