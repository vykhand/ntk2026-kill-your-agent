"""Acts 2 and 3: the durable host. `uv run act2`, `uv run act3`

Same workflow object, registered with the Durable Task extension against the local DTS emulator.
One process does both jobs: it hosts the worker (executors run here, so this is what you kill) and
it drives the queue as a client. Instance ids are the application ids, so a restart of the same command
finds the orchestration that was interrupted and simply waits for it to resume.

Act 2: kill -9 during PreveriPriloge, start again: SprejmiVlogo is not re-executed (same ticket number),
PreveriPriloge re-runs from its start, exactly one odločba per application.
Act 3: the workflow parks in ČakanjeNaŽig until the phone answers; the console prints the phone URL and
waits at zero compute. Kill it while parked, start again, tap the phone: it still finishes.
"""

from __future__ import annotations

import logging
import os
import sys
import time

import grpc
from agent_framework_durabletask import DurableAIAgentWorker, DurableWorkflowClient
from durabletask.azuremanaged.client import DurableTaskSchedulerClient
from durabletask.azuremanaged.worker import DurableTaskSchedulerWorker
from rich.markup import escape

from lipica.config import nastavitve
from lipica.console import console, opozorilo
from lipica.fixtures_io import AKT3_DVOJNA_VRSTA, AKT3_VRSTA, JUTRANJA_VRSTA
from lipica.hosts.common import banner, izpisi_izide, pokazi_takse, spawn_auto_kill, spusti_delavca, zasedi_delavca
from lipica.workflow import WORKFLOW_NAME, build_workflow

IDEMPOTENT = True  # idempotent by design from Act 2 on
TERMINAL = {"COMPLETED", "FAILED", "TERMINATED"}
EMULATOR_DASHBOARD = "http://localhost:8082"


class _BrezOdjavnegaOpozorila(logging.Filter):
    """worker.stop() cancels the gRPC work-item stream; durabletask logs that as a WARNING. Not on stage."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "Locally cancelled by application" not in record.getMessage()


def _dts_logger(name: str) -> logging.Logger:
    """durabletask builds its loggers outside the logging hierarchy, so hand it one we control."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO if os.environ.get("DTS_LOG", "").lower() == "info" else logging.WARNING)
    logger.addFilter(_BrezOdjavnegaOpozorila())
    return logger


def endpoint() -> str:
    return os.environ.get("DTS_ENDPOINT", "http://localhost:8080")


def v_oblaku() -> bool:
    """Act 5 runs the same host against a scheduler in Azure; everything else against the emulator."""
    return not endpoint().startswith("http://localhost")


def dashboard() -> str:
    """Where to look while the act runs: the emulator's own page, or the scheduler's blade in the portal."""
    return os.environ.get("DTS_DASHBOARD") or EMULATOR_DASHBOARD


def dts_kwargs(role: str = "worker") -> dict:
    credential = None
    if v_oblaku():
        from azure.identity import AzureCliCredential

        # Pin the tenant. The az CLI holds several logins here and its default drifts between them,
        # so an unpinned credential can hand back a token for the wrong directory mid-demo.
        tenant = os.environ.get("DTS_TENANT")
        credential = AzureCliCredential(tenant_id=tenant) if tenant else AzureCliCredential()
    return dict(
        host_address=endpoint(),
        taskhub=os.environ.get("DTS_TASKHUB", "default"),
        token_credential=credential,
        secure_channel=v_oblaku(),
        logger=_dts_logger(f"lipica.dts.{role}"),
    )


def make_worker(*, hitl: bool = False) -> DurableTaskSchedulerWorker:
    worker = DurableTaskSchedulerWorker(**dts_kwargs())
    DurableAIAgentWorker(worker).configure_workflow(build_workflow(idempotent=IDEMPOTENT, hitl=hitl))
    return worker


def make_raw_client(role: str = "client") -> DurableTaskSchedulerClient:
    return DurableTaskSchedulerClient(**dts_kwargs(role))


def instance_id(vloga_id: str) -> str:
    return vloga_id


def razlog_odpovedi(raw: DurableTaskSchedulerClient, iid: str) -> str:
    st = raw.get_orchestration_state(iid, fetch_payloads=True)
    if st and st.failure_details:
        return st.failure_details.message or st.failure_details.error_type or "neznan razlog"
    return "neznan razlog"


def pregled_vrste(client: DurableWorkflowClient, raw: DurableTaskSchedulerClient, vrsta: list[str]) -> dict[str, str | None]:
    """Tell the story before any executor runs: what the scheduler remembers about each application."""
    stanja = {vid: client.get_runtime_status(instance_id(vid)) for vid in vrsta}
    console.rule("Vrsta po podatkih razporejevalnika")
    for vid, st in stanja.items():
        if st is None:
            console.print(f"  {vid}  nova, še ni v razporejevalniku")
        elif st == "COMPLETED":
            console.print(f"  {vid}  [green]COMPLETED[/]: opravljeno")
        elif st in TERMINAL:
            console.print(f"  {vid}  [red]{st}[/]: {escape(razlog_odpovedi(raw, instance_id(vid)))[:200]} → nov poskus")
        elif client.get_pending_hitl_requests(instance_id(vid)):
            console.print(f"  {vid}  [bold magenta]{st}[/]: čaka na žig, nič se ne izvaja")
        else:
            console.print(f"  {vid}  [bold magenta]{st}[/]: nadaljujem točno tam, kjer se je ustavilo")
    return stanja


