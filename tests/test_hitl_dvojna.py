"""Act 3 stretch, in-process: the beehive permit needs two signatures in parallel (fan-out / fan-in)."""

import pytest

from lipica import odlocba, runstate
from lipica.workflow import ID_ZIG_REFERENT, ID_ZIG_VODJA, build_workflow


@pytest.fixture
def scratch(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "mock")
    monkeypatch.setenv("MALICA_SECONDS", "0")
    run, out = tmp_path / "run", tmp_path / "out"
    monkeypatch.setattr(runstate, "RUN_DIR", run)
    monkeypatch.setattr(runstate, "OUT_DIR", out)
    monkeypatch.setattr(runstate, "_COUNTER", run / "listek-counter")
    monkeypatch.setattr(runstate, "_STEP", run / "current-step.json")
    monkeypatch.setattr(odlocba, "OUT_DIR", out)
    return tmp_path


def _by_signer(events):
    return {e.data["podpisnik"]: e for e in events}


async def test_both_sign_in_parallel(scratch):
    wf = build_workflow(idempotent=True, hitl=True)
    r1 = await wf.run("VL-2026-0049")
    reqs = r1.get_request_info_events()
    assert {e.source_executor_id for e in reqs} == {ID_ZIG_REFERENT, ID_ZIG_VODJA}
    signers = _by_signer(reqs)
    assert set(signers) == {"referent", "vodja oddelka"} and all(e.data["popolna"] for e in reqs)

    r2 = await wf.run(responses={e.request_id: {"odobreno": True, "odobril": "test"} for e in reqs})
    (out,) = r2.get_outputs()
    assert out["zig"] is True and out["vloga_id"] == "VL-2026-0049"


async def test_vodja_rejects_then_both_sign(scratch):
    wf = build_workflow(idempotent=True, hitl=True)
    r1 = await wf.run("VL-2026-0049")
    signers = _by_signer(r1.get_request_info_events())
    r2 = await wf.run(responses={
        signers["referent"].request_id: {"odobreno": True},
        signers["vodja oddelka"].request_id: {"odobreno": False, "dopolnitev": ["potrdilo o vpisu v register čebelarjev (overjeno)"]},
    })
    reqs2 = r2.get_request_info_events()
    assert len(reqs2) == 2 and r2.get_outputs() == []  # looped through PreveriPriloge, parked again for both
    assert "potrdilo o vpisu v register čebelarjev (overjeno)" in reqs2[0].data["priloge"]

    r3 = await wf.run(responses={e.request_id: {"odobreno": True} for e in reqs2})
    (out,) = r3.get_outputs()
    assert out["zig"] is True
    assert (scratch / "out" / "takse.log").read_text(encoding="utf-8").count("\n") == 1
