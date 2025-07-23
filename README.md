# bwx

A lightweight python wrapper for the Bitwarden CLI.

## Features

- **Session management**: Unlock your Bitwarden vault once and cache the session token securely.
- **`cp`/`copy` subcommand**: Copy a password to the clipboard.
- **Auto‑clear**: Automatically clears the clipboard after a configurable timeout.
- **YAML config**: Easy configuration using a YAML file.

## Requirements
- UNIX
- Python 3+ with `pyyaml`
- Bitwarden CLI `bw`
- Clipboard management like `xsel` or `wl-clipboard`

## Installation

1. Get the script from the repository and install somewhere in your `PATH`
   ```bash
   wget https://raw.githubusercontent.com/msladek/bwx/refs/heads/main/bwx.py
   chmod +x bwx
   mv bwx.py ~/bin/bwx
   ```
2. Create a config fitting your needs, see `Configuration` section below:
   ```bash
   edit ~/.config/bwx.yml
   ```

## Usage

```bash
bwx <command>
```
See [Bitwarden CLI documentation](https://bitwarden.com/help/cli/) for available commands.

### Copy Password to Clipboard

```bash
bwx cp <item>
```

### Aliases

| Alias | Command |
|-------|------------------------------------|
| `bwx pw <item>` | `bw get password <item>` |

## Configuration

| Option                    | Default           | Description                 |             
|---------------------------|-------------------|-----------------------------|
| `debug`                   | `False`           | Toggle debug logging        |
| `transient_dir`           | `/run/user/<uid>` | Directory for session cache |
| `bw_cmd`                  | `"bw"`            | Bitwarden CLI command       |
| `clipboard_copy_cmd`      | `[] (disabled)`   | Clipboard copy command      |
| `clipboard_clear_cmd`     | `[] (disabled)`   | Clipboard clear command     |
| `clipboard_clear_timeout` | `30`              | Seconds before auto-clear   |

You can override the default config by creating a YAML file.
The script will look for config files in:

- `<script_dir>/bwx.yml` / `.yaml`
- `~/.config/bwx.yml` / `.yaml`
- `/etc/bwx.yml` / `.yaml`

### Example Config

```yaml
debug: false
transient_dir: "$XDG_RUNTIME_DIR" # ramdisk strongly recommended

bw_cmd: "bw" # in PATH or FQN

clipboard_copy_cmd: # disabled if empty
  - "xsel"
  - "--input"
  - "--clipboard"
clipboard_clear_cmd: # disabled if empty
  - "xsel"
  - "--clear"
  - "--clipboard"
clipboard_clear_timeout: 30 # seconds
```
