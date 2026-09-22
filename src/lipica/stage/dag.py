"""The live DAG: MAF draws the graph (`WorkflowViz(workflow).to_mermaid()`), we only colour it.

No hand-drawn diagram anywhere here — if the workflow changes, the picture changes with it. State
comes from the two hosts the notebooks drive: `states_from_runstate` reads the in-process host's
`.run/current-step.json`; `states_from_history` reads a durable orchestration's history plus its
pending human-in-the-loop requests — the latter always wins, since a parked executor's own dispatch
activity already reads "done" in history by the time it is waiting (see `states_from_history`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from agent_framework import Workflow, WorkflowViz

from lipica import runstate

# Node state -> NTK palette. mo.mermaid renders classDef/class lines like any other mermaid text.
DONE, RUNNING, WAITING, NOT_REACHED = "done", "running", "waiting", "not_reached"

_CLASS_STYLE = {
    DONE: "fill:#B0CA07,stroke:#0F8A3C,color:#1A1A1A",
    RUNNING: "fill:#E2DB2A,stroke:#1A1A1A,color:#1A1A1A",
    WAITING: "fill:#7C549D,stroke:#1A1A1A,color:#F9F9F9",
    NOT_REACHED: "fill:#D9D9D9,stroke:#8A8A8A,color:#4A4A4A",
}

# The exact sanitiser WorkflowViz uses for node ids (agent_framework._workflows._visualization),
# copied rather than imported because it is a nested function, not a public one: a label like
# "ČakanjeNaŽig" becomes "n__akanjeNa_ig" and that is the id `class` lines must target.
_NON_ID_CHARS = re.compile(r"[^0-9A-Za-z_]")


def _node_id(label: str) -> str:
    s = _NON_ID_CHARS.sub("_", label)
    if not s or not s[0].isalpha():
        s = f"n_{s}"
    return s


def mermaid(workflow: Workflow, states: dict[str, str]) -> str:
    """MAF's mermaid text, plus classDef/class lines colouring every executor by `states[executor_id]`
    (default `not_reached`). One string; `mo.mermaid(...)` renders it as-is."""
    lines = [WorkflowViz(workflow).to_mermaid(), ""]
    for state, style in _CLASS_STYLE.items():
        lines.append(f"classDef {state} {style};")
    for executor_id in workflow.executors:
        state = states.get(executor_id, NOT_REACHED)
        lines.append(f"class {_node_id(executor_id)} {state};")
    return "\n".join(lines)


def states_from_runstate() -> dict[str, str]:
    """The in-process host (`lipica.hosts.inprocess`) only ever advertises the executor running right
    now (`runstate.set_step`), and never clears it on a crash — so after a kill -9 this keeps naming
    the step it died in, which is exactly what should stay highlighted until `make reset`."""
    step = runstate.current_step()
    return {step["step"]: RUNNING} if step else {}


def states_from_history(history_events: Iterable[object], *, waiting: Iterable[str] = ()) -> dict[str, str]:
    """Durable state per executor id, from an orchestration's history plus its pending HITL requests.

    An activity is `dafx-<workflow>-<executorId>`: TaskScheduled without a matching TaskCompleted is
    `running` (in flight — or, after a kill and a restart, redelivered and about to be); a matching
    TaskCompleted is `done`. A park (`ctx.request_info`) is *not* silent in history the way the docs
    suggest: verified against the real emulator, the executor's own dispatch activity (e.g.
    `dafx-vloga-ČakanjeNaŽig`) completes as soon as it registers the request, while the orchestration
    stays RUNNING and genuinely parked — so a "done" reading from history can be stale for exactly the
    executor that is currently waiting. `waiting` (from `DurableWorkflowClient.get_pending_hitl_requests`,
    the `source_executor_id` field — always a live read, fetched alongside this same history) is the
    authoritative signal and overrides whatever history says, `done` included.
    """
    from durabletask.history import TaskCompletedEvent, TaskScheduledEvent

    from lipica.workflow import WORKFLOW_NAME

    prefix = f"dafx-{WORKFLOW_NAME}-"
    scheduled_by: dict[int, str] = {}
    states: dict[str, str] = {}
    for ev in history_events:
        if isinstance(ev, TaskScheduledEvent) and ev.name.startswith(prefix):
            executor_id = ev.name[len(prefix) :]
            scheduled_by[ev.event_id] = executor_id
            states.setdefault(executor_id, RUNNING)
    for ev in history_events:
        if isinstance(ev, TaskCompletedEvent):
            executor_id = scheduled_by.get(ev.task_scheduled_id)
            if executor_id:
                states[executor_id] = DONE
    for executor_id in waiting:
        states[executor_id] = WAITING
    return states
