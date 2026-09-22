import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="03 · Bring it back")


@app.cell(hide_code=True)
def _():
    import dataclasses
    import inspect
    import subprocess

    import marimo as mo

    from lipica import fixtures_io
    from lipica.hosts import durable
    from lipica.odlocba import stevilka_odlocbe
    from lipica.pravilnik import ROOT
    from lipica.stage import checks, dag, ledger, process, scheduler, terminal
    from lipica.stage.dashboard import dashboard_iframe, emulator_deep_link, preveri_iframe
    from lipica.workflow import build_workflow

    WORKER = "nb03"
    return (
        ROOT,
        WORKER,
        build_workflow,
        checks,
        dag,
        dashboard_iframe,
        dataclasses,
        durable,
        emulator_deep_link,
        fixtures_io,
        inspect,
        ledger,
        mo,
        preveri_iframe,
        process,
        scheduler,
        stevilka_odlocbe,
        subprocess,
        terminal,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Bring it back

    Same `Workflow` object as `02_crash`, now hosted by the **Durable Task extension**: every
    finished step goes to a checkpointed history, so a killed worker is not a lost worker — a new
    one redelivers the step in flight and carries on. The kill lands during `PreveriPriloge` of the
    second application, `VL-2026-0050`.
    """)
    return


@app.cell(hide_code=True)
def _(WORKER, checks, mo):
    _trak = checks.trak(worker_name=WORKER)
    mo.hstack(
        [mo.stat(value="✓" if p.ok else "✗", label=p.ime, caption=p.podrobnost, bordered=True) for p in _trak],
        justify="start",
        gap=1,
    )
    return


@app.cell(hide_code=True)
def _(durable, inspect, mo):
    mo.md(f"""
    **The worker.** `DurableAIAgentWorker` registers every executor as an activity named
    `dafx-vloga-<executor id>` on the Durable Task extension — the same `Workflow` object, a
    different host.
    ```python
    {inspect.getsource(durable.make_worker)}
    ```
    """)
    return


@app.cell(hide_code=True)
def _(inspect, mo):
    from agent_framework_durabletask import DurableWorkflowClient

    mo.md(
        f"""
        **The client.** The instance id *is* the application id, so starting the same id twice finds
        the interrupted orchestration instead of creating a second one — that is the whole trick.
        ```python
        {inspect.getsource(DurableWorkflowClient.start_workflow)}
        ```
        """
    )
    return


@app.cell(hide_code=True)
def _(inspect, mo, stevilka_odlocbe):
    mo.md(f"""
    **The price.** Delivery is at-least-once, so `PreveriPriloge` — and `IzdajOdločbo` — can run
    twice. The odločba number is derived from the application id, not random: a redelivered issue
    is a no-op.
    ```python
    {inspect.getsource(stevilka_odlocbe)}
    ```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    start_btn = mo.ui.run_button(label="Start worker + queue  (uv run act2)", kind="success")
    again_btn = mo.ui.run_button(label="Start again", kind="success")
    kill_btn = mo.ui.run_button(label="kill -9", kind="danger")
    reset_btn = mo.ui.run_button(label="Reset  (scripts/reset.py)", kind="warn")
    mo.hstack([start_btn, again_btn, kill_btn, reset_btn], justify="start", gap=1)
    return again_btn, kill_btn, reset_btn, start_btn


@app.cell(hide_code=True)
def _(mo):
    delavec_state, set_delavec = mo.state(None)
    return delavec_state, set_delavec


@app.cell(hide_code=True)
def _(WORKER, again_btn, mo, process, set_delavec, start_btn):
    mo.stop(not (start_btn.value or again_btn.value))
    _d = process.reattach(WORKER) or process.start(WORKER, process.uv_run("act2"))
    set_delavec(_d)
    mo.md(f"started **{WORKER}** · pid `{_d.pid}`")
    return


@app.cell(hide_code=True)
def _(delavec_state, kill_btn, mo, set_delavec):
    mo.stop(not kill_btn.value)
    _d = delavec_state()
    mo.stop(_d is None, mo.md("*No worker to kill.*"))
    _pid = _d.pid
    _d.kill9()
    set_delavec(_d)
    mo.md(f"`$ kill -9 {_pid}`   ·   confirmed dead: **{not _d.alive()}**")
    return


@app.cell(hide_code=True)
def _(ROOT, mo, reset_btn, set_delavec, subprocess):
    mo.stop(not reset_btn.value)
    _r = subprocess.run(
        ["uv", "run", "python", "scripts/reset.py"], cwd=str(ROOT), capture_output=True, text=True
    )
    set_delavec(None)
    mo.md(f"```\n{(_r.stdout + _r.stderr).strip()}\n```")
    return


@app.cell(hide_code=True)
def _(delavec_state, mo):
    _d = delavec_state()
    if _d is None:
        _besedilo = "*not started*"
    elif _d.alive():
        _besedilo = f"**running** · pid `{_d.pid}`"
    else:
        _besedilo = f"**stopped** · pid `{_d.pid}` (confirmed dead)"
    mo.md(_besedilo)
    return


@app.cell(hide_code=True)
def _(delavec_state, mo):
    _tece = bool(delavec_state() and delavec_state().alive())
    zivo = mo.ui.refresh(default_interval="1s") if _tece else mo.ui.refresh()
    zivo
    return (zivo,)


@app.cell(hide_code=True)
def _(dataclasses, fixtures_io, mo, scheduler, zivo):
    zivo
    _client, _raw = scheduler.client_pair("nb03")
    _vrstice = scheduler.tabela(_client, _raw, fixtures_io.JUTRANJA_VRSTA)
    mo.ui.table(
        [dataclasses.asdict(v) for v in _vrstice],
        selection=None,
        label="the scheduler's own view of the queue",
    )
    return


@app.cell(hide_code=True)
def _(fixtures_io, mo):
    vloga_izbira = mo.ui.dropdown(
        options=fixtures_io.JUTRANJA_VRSTA, value=fixtures_io.JUTRANJA_VRSTA[-1], label="live DAG for"
    )
    vloga_izbira
    return (vloga_izbira,)


@app.cell(hide_code=True)
def _(build_workflow, dag, mo, scheduler, vloga_izbira, zivo):
    zivo
    _wf = build_workflow(idempotent=True, hitl=False)
    _client, _raw = scheduler.client_pair("nb03")
    _stanja = scheduler.stanja_dag(_client, _raw, vloga_izbira.value)
    mo.mermaid(dag.mermaid(_wf, _stanja))
    return


@app.cell(hide_code=True)
def _(
    dashboard_iframe,
    durable,
    emulator_deep_link,
    mo,
    preveri_iframe,
    vloga_izbira,
):
    _url = emulator_deep_link(durable.dashboard(), vloga_izbira.value)
    _okvir = preveri_iframe(durable.dashboard())
    if _okvir.lahko:
        _out = mo.vstack(
            [
                mo.md(f"DTS dashboard, deep-linked to `{vloga_izbira.value}` — [open in a new tab]({_url})"),
                mo.Html(dashboard_iframe(_url)),
            ]
        )
    else:
        _out = mo.md(f"[Open the DTS dashboard for `{vloga_izbira.value}`]({_url})  \n*(not embedded: {_okvir.razlog})*")
    _out
    return


@app.cell(hide_code=True)
def _(delavec_state, mo, terminal, zivo):
    zivo
    _d = delavec_state()
    mo.Html(terminal.ansi_to_html(_d.tail(300) if _d else ""))
    return


@app.cell(hide_code=True)
def _(dataclasses, ledger, mo, zivo):
    zivo
    _vrstice = ledger.vrstice()
    _podvojene = sum(1 for v in _vrstice if v.podvojeno)
    mo.vstack(
        [
            mo.ui.table([dataclasses.asdict(v) for v in _vrstice], selection=None, label="out/takse.log"),
            mo.md(
                "**Exactly one fee per application** — no duplicate row above. No new čakalni listek "
                "prints in the terminal on the resumed run either: the ticket did not change."
                if _podvojene == 0
                else f"**{_podvojene} duplicate fee(s)** flagged above — that should not happen on the durable host."
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
