#!/usr/bin/env python3
import os
import sys
import shutil
import signal
import subprocess
import time
from typing import List, Tuple, TypedDict

# --- Configuration ---
class Config(TypedDict):
  debug: bool
  tmp_dir: str
  cmd_bitwarden: str
  cmd_clipboard_copy: List[str]
  cmd_clipboard_clear: List[str]
  cmd_clipboard_mode: Tuple[str, str] # first is clipboard, second is primary
  clear_timeout: int # seconds

config: Config = {
  "debug": False,
  "tmp_dir": f"/run/user/{os.getuid()}",
  "cmd_bitwarden": "bw",
  "cmd_clipboard_copy": ["xsel", "--input"],
  "cmd_clipboard_clear": ["xsel", "--clear"],
  "cmd_clipboard_mode": ("--clipboard", "--primary"),
  "clear_timeout": 30,
}

# --- Main Function ---
def main() -> None:
  pre_checks()
  cmd_bw = config["cmd_bitwarden"]
  config["debug"] = "--debug" in sys.argv and sys.argv.remove("--debug") is None
  primary = "--primary" in sys.argv and sys.argv.remove("--primary") is None
  if len(sys.argv) < 2:
    os.execvp(cmd_bw, [cmd_bw, "--help"])
  cmd, *args = sys.argv[1:]
  log(f"command: '{cmd}', Args: {args}")
  if not cmd in ("login", "logout"):
    unlock()
  if cmd == "unlock":
    sys.exit(0)
  elif cmd in ("cp", "copy"):
    copy(item=" ".join(args), primary=primary)
    sys.exit(0)
  else:
    log(f"passing command to '{cmd_bw}'...")
    base_cmd = [cmd_bw, cmd] if cmd != "pw" else [cmd_bw, "get", "password"]
    os.execvp(cmd_bw, base_cmd + args)

def pre_checks() -> None:
  if not shutil.which(config["cmd_bitwarden"]):
    sys.exit(f"Error: {config["cmd_bitwarden"]} command not found")
  tmp_dir = config["tmp_dir"]
  if not os.path.isdir(tmp_dir):
    sys.exit(f"Error: Temporary directory {tmp_dir} does not exist")
  if not os.access(tmp_dir, os.W_OK):
    sys.exit(f"Error: No write permission for temporary directory {tmp_dir}")

# --- Session Management ---
SESSION_ENV = "BW_SESSION"

def unlock() -> None:
  log("unlocking vault...")
  token = os.getenv(SESSION_ENV)
  if token: return token
  session_file = os.path.join(config["tmp_dir"], SESSION_ENV)
  token = load_session(session_file)
  if not token: 
    log("no active session. Unlocking vault...")
    try: token = subprocess.check_output([config["cmd_bitwarden"], "unlock", "--raw"], text=True).strip()
    except subprocess.CalledProcessError: sys.exit(1)
    if not token: sys.exit("Error: No session token found")
    save_session(session_file, token)
  os.environ[SESSION_ENV] = token

def load_session(session_file: str) -> str:
  if os.path.isfile(session_file):
    log(f"loading session from file")
    with open(session_file) as file:
      return file.read().strip()
  return ""

def save_session(session_file: str, token: str) -> None:
  log(f"saving new session token to {session_file}")
  fd = os.open(session_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
  try:
    os.write(fd, token.encode())
  finally:
    os.close(fd)

# --- Copy Command ---
def copy(item: str, primary: bool = False) -> None:
  cmd = config["cmd_clipboard_copy"] + [config["cmd_clipboard_mode"][primary]]
  if not shutil.which(cmd[0]):
    sys.exit(f"Error: {cmd[0]} command not found")
  log(f"copy for: '{item}'")
  try: pw = subprocess.check_output([config["cmd_bitwarden"], "get", "password", item], text=True).strip()
  except subprocess.CalledProcessError: return
  log(f"pw retrieved, copying to {"primary" if primary else "clipboard"}...")
  copy_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
  pid_file = os.path.join(config["tmp_dir"], "bw_clear.pid")
  copy_clear_cancel(pid_file)
  copy_process.communicate(pw)
  log(f"copy done")
  copy_clear_fork(pid_file, primary)

def copy_clear_fork(pid_file: str, primary: bool = False) -> None:
  cmd = config["cmd_clipboard_clear"] + [config["cmd_clipboard_mode"][primary]]
  if not shutil.which(cmd[0]):
    sys.exit(f"Error: {cmd[0]} command not found")
  if os.fork() != 0: return # parent exits
  pid = os.getpid()
  log(f"[{pid}] forked")
  if not config["debug"]: os.setsid() # detach from tty/signals
  signal.signal(signal.SIGTERM, lambda signum, frame: copy_clear_cleanup(pid_file, signum))
  try:
    with open(pid_file, 'w') as file:
      file.write(str(pid))
    log(f"[{pid}] sleeping for {config["clear_timeout"]}s")
    time.sleep(config["clear_timeout"])
    log(f"[{pid}] clearing clipboard")
    subprocess.run(cmd)
  finally:
    copy_clear_cleanup(pid_file)
    os._exit(0)

def copy_clear_cancel(pid_file: str) -> None:
  if not os.path.isfile(pid_file): return
  with open(pid_file) as file:
    pid = int(file.read().strip())
    try:
      os.kill(pid, signal.SIGTERM)
      log(f"sent SIGTERM to existing process {pid}")
    except ProcessLookupError:
      log(f"process {pid} not found, likely already gone")
      pass

def copy_clear_cleanup(pid_file: str, signum=None) -> None:
  if signum is not None:
    log(f"[{os.getpid()}] received cleanup signal {signum}")
  try:
    os.remove(pid_file)
    log(f"[{os.getpid()}] removed its PID file")
  except OSError: pass
  if signum is not None:
    os._exit(0)

# --- Logging ---
def log(message: str) -> None:
  if config["debug"]: print(f"DEBUG: {message}", file=sys.stderr)

# --- Main Execution ---
if __name__ == "__main__":
  main()
