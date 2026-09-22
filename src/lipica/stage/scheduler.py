"""The stage: what the Durable Task scheduler currently knows about every application in the queue.

Reuses `lipica.hosts.durable` for the client/raw pair, exactly like `uv run act2`/`act3` do, so a
notebook's table shows the same reality the terminal fallback would. Honours
`DTS_ENDPOINT`/`DTS_TASKHUB`/`DTS_SUBSCRIPTION`/`DTS_TENANT` (see `scripts/act5_env.sh`), so notebook 06 points the same
functions at the Azure scheduler just by setting those first. Pending stamp requests are read the
same way `lipica.hosts.zig_api.cakajoce` reads them (the phone's own API) — this module adds the
per-application table and the live-DAG glue on top.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_framework_durabletask import DurableWorkflowClient
from durabletask.azuremanaged.client import DurableTaskSchedulerClient
from durabletask.history import TaskScheduledEvent

from lipica.hosts.durable import TERMINAL, instance_id, make_raw_client
from lipica.stage import dag
from lipica.workflow import WORKFLOW_NAME

_ACTIVITY_PREFIX = f"dafx-{WORKFLOW_NAME}-"


@dataclass(frozen=True)
class Vrstica:
    """One row of the queue table: what the scheduler remembers about one application right now."""

    vloga_id: str
    instance_id: str
    status: str | None  # None: no orchestration started yet in this run
    zadnja_aktivnost: str | None  # most recently scheduled executor id, or None
    caka_na_zig: int  # count of open stamp requests (>0 only while status is non-terminal)


def client_pair(role: str = "nb") -> tuple[DurableWorkflowClient, DurableTaskSchedulerClient]:
    """The same client pair the CLI hosts build, against whichever scheduler DTS_ENDPOINT points at."""
    raw = make_raw_client(role)
    return DurableWorkflowClient(raw, workflow_name=WORKFLOW_NAME), raw


def pending_executors(client: DurableWorkflowClient, iid: str) -> set[str]:
    """Executor ids with an open `request_info` on this instance right now. Guarded like
    `zadnja_aktivnost`/`stanja_dag`'s own history fetch: a live panel polls this every second, and a
    transient gRPC hiccup must not crash the cell — empty is the same "nothing new to show" as a fresh read."""
    try:
        pending = client.get_pending_hitl_requests(iid)
    except Exception:
        return set()
    return {r["source_executor_id"] for r in pending if r.get("source_executor_id")}


def zadnja_aktivnost(raw: DurableTaskSchedulerClient, iid: str) -> str | None:
    """The most recently *scheduled* activity's executor id — the table's 'current step' column."""
    try:
        history = raw.get_orchestration_history(iid)
    except Exception:
        return None
    scheduled = [e for e in history if isinstance(e, TaskScheduledEvent) and e.name.startswith(_ACTIVITY_PREFIX)]
    return scheduled[-1].name[len(_ACTIVITY_PREFIX) :] if scheduled else None


def tabela(client: DurableWorkflowClient, raw: DurableTaskSchedulerClient, vloge: list[str]) -> list[Vrstica]:
    """One row per application in `vloge` (e.g. `fixtures_io.JUTRANJA_VRSTA`), in that order."""
    rows: list[Vrstica] = []
    for vloga_id in vloge:
        iid = instance_id(vloga_id)
        status = client.get_runtime_status(iid)
        pending = pending_executors(client, iid) if status is not None and status not in TERMINAL else set()
        rows.append(
            Vrstica(
                vloga_id=vloga_id,
                instance_id=iid,
                status=status,
                zadnja_aktivnost=zadnja_aktivnost(raw, iid) if status else None,
                caka_na_zig=len(pending),
            )
        )
    return rows


def stanja_dag(client: DurableWorkflowClient, raw: DurableTaskSchedulerClient, vloga_id: str) -> dict[str, str]:
    """Glue for the live DAG: this instance's history + pending requests -> `dag.states_from_history`."""
    iid = instance_id(vloga_id)
    try:
        history = raw.get_orchestration_history(iid)
    except Exception:
        history = []
    return dag.states_from_history(history, waiting=pending_executors(client, iid))
