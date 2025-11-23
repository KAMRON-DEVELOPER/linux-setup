# 🚀 MY ULTIMATE NEOVIM SETUP 🚀

## ⭐ TMUX ⭐
******************************** TMUX ***********************************
$ tmux new -s new-session == create new session
$ tmux a == attach to last session
$ tmux a -t session_name == attachin to given session name
$ tmux ls == show all sessions
$ shift + </> == change windows
$ alt + </^/> == change panes
<prefix> + d == deattach from tmux session
<prefix> + s == navigate beetween sessions
<prefix> + w == preview session
<prefix> + : == type command to navbar
<prefix> + z == zoom or toggle fullscreen
<prefix> + {/} == move the current pain to right/left
<prefix> + ! == take the current pains to new window
<prefix> + V == split vertically 
<prefix> + H == split horizontally
<prefix> + alt + <^> == resize panes
<prefix> + V == split vertically
# tmux-resurrect
prefix + Ctrl-s == save session even kill-server!!!
prefix + Ctrl-r == restore session even killed server!!!

## ⭐ NAVIGATION ⭐

| Mode | Key        | Action                          |
| ---- | ---------- | ------------------------------- |
| (n)  | `h`        | Move cursor left                |
| (n)  | `l`        | Move cursor right               |
| (n)  | `j`        | Move cursor below               |
| (n)  | `k`        | Move cursor up                  |
| (n)  | `w`        | Bring cursor to next word head  |
| (n)  | `e`        | Bring cursor to end of word     |
| (n)  | `gg`       | Go to start of file             |
| (n)  | `G`        | Go to end of file               |
| (n)  | `{`        | Go to start of paragraph        |
| (n)  | `}`        | Go to end of paragraph          |
| (n)  | `0`        | Go to start of line             |
| (n)  | `^`        | Go to first non-blank character |
| (n)  | `$`        | Go to end of line               |
| (n)  | `Ctrl + u` | Move up half page               |
| (n)  | `Ctrl + d` | Move down half page             |
| (n)  | `Ctrl + b` | Move one page up                |
| (n)  | `Ctrl + f` | Move one page down              |
| (n)  | `zf`       | Create a fold                   |
| (n)  | `zd`       | Delete a fold                   |
| (n)  | `zo`       | Open a fold                     |
| (n)  | `zc`       | Close a fold                    |
| (n)  | `zC`       | Close all folds under cursor    |
| (n)  | `zr`       | Reduce folding level            |
| (n)  | `zm`       | Increase folding level          |

## ⭐ EDITING ⭐

| Mode | Key        | Action                            |
| ---- | ---------- | --------------------------------- |
| (n)  | `x`        | Delete character after cursor     |
| (n)  | `dw`       | Delete to word end                |
| (n)  | `diw`      | Delete whole word                 |
| (n)  | `dd`       | Delete entire line                |
| (n)  | `D`        | Delete from cursor to end of line |
| (n)  | `u`        | Undo                              |
| (n)  | `Ctrl + r` | Redo                              |
| (n)  | `>>`       | Indent right                      |
| (n)  | `<<`       | Indent left                       |
| (n)  | `~`        | Toggle case                       |
| (n)  | `.`        | Repeat last action                |
| (n)  | `viw`      | Select inside word                |
| (n)  | `ciw`      | Change inside word                |
| (n)  | `cw`       | Change word (partial)             |
| (n)  | `caw`      | Change entire word                |

## ⭐ VISUAL MODE ⭐

| Mode | Key | Action              |
| ---- | --- | ------------------- |
| (v)  | `v` | Start visual mode   |
| (v)  | `V` | Select whole line   |
| (v)  | `y` | Yank (copy)         |
| (v)  | `p` | Paste               |
| (v)  | `P` | Paste before cursor |

## 📦 PLUGINS CONFIGURATION 📦

### ⚙️ nvim-treesitter

| Mode | Key            | Action                |
| ---- | -------------- | --------------------- |
| (v)  | `Ctrl + Space` | Incremental selection |
| (v)  | `Backspace`    | Decremental selection |

### ⚙️ vim-maximizer

| Mode | Key        | Action                         |
| ---- | ---------- | ------------------------------ |
| (n)  | `Ctrl + M` | Maximize/minimize split window |

### ⚙️ mason, mason-lspconfig, nvim-lspconfig

| Mode | Key           | Action                      |
| ---- | ------------- | --------------------------- |
| (n)  | `Leader + ch` | Show code hover information |
| (n)  | `Leader + cd` | Go to code definition       |
| (n)  | `Leader + cr` | Show code references        |
| (n)  | `Leader + ca` | Show code actions           |

### ⚙️ nvim-surround

| Mode | Key                     | Action                           |
| ---- | ----------------------- | -------------------------------- |
| (n)  | `ysiw + character`      | Surround word with a character   |
| (n)  | `yss + character`       | Surround line with a character   |
| (n)  | `ds + character`        | Delete surrounding character     |
| (n)  | `cs + character`        | Change surrounding character     |
| (n)  | `cs + character + text` | Change surrounding with new text |

| Example Commands               | Result                          |
| ------------------------------ | ------------------------------- |
| `ysi)`                         | (surround text)                |
| `ys"`                         | "surround text"               |
| `dst`                          | Delete surrounding tags         |
| `cs"'`                        | Change quotes                  |
| `csth1<CR>`                    | Change to `<h1>text</h1>`      |

### ⚙️ vim-fugitive

| Mode | Key            | Action                      |
| ---- | -------------- | --------------------------- |
| (n)  | `Leader + gs`  | Open Git status window      |
| (n)  | `Leader + gd`  | Show Git diff               |
| (n)  | `Leader + gaa` | Stage all files             |
| (n)  | `Leader + ga`  | Stage current file          |
| (n)  | `Leader + gc`  | Commit changes with message |

| Fugitive Shortcuts                      |
| --------------------------------------- |
| `-` : Stage/unstage current file        |
| `cc` : Commit changes                   |
| `s` : Stage the current file            |
| `u` : Unstage the current file          |
| `X` : Discard changes                   |
| `=` : View file differences             |
| `ZZ` : Save and exit the commit message |

### ⚙️ flutter-tools

| Command                  | Description                              |
| ------------------------ | ---------------------------------------- |
| `FlutterRun`            | Run the current project                  |
| `FlutterDebug`          | Force debug mode                         |
| `FlutterDevices`        | List connected devices                   |
| `FlutterEmulators`      | List available emulators                 |
| `FlutterReload`         | Reload the running project               |
| `FlutterRestart`        | Restart the current project              |
| `FlutterQuit`           | Quit the running session                 |
| `FlutterAttach`         | Attach to a running app                  |
| `FlutterDetach`         | Detach from running app                  |
| `FlutterOutlineToggle`  | Toggle the outline widget tree           |
| `FlutterDevTools`       | Start Dart Dev Tools server              |
| `FlutterLspRestart`     | Restart Dart language server             |
| `FlutterReanalyze`      | Force LSP server reanalysis              |
| `FlutterRename`         | Rename and update imports                |
| `FlutterLogClear`       | Clear log buffer                         |
| `FlutterLogToggle`      | Toggle log buffer                        |
