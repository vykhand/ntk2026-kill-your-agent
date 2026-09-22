"""kill -9 the demo worker: right now, or the moment a given executor starts.

    uv run python scripts/kill_during.py --now
    uv run python scripts/kill_during.py --at PreveriPriloge
    uv run python scripts/kill_during.py --at PreveriPriloge:VL-2026-0050 --delay 2

The worker advertises its current step in .run/current-step.json (see lipica.runstate.set_step) and
its pid in .run/<act>.pid. SIGKILL only; anything gentler would let the process clean up, and the
whole point is that it must not get the chance.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lipica import runstate  # noqa: E402


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _kill(pid: int, why: str) -> None:
    os.kill(pid, signal.SIGKILL)
    print(f"kill -9 {pid}   # {why}")
    print("Referent je šel na malico.")


def kill_now() -> int:
    pids = sorted(runstate.RUN_DIR.glob("*.pid")) if runstate.RUN_DIR.exists() else []
    live = [(p.stem, int(p.read_text())) for p in pids if _alive(int(p.read_text()))]
    if not live:
        print("Noben delovni proces ne teče (v .run/ ni živih pid-ov).")
        return 0
    for name, pid in live:
        _kill(pid, name)
    return 0


def _matches(step: dict | None, executor: str, vloga_id: str) -> bool:
    return bool(step) and step["step"] == executor and (not vloga_id or step["vloga_id"] == vloga_id) and _alive(step["pid"])


def kill_at(target: str, delay: float, timeout: float) -> int:
    executor, _, vloga_id = target.partition(":")
    deadline = time.time() + timeout
    print(f"Čakam na korak {executor}" + (f" za {vloga_id}" if vloga_id else "") + " ...")
    while time.time() < deadline:
        step = runstate.current_step()
        if _matches(step, executor, vloga_id):
            if delay:
                time.sleep(delay)
            if not _matches(runstate.current_step(), executor, vloga_id):
                print("Korak se je medtem končal; nič ni bilo ubito (skrajšaj --delay ali podaljšaj MALICA_SECONDS).")
                return 1
            _kill(step["pid"], f"{step['step']} {step['vloga_id']}")
            return 0
        time.sleep(0.1)
    print("Korak se v roku ni zgodil; nič ni bilo ubito.")
    return 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--now", action="store_true", help="kill the running worker(s) immediately")
    g.add_argument("--at", metavar="EXECUTOR[:VLOGA]", help="kill when this executor starts")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds to wait after the step starts (default 1.5)")
    ap.add_argument("--timeout", type=float, default=300, help="give up after N seconds (default 300)")
    a = ap.parse_args()
    sys.exit(kill_now() if a.now else kill_at(a.at, a.delay, a.timeout))


if __name__ == "__main__":
    main()
