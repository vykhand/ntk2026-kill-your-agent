"""The status strip every notebook opens with: emulator reachable, model reachable, worker alive, DevUI up.

Read-only, fast (a couple of seconds at most) and safe to call on every cell re-run — nothing here
starts anything.
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass

from lipica.config import nastavitve
from lipica.stage import process


@dataclass(frozen=True)
class Preverba:
    """One row of the status strip."""

    ime: str
    ok: bool
    podrobnost: str


def _dosegljiv(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (localhost only)
            return 200 <= resp.status < 300
    except Exception:
        return False


def emulator(url: str = "http://localhost:8082") -> Preverba:
    """The DTS emulator's own dashboard (Act 5 checks the scheduler itself, not this)."""
    return Preverba("DTS emulator", _dosegljiv(url + "/"), url)


def model() -> Preverba:
    """Whatever `LLM_BACKEND` currently points at. `mock` needs nothing and always passes."""
    n = nastavitve()
    if n.llm_backend == "mock":
        return Preverba("model", True, "mock (brez modela)")
    if n.llm_backend == "ollama":
        ime = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
        return Preverba("model", _dosegljiv("http://localhost:11434/api/tags"), f"ollama:{ime}")
    return Preverba("model", True, "azure (preverjeno šele ob klicu)")


def worker(name: str) -> Preverba:
    """Whether a notebook-started worker by this name (see `stage.process.start`) is still alive."""
    d = process.reattach(name)
    return Preverba(f"delavec {name}", d is not None, f"pid {d.pid}" if d else "ne teče")


def devui(port: int = 8090) -> Preverba:
    return Preverba("DevUI", _dosegljiv(f"http://127.0.0.1:{port}/"), f"http://127.0.0.1:{port}")


def trak(worker_name: str | None = None) -> list[Preverba]:
    """The whole strip in display order; pass the current notebook's worker name to include it."""
    items = [emulator(), model()]
    if worker_name:
        items.append(worker(worker_name))
    items.append(devui())
    return items
