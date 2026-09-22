"""Shared host plumbing: banner, worker guard, auto-kill helper, result lines, ledger summary."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from rich.markup import escape

from lipica import runstate
from lipica.config import Nastavitve
from lipica.console import console, naslov, opozorilo
from lipica.domain import Odlocba
from lipica.pravilnik import ROOT


def banner(act: str, subtitle: str, n: Nastavitve, *, idempotent: bool) -> None:
    naslov(act, subtitle)
    console.print(
        f"[dim]LLM_BACKEND={n.llm_backend}  MALICA_SECONDS={n.malica_seconds:g}"
        f"  odločba idempotentna: {'da' if idempotent else 'ne'}[/]"
    )


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def zasedi_delavca(name: str) -> None:
    """Refuse to start if the same act is still running: two workers on one task hub split the work."""
    p = runstate.RUN_DIR / f"{name}.pid"
    if p.exists():
        try:
            pid = int(p.read_text().strip() or 0)
        except ValueError:
            pid = 0
        if pid and pid != os.getpid() and _alive(pid):
            opozorilo(f"Delavec {name} (pid {pid}) že teče. Ustavi ga z `make kill` in poskusi znova.")
            sys.exit(1)
    runstate.write_pid(name)


def spusti_delavca(name: str) -> None:
    runstate.clear_step()
    runstate.remove_pid(name)


def spawn_auto_kill(n: Nastavitve) -> None:
    """Rehearsal helper: KILL_AT=PreveriPriloge:VL-2026-0050 launches the kill script detached, once per reset."""
    if not n.kill_at:
        return
    marker = runstate.RUN_DIR / "auto-kill-armed"
    if marker.exists():
        console.print("[dim]auto-kill je bil v tej vaji že sprožen (make reset ga ponastavi)[/]")
        return
    runstate.ensure_dirs()
    marker.touch()
    delay = min(1.5, max(0.2, n.malica_seconds / 2))
    subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "kill_during.py"), "--at", n.kill_at, "--delay", str(delay)],
        start_new_session=True,
    )
    console.print(f"[dim]auto-kill armed at {n.kill_at} (+{delay:g} s)[/]")


def kratka_pot(path: str) -> str:
    try:
        return str(Path(path).relative_to(ROOT))
    except ValueError:
        return path


def izpisi_izide(outputs: list) -> None:
    for out in outputs:
        if isinstance(out, dict) and "stevilka" in out:
            o = Odlocba.model_validate(out)
            console.print(f"[bold green]✔ {o.vloga_id} → {o.stevilka} · {kratka_pot(o.pdf_path)}[/]")
        elif isinstance(out, dict) and out.get("stanje") == "poziv_k_dopolnitvi":
            console.print(f"[bold red]✘ {out['vloga_id']} · poziv k dopolnitvi: {escape(', '.join(out['manjkajoce']))}[/]")
        else:
            console.print(f"[bold red]✘ {escape(str(out))}[/]")


def pokazi_takse() -> None:
    ledger = runstate.OUT_DIR / "takse.log"
    console.rule("Zaračunane takse (out/takse.log)")
    if not ledger.exists():
        console.print("(nič)")
        return
    for line in ledger.read_text(encoding="utf-8").splitlines():
        console.print(escape(line))
