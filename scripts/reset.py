"""Clean slate between rehearsals: queue counter, odločbe, fee ledger, run state, and the demo's
orchestration instances in the DTS emulator.

    uv run python scripts/reset.py            # everything
    uv run python scripts/reset.py --local    # files only, leave the emulator alone

Finished instances are purged through the API. An interrupted (still RUNNING) instance cannot be purged,
and against the emulator it cannot be terminated without a worker either, so the container is restarted
instead: its state lives in memory only, so that is a full wipe (a few seconds). Against a cloud scheduler
(Act 5) there is no container, and termination works without a worker, so it terminates and then purges.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lipica import fixtures_io, runstate  # noqa: E402

TERMINAL = {"COMPLETED", "FAILED", "TERMINATED"}


def reset_files() -> None:
    for d in (runstate.RUN_DIR, runstate.OUT_DIR):
        if d.exists():
            shutil.rmtree(d)
            # LIPICA_RUN_DIR/LIPICA_OUT_DIR may point outside ROOT (isolated test/notebook runs) —
            # relative_to() would raise then, so fall back to the absolute path.
            try:
                shown = d.relative_to(ROOT)
            except ValueError:
                shown = d
            print("removed", shown)
    runstate.ensure_dirs()


def restart_emulator() -> bool:
    print("running instance found: restarting the emulator container (in-memory state, full wipe) ...")
    r = subprocess.run(["docker", "compose", "restart", "dts-emulator"], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print("docker compose restart failed:", r.stderr.strip()[-300:])
        return False
    from lipica.hosts.durable import make_raw_client

    for _ in range(60):
        try:
            with urllib.request.urlopen("http://localhost:8082/", timeout=2) as resp:
                if resp.status != 200:
                    raise OSError("dashboard not ready")
            make_raw_client("reset").get_orchestration_state("probe", fetch_payloads=False)  # gRPC ready too
            print("emulator is back")
            return True
        except Exception:
            pass
        time.sleep(1)
    print("emulator did not come back within 60 s")
    return False


def reset_emulator() -> bool:
    from lipica.hosts.durable import instance_id, make_raw_client, v_oblaku

    try:
        raw = make_raw_client("reset")
        states = {}
        for vloga_id in fixtures_io.vloge():  # every application any act may have started
            st = raw.get_orchestration_state(instance_id(vloga_id), fetch_payloads=False)
            if st is not None:
                states[instance_id(vloga_id)] = st.runtime_status.name
    except Exception as e:  # emulator down is fine for Act 1 rehearsals
        print(f"(emulator not reset: {type(e).__name__}: {e})")
        return False
    if not states:
        print("emulator: nothing to purge")
        return True
    if any(s not in TERMINAL for s in states.values()):
        if not v_oblaku():
            return restart_emulator()
        # No container to restart in Act 5. A real scheduler will terminate a running orchestration
        # without a worker attached, so ask it to, then fall through and purge.
        for iid, st in states.items():
            if st in TERMINAL:
                continue
            try:
                raw.terminate_orchestration(iid, output="reset")
                print(f"terminated {iid} (was {st})")
            except Exception as e:
                print(f"could not terminate {iid}: {type(e).__name__}: {e}")
        time.sleep(3)  # termination is asynchronous; give the scheduler a moment before purging
    ok = True
    for iid, st in states.items():
        try:
            res = raw.purge_orchestration(iid)
            print(f"purged {iid} (was {st}, deleted={res.deleted_instance_count})")
        except Exception as e:
            ok = False
            print(f"could not purge {iid}: {type(e).__name__}: {e}")
    return ok


def main() -> None:
    reset_files()
    ok = True if "--local" in sys.argv else reset_emulator()
    print("Čista miza. Naslednji listek bo št. 47." if ok else "Miza ni čisto čista, glej zgoraj.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
