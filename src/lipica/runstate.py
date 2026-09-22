"""Small on-disk run state under .run/: the queue-ticket counter, the current step (for the
kill helper) and worker pids. Nothing here is workflow state; it is demo plumbing."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from lipica.pravilnik import ROOT

RUN_DIR = Path(os.environ.get("LIPICA_RUN_DIR") or ROOT / ".run")
OUT_DIR = Path(os.environ.get("LIPICA_OUT_DIR") or ROOT / "out")

_COUNTER = RUN_DIR / "listek-counter"
_STEP = RUN_DIR / "current-step.json"
_PRVA_STEVILKA = 47  # the number from the scenario spec


def ensure_dirs() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "odlocbe").mkdir(parents=True, exist_ok=True)


def naslednja_stevilka_listka() -> int:
    ensure_dirs()
    current = int(_COUNTER.read_text()) if _COUNTER.exists() else _PRVA_STEVILKA - 1
    current += 1
    _COUNTER.write_text(str(current))
    return current


def reset_listek() -> None:
    if _COUNTER.exists():
        _COUNTER.unlink()


def set_step(vloga_id: str, executor: str) -> None:
    """Advertise which executor is running, so `make kill` can strike at the right moment."""
    ensure_dirs()
    _STEP.write_text(json.dumps({"pid": os.getpid(), "vloga_id": vloga_id, "step": executor, "ts": time.time()}))


def current_step() -> dict | None:
    if not _STEP.exists():
        return None
    try:
        return json.loads(_STEP.read_text())
    except json.JSONDecodeError:
        return None


def clear_step() -> None:
    if _STEP.exists():
        _STEP.unlink()


def write_pid(name: str) -> Path:
    ensure_dirs()
    p = RUN_DIR / f"{name}.pid"
    p.write_text(str(os.getpid()))
    return p


def remove_pid(name: str) -> None:
    p = RUN_DIR / f"{name}.pid"
    if p.exists() and p.read_text().strip() == str(os.getpid()):
        p.unlink()
