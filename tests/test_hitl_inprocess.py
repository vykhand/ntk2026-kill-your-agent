"""Act 3's pause and loop, in-process with the mock backend: reject with a supplement, then approve."""

import pytest

from lipica import odlocba, runstate
from lipica.workflow import ID_CAKANJE, build_workflow


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


async def test_reject_then_approve_loops_back_and_stamps(scratch):
    wf = build_workflow(idempotent=True, hitl=True)

    r1 = await wf.run("VL-2026-0048")
    reqs = r1.get_request_info_events()
    assert len(reqs) == 1 and reqs[0].source_executor_id == ID_CAKANJE
    assert reqs[0].data["popolna"] is False and reqs[0].data["manjkajoce"] == ["potrdilo o označitvi (čip)"]
    assert r1.get_outputs() == []

    r2 = await wf.run(responses={reqs[0].request_id: {"odobreno": False, "odobril": "test"}})
    reqs2 = r2.get_request_info_events()
    assert len(reqs2) == 1 and reqs2[0].request_id != reqs[0].request_id
    assert reqs2[0].data["popolna"] is True  # the citizen brought the čip, PreveriPriloge ran again

    r3 = await wf.run(responses={reqs2[0].request_id: {"odobreno": True, "odobril": "test"}})
    outs = r3.get_outputs()
    assert len(outs) == 1 and outs[0]["zig"] is True and outs[0]["vloga_id"] == "VL-2026-0048"
    assert (scratch / "out" / "takse.log").read_text(encoding="utf-8").count("\n") == 1


async def test_approve_directly_when_complete(scratch):
    wf = build_workflow(idempotent=True, hitl=True)
    r1 = await wf.run("VL-2026-0047")
    (req,) = r1.get_request_info_events()
    assert req.data["popolna"] is True
    r2 = await wf.run(responses={req.request_id: {"odobreno": True}})
    (out,) = r2.get_outputs()
    assert out["zig"] is True


async def test_auto_mode_still_ends_incomplete_applications(scratch):
    wf = build_workflow(idempotent=True, hitl=False)
    r = await wf.run("VL-2026-0048")
    assert r.get_request_info_events() == []
    (out,) = r.get_outputs()
    assert out["stanje"] == "poziv_k_dopolnitvi"
