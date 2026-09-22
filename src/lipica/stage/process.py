"""Delavec: a worker subprocess a notebook starts and can `kill -9`.

The notebook kernel must never die from this — it is the presenter's control panel and survives
every kill — so every worker runs as a real OS subprocess, in its own session, never as an
in-process call. It is always the same command the terminal fallback uses (`uv run act2`, ...), so
the notebook and the terminal commands in the README always agree.

`uv run <script>` is not always the process we get the pid for: uv can fork a Python child rather
than exec-replace itself, so the pid we start with may only be the launcher. `kill9()` therefore
signals the whole process group, not just that one pid.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from lipica import runstate
from lipica.pravilnik import ROOT

# This package's own bookkeeping, separate from the top-level RUN_DIR/<act>.pid that
# lipica.hosts.common writes (that one is what `make kill` / scripts/kill_during.py scan for
# ALL of an act's own worker processes; ours is only for reattaching *this* notebook's handle).
_SUBDIR = "nb"


def _dir() -> Path:
    d = runstate.RUN_DIR / _SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def uv_run(*args: str) -> list[str]:
    """`uv run act2` etc, from the repo root — the same entry point the terminal fallback uses."""
    return ["uv", "run", *args]


@dataclass
class Delavec:
    """A handle on one named worker. `pid` is the process we started (or reattached to); it may be
    `uv` itself, so `alive()`/`kill9()` reason about its process group, not just this one pid."""

    name: str
    pid: int
    log_path: Path

    @property
    def _pid_path(self) -> Path:
        return _dir() / f"{self.name}.pid"

    def alive(self) -> bool:
        """True while the process is running. Reaps first: a process that exits on its own (the common
        case — a CLI command finishing, a queue running out) stays a zombie, and `os.kill(pid, 0)` keeps
        succeeding for a zombie, until something calls `waitpid` on it — verified against a real `uv run`
        child that exits normally: `alive()` stayed `True` for minutes without this."""
        self._reap()
        try:
            os.kill(self.pid, 0)
        except OSError:
            return False
        return True

    def kill9(self, *, timeout: float = 8.0) -> bool:
        """SIGKILL the process group. Blocks until the pid is confirmed gone (or `timeout` runs out).
        Returns whether it is actually dead — the whole point of the demo is not to lie about that."""
        self._reap()
        if not self.alive():
            self._forget()
            return True
        try:
            os.killpg(os.getpgid(self.pid), signal.SIGKILL)
        except OSError:
            pass  # already gone, or never had its own group (killed the direct pid below either way)
        try:
            os.kill(self.pid, signal.SIGKILL)
        except OSError:
            pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._reap()
            if not self.alive():
                self._forget()
                return True
            time.sleep(0.1)
        return not self.alive()

    def tail(self, n: int = 200) -> str:
        """The worker's own stdout+stderr, most recent `n` lines."""
        if not self.log_path.exists():
            return ""
        lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])

    def _reap(self) -> None:
        """Collect the exit status if we are the parent (a killed child stays a zombie — and `alive()`
        below still true — until something waits on it); harmless if we are not (a reattached handle)."""
        try:
            os.waitpid(self.pid, os.WNOHANG)
        except ChildProcessError:
            pass

    def _forget(self) -> None:
        if self._pid_path.exists() and self._pid_path.read_text().strip() == str(self.pid):
            self._pid_path.unlink(missing_ok=True)


def start(name: str, args: list[str], *, env: dict[str, str] | None = None) -> Delavec:
    """Start `args` (typically `uv_run("act2")`) from the repo root as `name`'s worker: stdout+stderr
    to `RUN_DIR/nb/<name>.log`, pid to `RUN_DIR/nb/<name>.pid`, its own session so `kill9()` can
    reach every descendant. `env` overrides/extends the current environment (e.g. `LLM_BACKEND`)."""
    child_env = {**os.environ, "FORCE_COLOR": "1", "COLUMNS": "110", "PYTHONUNBUFFERED": "1", **(env or {})}
    log_path = _dir() / f"{name}.log"
    with log_path.open("w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            args,
            cwd=str(ROOT),
            env=child_env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # new process group: ours to kill as a unit
        )
    (_dir() / f"{name}.pid").write_text(str(proc.pid))
    return Delavec(name=name, pid=proc.pid, log_path=log_path)


def reattach(name: str) -> Delavec | None:
    """Find `name`'s worker again after the notebook kernel restarts (its Popen handle is gone, but
    the pid file survives). None if there is no record, or the pid it names is no longer alive."""
    pid_path = _dir() / f"{name}.pid"
    if not pid_path.exists():
        return None
    try:
        pid = int(pid_path.read_text().strip())
    except ValueError:
        return None
    d = Delavec(name=name, pid=pid, log_path=_dir() / f"{name}.log")
    if not d.alive():
        d._forget()
        return None
    return d
