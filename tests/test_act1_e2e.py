"""Runs the real Act 1 entry point (mock LLM, no countdown) in a scratch directory."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_act1(tmp_path: Path, **env: str) -> subprocess.CompletedProcess:
    base = {
        **os.environ,
        "LLM_BACKEND": "mock",
        "MALICA_SECONDS": "0",
        "LIPICA_RUN_DIR": str(tmp_path / "run"),
        "LIPICA_OUT_DIR": str(tmp_path / "out"),
        "KILL_AT": "",
        **env,
    }
    return subprocess.run(
        [sys.executable, "-m", "lipica.hosts.inprocess"], cwd=ROOT, env=base, capture_output=True, text=True, timeout=120
    )


def test_act1_processes_the_queue(tmp_path):
    p = _run_act1(tmp_path)
    assert p.returncode == 0, p.stderr[-2000:]
    out = p.stdout
    assert "Vaša številka:         47" in out and "Vaša številka:         48" in out
    assert out.count("ODLOČBA ODL-2026-") == 2
    ledger = (tmp_path / "out" / "takse.log").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 2 and "Anica Lipovšek" in ledger[0] and "18,90 €" in ledger[0]
    assert ledger[1].endswith("brez takse")
    assert len(list((tmp_path / "out" / "odlocbe").glob("*.pdf"))) == 2


def test_act1_rerun_is_not_idempotent(tmp_path):
    """The fragile baseline: running twice issues the odločbe twice (the point of Act 1)."""
    _run_act1(tmp_path)
    p = _run_act1(tmp_path)
    assert p.returncode == 0, p.stderr[-2000:]
    ledger = (tmp_path / "out" / "takse.log").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 4
    assert len(list((tmp_path / "out" / "odlocbe").glob("*.pdf"))) == 4
    assert "Vaša številka:         49" in p.stdout


def test_act1_with_idempotent_switch(tmp_path):
    """Same code with the Act 2 flag on IzdajOdločbo: the second run charges nothing."""
    _run_act1(tmp_path, LIPICA_ACT1_IDEMPOTENT="1")
    p = _run_act1(tmp_path, LIPICA_ACT1_IDEMPOTENT="1")
    assert "je že izdana" in p.stdout
    ledger = (tmp_path / "out" / "takse.log").read_text(encoding="utf-8").splitlines()
    assert len(ledger) == 2
