"""dag.py: mermaid colouring from a synthetic state dict, and both state-derivation helpers.
No emulator, no model — everything here is built in-memory."""

from datetime import datetime, timezone

from durabletask.history import TaskCompletedEvent, TaskScheduledEvent

from lipica import runstate
from lipica.stage import dag
from lipica.workflow import WORKFLOW_NAME, build_workflow

WF = build_workflow(idempotent=True, hitl=True)
NOW = datetime.now(timezone.utc)


def test_mermaid_includes_workflowviz_text_and_class_defs():
    text = dag.mermaid(WF, {"SprejmiVlogo": dag.DONE})
    assert text.startswith("flowchart TD")
    assert "classDef done" in text and "classDef running" in text
    assert "classDef waiting" in text and "classDef not_reached" in text


def test_mermaid_maps_diacritic_label_to_the_sanitised_node_id():
    # WorkflowViz sanitises "ČakanjeNaŽig" to this exact id (see agent_framework's own visualizer).
    text = dag.mermaid(WF, {"ČakanjeNaŽig": dag.WAITING})
    assert "class n__akanjeNa_ig waiting;" in text


def test_mermaid_defaults_unmentioned_executors_to_not_reached():
    text = dag.mermaid(WF, {})
    assert "class SprejmiVlogo not_reached;" in text


def _scheduled(event_id: int, executor: str) -> TaskScheduledEvent:
    return TaskScheduledEvent(event_id=event_id, timestamp=NOW, name=f"dafx-{WORKFLOW_NAME}-{executor}")


def _completed(event_id: int, task_scheduled_id: int) -> TaskCompletedEvent:
    return TaskCompletedEvent(event_id=event_id, timestamp=NOW, task_scheduled_id=task_scheduled_id, result="{}")


def test_states_from_history_done_vs_in_flight():
    history = [
        _scheduled(1, "SprejmiVlogo"),
        _completed(2, 1),
        _scheduled(3, "PreveriPriloge"),  # killed mid-check: scheduled, never completed
    ]
    states = dag.states_from_history(history)
    assert states == {"SprejmiVlogo": dag.DONE, "PreveriPriloge": dag.RUNNING}


def test_states_from_history_redelivery_keeps_it_running_until_a_second_completion():
    """After a kill and restart, the activity is scheduled again (redelivery); still 'running'
    until one of the TaskScheduled events actually completes."""
    history = [
        _scheduled(1, "PreveriPriloge"),  # first attempt, killed before completion
        _scheduled(2, "PreveriPriloge"),  # redelivered
        _completed(3, 2),
    ]
    assert dag.states_from_history(history) == {"PreveriPriloge": dag.DONE}


def test_states_from_history_ignores_events_outside_this_workflow():
    history = [TaskScheduledEvent(event_id=1, timestamp=NOW, name="dafx-other-workflow-Foo")]
    assert dag.states_from_history(history) == {}


def test_states_from_history_marks_pending_hitl_as_waiting():
    history = [_scheduled(1, "SprejmiVlogo"), _completed(2, 1)]
    states = dag.states_from_history(history, waiting=["ČakanjeNaŽig", "SprejmiVlogo"])
    assert states["ČakanjeNaŽig"] == dag.WAITING
    assert states["SprejmiVlogo"] == dag.WAITING  # `waiting` is a live read; it overrides history, done included


def test_states_from_history_waiting_overrides_a_hitl_executors_own_completed_activity():
    """Verified against the real DTS emulator: ČakanjeNaŽig's own `dafx-vloga-ČakanjeNaŽig` activity
    completes as soon as `ctx.request_info` registers the request — history alone would show it `done`
    even though the orchestration is genuinely parked. `waiting` (the live pending-request read) must win."""
    history = [
        _scheduled(1, "SprejmiVlogo"),
        _completed(2, 1),
        _scheduled(3, "PreveriPriloge"),
        _completed(4, 3),
        _scheduled(5, "ČakanjeNaŽig"),
        _completed(6, 5),  # the dispatch activity is "done" ...
    ]
    states = dag.states_from_history(history, waiting=["ČakanjeNaŽig"])  # ... but a request is still open
    assert states["ČakanjeNaŽig"] == dag.WAITING
    assert states["SprejmiVlogo"] == dag.DONE and states["PreveriPriloge"] == dag.DONE


def test_states_from_runstate_reads_current_step(tmp_path, monkeypatch):
    monkeypatch.setattr(runstate, "RUN_DIR", tmp_path)
    monkeypatch.setattr(runstate, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(runstate, "_STEP", tmp_path / "current-step.json")
    assert dag.states_from_runstate() == {}

    runstate.set_step("VL-2026-0050", "PreveriPriloge")
    assert dag.states_from_runstate() == {"PreveriPriloge": dag.RUNNING}
