#!/usr/bin/env python3
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
import os
import sys
import shutil
import signal
import subprocess
from subprocess import SubprocessError
import time
from typing import List
import yaml

@dataclass
class Config:
  debug: bool = False
  transient_dir: str = os.getenv("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
  bw_cmd: str = "bw"
  clipboard_copy_cmd: List[str] = field(default_factory=lambda: [])
  clipboard_clear_cmd: List[str] = field(default_factory=lambda: [])
  clipboard_clear_timeout: int = 30 # seconds

  CFG_PATHS = (
    Path("/etc/bwx.yml"),
    Path("/etc/bwx.yaml"),
    Path.home() / ".config" / "bwx.yml",
    Path.home() / ".config" / "bwx.yaml",
    Path(__file__).parent / "bwx.yml",
    Path(__file__).parent / "bwx.yaml",
  )

  @classmethod
  def from_yaml(cls) -> "Config":
    cfg = asdict(cls())
    for file in cls.CFG_PATHS:
      if not file.is_file(): continue
      cfg.update(yaml.safe_load(file.read_text()) or {})
    return cls(**cfg).validate()

  def get_transient_path(self) -> Path:
    dir = os.path.expandvars(self.transient_dir)
    dir = os.path.expanduser(dir)
    return Path(dir)
  
  def is_copy_enabled(self) -> bool: return bool(self.clipboard_copy_cmd)

  def is_clear_enabled(self) -> bool: return bool(self.clipboard_clear_cmd)
  
  def validate(self) -> "Config":
    if not self.transient_dir:
      raise ValueError("transient directory not set")
    self.get_transient_path().mkdir(exist_ok=True, mode=0o700)
    if not shutil.which(self.bw_cmd):
      raise ValueError(f"command '{self.bw_cmd}' not found")
    if self.is_copy_enabled() and not shutil.which(self.clipboard_copy_cmd[0]):
      raise ValueError(f"command '{self.clipboard_copy_cmd[0]}' not found")
    if self.is_clear_enabled() and not shutil.which(self.clipboard_clear_cmd[0]):
      raise ValueError(f"command '{self.clipboard_clear_cmd[0]}' not found")
    if self.is_clear_enabled() and self.clipboard_clear_timeout <= 0:
      raise ValueError("clipboard clear timeout must be positive")
    return self

class Session:
  SESSION_ENV = "BW_SESSION"
  def __init__(self, cfg: Config):
    self.cfg = cfg
    self.session_file = self.cfg.get_transient_path() / self.SESSION_ENV

  def unlock(self) -> str:
    token = os.getenv(self.SESSION_ENV)
    if token: return token    
    token = self._load_session()
    if not token: 
      logger.debug("unlocking vault...")
      token = subprocess.check_output([self.cfg.bw_cmd, "unlock", "--raw"], text=True).strip()
      if not token: raise ValueError("no session token received")
      self._save_session(token)
    os.environ[self.SESSION_ENV] = token
    return token

  def _load_session(self) -> str:
    if self.session_file.is_file():
      logger.debug(f"loading session from {self.session_file}")
      return self.session_file.read_text()
    return ""

  def _save_session(self, token: str) -> None:
    logger.debug(f"saving new session token to {self.session_file}")
    self.session_file.touch(mode=0o600, exist_ok=True)
    self.session_file.write_text(token)

class CopyCommand:
  PID_FILE_NAME = "bw_clear.pid"
  def __init__(self, cfg: Config):
    self.cfg = cfg
    self.pid_file = self.cfg.get_transient_path() / self.PID_FILE_NAME

  def execute(self, item: str) -> None:
    if not self.cfg.is_copy_enabled():
      raise ValueError("clipboard copy command not configured")
    logger.debug(f"copy for: '{item}'")
    try: pw = subprocess.check_output([self.cfg.bw_cmd, "get", "password", item], text=True).strip()
    except SubprocessError: return # bw_cmd prints error message
    logger.debug(f"copying to clipboard...")
    copy_process = subprocess.Popen(self.cfg.clipboard_copy_cmd, stdin=subprocess.PIPE, text=True)
    self._copy_clear_cancel()
    copy_process.communicate(pw)
    logger.debug(f"copy done")
    self._copy_clear_fork()

  def _copy_clear_fork(self) -> None:
    if not self.cfg.is_clear_enabled():
      logger.debug("copy clear not enabled, skipping")
      return
    if os.fork() != 0: return # parent exits
    pid = os.getpid()
    logger.debug(f"{pid}:forked")
    if not self.cfg.debug: os.setsid() # detach from tty/signals
    signal.signal(signal.SIGTERM, lambda signum, frame: self._copy_clear_cleanup(signum))
    try:
      self.pid_file.write_text(str(pid))
      logger.debug(f"{pid}:sleeping for {self.cfg.clipboard_clear_timeout}s")
      time.sleep(self.cfg.clipboard_clear_timeout)
      logger.debug(f"{pid}:clearing clipboard")
      subprocess.run(self.cfg.clipboard_clear_cmd)
    finally:
      self._copy_clear_cleanup()
      os._exit(0)

  def _copy_clear_cancel(self) -> None:
    if not self.pid_file.is_file(): return
    pid = int(self.pid_file.read_text())
    try:
      os.kill(pid, signal.SIGTERM)
      logger.debug(f"sent SIGTERM to existing process {pid}")
    except ProcessLookupError:
      logger.debug(f"process {pid} not found, likely already gone")
      pass

  def _copy_clear_cleanup(self, signum=None) -> None:
    if signum is not None:
      logger.debug(f"{os.getpid()}:received cleanup signal {signum}")
    self.pid_file.unlink(missing_ok=True)
    logger.debug(f"{os.getpid()}:removed its PID file")
    if signum is not None:
      os._exit(0)

class Bwx:
  def __init__(self, cfg: Config):
    self.cfg = cfg

  def run(self) -> int:
    if len(sys.argv) < 2:
      os.execvp(self.cfg.bw_cmd, [self.cfg.bw_cmd, "--help"])
    cmd, *args = sys.argv[1:]
    logger.debug(f"command: '{cmd}', Args: {args}")
    if not cmd in ("login", "logout", "config"):
      session = Session(self.cfg)
      session.unlock()
    if cmd == "unlock":
      return 0;
    elif cmd in ("cp", "copy"):
      copy = CopyCommand(self.cfg)
      copy.execute(" ".join(args))
      return 0
    else:
      logger.debug(f"passing command to '{self.cfg.bw_cmd}'...")
      base_cmd = [self.cfg.bw_cmd, cmd] if cmd != "pw" else [self.cfg.bw_cmd, "get", "password"]
      os.execvp(self.cfg.bw_cmd, base_cmd + args)

if __name__ == "__main__":
  logging.basicConfig(stream=sys.stderr, level=logging.WARN)
  logger = logging.getLogger("bwx")
  try: 
    config = Config.from_yaml()
    if config.debug: logger.setLevel(logging.DEBUG)
    bwx = Bwx(config)
    status = bwx.run()
    sys.exit(status)
  except (yaml.YAMLError, ValueError, OSError, SubprocessError) as e:
    logger.error(e)
    sys.exit(1)
