# bwx

A lightweight python wrapper for the Bitwarden CLI.

## Features

- Unlocks Bitwarden vault once per session and caches the session token.
- Additional `cp`/`copy` subcommand to copy a password to the clipboard.
- Automatically clears the clipboard after a configurable timeout.
- Supports PRIMARY selection.

## Installation

1. Download the script from the repository:
   ```bash
   wget https://raw.githubusercontent.com/msladek/bwx/refs/heads/main/bwx.py
   ```
2. Copy the script to a directory in your `PATH`, e.g.:
   ```bash
   cp bwx.py ~/bin/bwx
   ```
3. Make it executable:
   ```bash
   chmod +x ~/bin/bwx
   ```
4. Adapt the config in the script to your needs, see `Configuration` section below.

## Usage

```bash
bwx <command>
```
See [Bitwarden CLI documentation](https://bitwarden.com/help/cli/) for available commands.

### Copy Password to Clipboard

```bash
bwx cp [--debug] [--primary] <item>
```
- `--debug` – Enable verbose output.
- `--primary` – Copy to X11 PRIMARY selection instead of the clipboard.

## Configuration

| Option                | Default                       | Description                                  |
|-----------------------|-------------------------------|----------------------------------------------|
| `debug`               | `False`                       | Toggle debug logging.                        |
| `tmp_dir`             | `/run/user/<uid>`             | Base directory for session and PID files.    |
| `cmd_bitwarden`       | `"bw"`                        | Bitwarden CLI command.                       |
| `cmd_clipboard_copy`  | `['xsel', '--input']`         | Clipboard copy command.                      |
| `cmd_clipboard_clear` | `['xsel', '--clear']`         | Clipboard clear command.                     |
| `cmd_clipboard_mode`  | `('--clipboard','--primary')` | Clipboard flags: (`clipboard`, `primary`).   |
| `clear_timeout`       | `30`                          | Seconds before auto-clear.                   |

## License

MIT License

