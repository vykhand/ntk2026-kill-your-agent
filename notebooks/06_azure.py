import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="06 · Scheduler in Azure")


@app.cell(hide_code=True)
def _():
    import dataclasses
    import inspect
    import os
    import subprocess

    import marimo as mo

    from lipica import fixtures_io
    from lipica.hosts import durable
    from lipica.pravilnik import ROOT
    from lipica.stage import checks, dag, ledger, process, scheduler, terminal
    from lipica.stage.dashboard import Act5NiPripravljen, act5_env, prijazna_napaka
    from lipica.workflow import build_workflow

    WORKER = "nb06"
    return (
        Act5NiPripravljen,
        ROOT,
        WORKER,
        act5_env,
        build_workflow,
        checks,
        dag,
        dataclasses,
        durable,
        fixtures_io,
        inspect,
        ledger,
        mo,
        os,
        prijazna_napaka,
        process,
        scheduler,
        subprocess,
        terminal,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Same code, scheduler in Azure

    `03_durable` against the Durable Task emulator; this notebook, against a real **Durable Task
    Scheduler** in Sweden Central. Only the scheduler moves — the worker still runs on this laptop,
    so `kill -9` still lands on a local process, but the state it was holding is provably not here.
    """)
    return


@app.cell(hide_code=True)
def _(WORKER, checks, mo):
    _trak = [checks.model(), checks.worker(WORKER)]
    mo.hstack(
        [mo.stat(value="✓" if p.ok else "✗", label=p.ime, caption=p.podrobnost, bordered=True) for p in _trak],
        justify="start",
        gap=1,
    )
    return


@app.cell(hide_code=True)
def _(durable, inspect, mo):
    mo.md(f"""
    **The only difference: endpoint + credential.** Same `Workflow`, same `DurableTaskSchedulerWorker`
    `03_durable` already uses — one function picks the endpoint and, in Azure, a credential.
    Azure Functions was tried first and rejected instead: it refuses non-ASCII function names, so
    `dafx-vloga-ČakanjeNaŽig` never loads. The Durable Task Scheduler has no such
    restriction, so the worker keeps running right here.
    ```python
    {inspect.getsource(durable.dts_kwargs)}
    ```
    """)
    return


@app.cell(hide_code=True)
def _(Act5NiPripravljen, act5_env, os):
    try:
        _env = act5_env()
        os.environ.update(_env)
        azd_napaka = None
    except Act5NiPripravljen as e:
        azd_napaka = str(e)
    return (azd_napaka,)


@app.cell(hide_code=True)
def _(azd_napaka, durable, mo, os):
    if azd_napaka:
        _out = mo.callout(
            mo.md(f"{azd_napaka}\n\nSee `act5/README.md` — `cd act5 && azd provision` (once)."),
            kind="warn",
            title="No Azure scheduler environment yet",
        )
    else:
        _out = mo.md(
            f"endpoint `{os.environ.get('DTS_ENDPOINT')}`  ·  task hub `{os.environ.get('DTS_TASKHUB', 'default')}`"
            f"  ·  [open the scheduler in the portal]({durable.dashboard()})"
        )
    _out
    return


@app.cell(hide_code=True)
def _(azd_napaka, mo):
    start_btn = mo.ui.run_button(label="Start worker + queue  (uv run act2, against Azure)", kind="success", disabled=bool(azd_napaka))
    again_btn = mo.ui.run_button(label="Start again", kind="success", disabled=bool(azd_napaka))
    kill_btn = mo.ui.run_button(label="kill -9", kind="danger", disabled=bool(azd_napaka))
    reset_btn = mo.ui.run_button(label="Reset  (scripts/reset.py)", kind="warn", disabled=bool(azd_napaka))
    mo.vstack(
        [
            mo.hstack([start_btn, again_btn, kill_btn, reset_btn], justify="start", gap=1),
            mo.md("*Reset acts on whichever scheduler `DTS_ENDPOINT` currently points at — including Azure.*"),
        ]
    )
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
    mo.md(f"started **{WORKER}** · pid `{_d.pid}` (against Azure — `DTS_ENDPOINT` carried through its environment)")
    return


@app.cell(hide_code=True)
def _(delavec_state, kill_btn, mo, set_delavec):
    mo.stop(not kill_btn.value)
    _d = delavec_state()
    mo.stop(_d is None, mo.md("*No worker to kill.*"))
    _pid = _d.pid
    _d.kill9()
    set_delavec(_d)
    mo.md(f"`$ kill -9 {_pid}`   ·   confirmed dead: **{not _d.alive()}**   ·   the orchestration is still in Azure")
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
def _(
    azd_napaka,
    dataclasses,
    fixtures_io,
    mo,
    prijazna_napaka,
    scheduler,
    zivo,
):
    zivo
    if azd_napaka:
        _out = mo.md("*(no Azure environment — see above)*")
    else:
        try:
            _client, _raw = scheduler.client_pair("nb06")
            _vrstice = scheduler.tabela(_client, _raw, fixtures_io.JUTRANJA_VRSTA)
            _out = mo.ui.table(
                [dataclasses.asdict(v) for v in _vrstice],
                selection=None,
                label="the scheduler's own view of the queue (Azure)",
            )
        except Exception as e:
            _out = mo.callout(mo.md(prijazna_napaka(e)), kind="danger", title="Status query failed")
    _out
    return


@app.cell(hide_code=True)
def _(fixtures_io, mo):
    vloga_izbira = mo.ui.dropdown(
        options=fixtures_io.JUTRANJA_VRSTA, value=fixtures_io.JUTRANJA_VRSTA[-1], label="live DAG for"
    )
    vloga_izbira
    return (vloga_izbira,)


@app.cell(hide_code=True)
def _(
    azd_napaka,
    build_workflow,
    dag,
    mo,
    prijazna_napaka,
    scheduler,
    vloga_izbira,
    zivo,
):
    zivo
    if azd_napaka:
        _out = mo.md("*(no Azure environment — see above)*")
    else:
        try:
            _wf = build_workflow(idempotent=True, hitl=False)
            _client, _raw = scheduler.client_pair("nb06")
            _stanja = scheduler.stanja_dag(_client, _raw, vloga_izbira.value)
            _out = mo.mermaid(dag.mermaid(_wf, _stanja))
        except Exception as e:
            _out = mo.callout(mo.md(prijazna_napaka(e)), kind="danger", title="Status query failed")
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
                "**Exactly one fee per application** — no duplicate row above, same as `03_durable`. "
                "Only the scheduler moved; the idempotency guarantee did not change."
                if _podvojene == 0
                else f"**{_podvojene} duplicate fee(s)** flagged above — that should not happen."
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