def _pocakaj_z_zigom(client: DurableWorkflowClient, iid: str) -> list:
    """Act 3 wait: announce every new stamp request with the phone URL, return outputs when done."""
    from lipica.hosts.zig_api import lan_ip

    announced: set[str] = set()
    while True:
        status = client.get_runtime_status(iid)
        if status in TERMINAL:
            break
        for req in client.get_pending_hitl_requests(iid):
            rid = req["request_id"]
            if rid in announced:
                continue
            announced.add(rid)
            d = req.get("data") or {}
            stanje = "[green]popolna[/]" if d.get("popolna") else "[red]nepopolna[/] · manjka: " + escape(", ".join(d.get("manjkajoce") or []))
            console.rule("⏸  Čakanje na žig" + (f" · podpis: {escape(str(d['podpisnik']))}" if d.get("podpisnik") else ""))
            console.print(f"  {d.get('vloga_id', iid)} · listek {d.get('listek', '?')} · {escape(str(d.get('stranka', '')))} · {escape(str(d.get('postopek', '')))}")
            console.print(f"  preverjanje ({escape(str(d.get('vir', '')))}): {stanje}")
            console.print(f"  [bold]telefon: http://{lan_ip()}:{os.environ.get('ZIG_PORT', '8000')}[/]   ·   terminal: make odobri / make zavrni")
            console.print("  [dim]delovni tok čaka in ne porablja ničesar; nadzorna plošča: orkestracija RUNNING, nobena aktivnost v teku[/]")
        time.sleep(1)
    if status != "COMPLETED":
        raise RuntimeError(status)
    return client.await_workflow_output(iid, timeout_seconds=30) or []


def obdelaj_vrsto(client: DurableWorkflowClient, raw: DurableTaskSchedulerClient, stanja: dict[str, str | None], *, hitl: bool) -> None:
    """Start each application unless it already exists, then wait for it. Sequential, like the counter."""
    for vloga_id, status in stanja.items():
        iid = instance_id(vloga_id)
        console.rule(f"Vloga {vloga_id}  ·  orkestracija {iid}")
        if status is None:
            client.start_workflow(input=vloga_id, instance_id=iid)
        elif status in TERMINAL and status != "COMPLETED":
            raw.purge_orchestration(iid)
            client.start_workflow(input=vloga_id, instance_id=iid)
        try:
            outputs = _pocakaj_z_zigom(client, iid) if hitl else (client.await_workflow_output(iid, timeout_seconds=600) or [])
            izpisi_izide(outputs)
        except RuntimeError:  # the orchestration ended FAILED/TERMINATED: say why, the next run retries it
            opozorilo(f"✘ {iid} je odpovedala: {escape(razlog_odpovedi(raw, iid))[:300]}")
            opozorilo("   naslednji zagon jo pobriše in začne znova")


def run_act(*, name: str, naslov: str, podnaslov: str, vrsta: list[str], hitl: bool) -> None:
    logging.basicConfig(level=logging.WARNING)
    n = nastavitve()
    banner(naslov, podnaslov, n, idempotent=IDEMPOTENT)
    kje = "Azure" if v_oblaku() else "emulator"
    console.print(
        f"[dim]nadzorna plošča: {dashboard()}  ·  taskhub {os.environ.get('DTS_TASKHUB', 'default')} ({kje})[/]"
    )
    zasedi_delavca(name)
    spawn_auto_kill(n)

    raw = make_raw_client()
    client = DurableWorkflowClient(raw, workflow_name=WORKFLOW_NAME)
    try:
        stanja = pregled_vrste(client, raw, vrsta)
    except grpc.RpcError as e:
        kaj = "Preveri `az login` in omrežje." if v_oblaku() else "Zaženi `make emulator`."
        opozorilo(f"Razporejevalnik ni dosegljiv na {endpoint()} ({e.code().name}). {kaj}")
        spusti_delavca(name)
        sys.exit(1)

    worker = make_worker(hitl=hitl)
    worker.start()  # returns immediately; from here on any interrupted activity is redelivered to us
    try:
        obdelaj_vrsto(client, raw, stanja, hitl=hitl)
        pokazi_takse()
    finally:
        spusti_delavca(name)
        worker.stop()


def main() -> None:
    run_act(
        name="act2",
        # Act 5 is this same act against a scheduler in Azure, so the banner has to say which.
        naslov=f"Vstajenje (Durable Task + {'DTS v Azuru' if v_oblaku() else 'DTS emulator'})",
        podnaslov="kill -9 med PreveriPriloge → nadaljevanje s kontrolne točke",
        vrsta=JUTRANJA_VRSTA,
        hitl=False,
    )


def main_act3() -> None:
    run_act(
        name="act3",
        naslov="Čakanje na žig (Durable Task + telefon)",
        podnaslov="delovni tok čaka dneve in ne porabi ničesar; žig pride s telefona",
        vrsta=AKT3_VRSTA,
        hitl=True,
    )


def main_act3_dvojna() -> None:
    run_act(
        name="act3",
        naslov="Dvojna odobritev (referent + vodja oddelka)",
        podnaslov="dva podpisa vzporedno, nato žig: fan-out, fan-in, oba čakata brez porabe",
        vrsta=AKT3_DVOJNA_VRSTA,
        hitl=True,
    )


if __name__ == "__main__":
    main()
