"""The stamp, from outside the workflow: find applications parked in ČakanjeNaŽig and answer them.
Used by the phone page (hosts/telefon.py), the CLI (scripts/zig.py) and the act3 console."""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass

from agent_framework_durabletask import DurableWorkflowClient

from lipica import fixtures_io, runstate
from lipica.hosts.durable import TERMINAL, instance_id, make_raw_client
from lipica.workflow import WORKFLOW_NAME

# The scheduler keeps every pending request in the custom status until ALL of them have been answered
# (the orchestrator waits on the whole batch), so the phone and the CLI remember what they already sent.
_ODGOVORJENO = "odgovorjeno.json"


def _odgovorjeno() -> set[str]:
    p = runstate.RUN_DIR / _ODGOVORJENO
    try:
        return set(json.loads(p.read_text())) if p.exists() else set()
    except json.JSONDecodeError:
        return set()


def _zapomni(request_id: str) -> None:
    runstate.ensure_dirs()
    (runstate.RUN_DIR / _ODGOVORJENO).write_text(json.dumps(sorted(_odgovorjeno() | {request_id})))


@dataclass(frozen=True)
class Zahteva:
    instance_id: str
    request_id: str
    data: dict


def make_client(role: str = "zig") -> DurableWorkflowClient:
    return DurableWorkflowClient(make_raw_client(role), workflow_name=WORKFLOW_NAME)


def cakajoce(client: DurableWorkflowClient) -> list[Zahteva]:
    """Every application (by fixture id) that is RUNNING and has a pending stamp request."""
    found: list[Zahteva] = []
    ze = _odgovorjeno()
    for vloga_id in fixtures_io.vloge():
        iid = instance_id(vloga_id)
        status = client.get_runtime_status(iid)
        if status is None or status in TERMINAL:
            continue
        for req in client.get_pending_hitl_requests(iid):
            data = req.get("data") or {}
            if isinstance(data, dict) and req["request_id"] not in ze:
                found.append(Zahteva(iid, req["request_id"], data))
    return found


def odgovori(client: DurableWorkflowClient, z: Zahteva, *, odobreno: bool, odobril: str, opomba: str = "", dopolnitev: list[str] | None = None) -> dict:
    response = {"odobreno": odobreno, "odobril": odobril, "opomba": opomba, "dopolnitev": dopolnitev or []}
    client.send_hitl_response(z.instance_id, z.request_id, response)
    _zapomni(z.request_id)
    return response


def lan_ip() -> str:
    """The address a phone on the same hotspot can reach; no packet is sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
