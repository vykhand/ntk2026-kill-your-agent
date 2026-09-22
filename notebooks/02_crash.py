import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import inspect
    import subprocess

    import marimo as mo

    from lipica import runstate
    from lipica.hosts.inprocess import run as inprocess_run
    from lipica.pravilnik import ROOT
    from lipica.stage import checks, dag, ledger, process, terminal
    from lipica.workflow import IzdajOdlocbo, build_workflow

    return (
        IzdajOdlocbo,
        ROOT,
        build_workflow,
        checks,
        dag,
        inprocess_run,
        inspect,
        ledger,
        mo,
        process,
        runstate,
        subprocess,
        terminal,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Kill it
    `kill -9` mid-check, in-process: the step in flight is lost, and the fee is charged twice.
    """)
    return


@app.cell(hide_code=True)
def _(checks, mo):
    mo.ui.table(
        [{"preverba": p.ime, "stanje": "OK" if p.ok else "—", "podrobnost": p.podrobnost} for p in checks.trak(worker_name="act1")],
        selection=None,
        pagination=False,
        show_download=False,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### The fragile baseline
    `uv run act1` runs the morning queue in-process, one application after another — nothing
    survives between executors. Real source, `lipica.hosts.inprocess.run`.
    """)
    return


@app.cell(hide_code=True)
def _(inprocess_run, inspect, mo):
    mo.md(f"""
    ```python\n{inspect.getsource(inprocess_run)}\n```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### The side effect is not idempotent
    `IzdajOdlocbo(idempotent=False)`: every issue gets a random number. Re-run the same
    application and it is a *second* decision, a *second* fee — not a repeat of the first.
    """)
    return


@app.cell(hide_code=True)
def _(IzdajOdlocbo, inspect, mo):
    mo.md(f"""
    ```python\n{inspect.getsource(IzdajOdlocbo)}\n```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    `checkpoint_storage=` would save state after each step — but nobody notices the crash, and
    nobody calls resume. A save file with no one to reload it.
    """)
    return


@app.cell(hide_code=True)
def _(mo, process):
    get_delavec, set_delavec = mo.state(process.reattach("act1"))
    return get_delavec, set_delavec


@app.cell(hide_code=True)
def _(get_delavec, mo):
    _d = get_delavec()
    _teka = _d is not None and _d.alive()
    start_btn = mo.ui.run_button(label="▶ Start queue", kind="success", disabled=_d is not None)
    kill_btn = mo.ui.run_button(label="☠ kill -9", kind="danger", disabled=not _teka)
    again_btn = mo.ui.run_button(label="▶ Start again", kind="success", disabled=_d is None or _teka)
    reset_btn = mo.ui.run_button(label="⟲ Reset", kind="warn")
    _ukaz = f"$ kill -9 {_d.pid}" if _teka else "$ kill -9 <pid>"
    mo.vstack(
        [
            mo.hstack([start_btn, kill_btn, again_btn, reset_btn], justify="start", gap=2),
            mo.md(f"```\n{_ukaz}\n```"),
        ]
    )
    return again_btn, kill_btn, reset_btn, start_btn


@app.cell(hide_code=True)
def _(mo, process, set_delavec, start_btn):
    mo.stop(not start_btn.value, mo.md("*(press Start queue)*"))
    set_delavec(process.start("act1", process.uv_run("act1")))
    mo.md("started `uv run act1`.")
    return


@app.cell(hide_code=True)
def _(again_btn, mo, process, set_delavec):
    mo.stop(not again_btn.value, mo.md("*(press Start again once it has died)*"))
    set_delavec(process.start("act1", process.uv_run("act1")))
    mo.md("started `uv run act1` again — from the top of the queue.")
    return


@app.cell(hide_code=True)
def _(get_delavec, kill_btn, mo, set_delavec):
    mo.stop(not kill_btn.value, mo.md("*(press kill -9 while PreveriPriloge is counting down)*"))
    _d = get_delavec()
    _pid = _d.pid
    _mrtev = _d.kill9()
    set_delavec(_d)
    mo.md(f"`$ kill -9 {_pid}` → referent je šel na malico. " + ("Confirmed dead." if _mrtev else "still alive?!"))
    return


@app.cell(hide_code=True)
def _(ROOT, get_delavec, mo, process, reset_btn, set_delavec, subprocess):
    mo.stop(not reset_btn.value, mo.md("*(press Reset between rehearsals)*"))
    _d = get_delavec()
    if _d is not None and _d.alive():
        _d.kill9()
    _r = subprocess.run(process.uv_run("python", "scripts/reset.py", "--local"), cwd=ROOT, capture_output=True, text=True)
    set_delavec(None)
    mo.md(f"```\n{_r.stdout.strip()}\n```")
    return


@app.cell(hide_code=True)
def _(get_delavec, mo):
    # Ticks at 1 s only while a worker is alive right now; a natural (non-killed) exit keeps it
    # ticking harmlessly until the next Start/Kill/Reset click re-checks — cheap reads, fine for a demo.
    _d = get_delavec()
    ziv = mo.ui.refresh(default_interval="1s") if (_d is not None and _d.alive()) else mo.ui.refresh()
    ziv
    return (ziv,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Live: current step and DAG
    Where it died stays highlighted — nobody advertises the crash.
    """)
    return


@app.cell(hide_code=True)
def _(build_workflow, dag, get_delavec, mo, runstate, terminal, ziv):
    ziv
    _d = get_delavec()
    _korak = runstate.current_step()
    _naslov = f"**{_korak['step']}** · {_korak['vloga_id']}" if _korak else "*(ni v teku)*"
    _wf = build_workflow(idempotent=False, hitl=False)
    _states = dag.states_from_runstate()
    mo.vstack(
        [
            mo.md(f"trenutni korak: {_naslov}"),
            mo.mermaid(dag.mermaid(_wf, _states)),
            mo.Html(terminal.ansi_to_html(_d.tail(100) if _d is not None else "", height="260px")),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Result: the ledger
    Every row past an application's first `vloga_id` is a duplicate — same citizen, two decisions.
    """)
    return


@app.cell(hide_code=True)
def _(ledger, mo, ziv):
    ziv
    _vrstice = ledger.vrstice()
    _pdfji = ledger.pdfji()
    _rows = [
        {
            "čas": v.cas,
            "vloga": v.vloga_id,
            "stranka": v.stranka,
            "odločba": v.stevilka,
            "taksa": v.taksa,
            "podvojeno": "⚠️ da" if v.podvojeno else "",
        }
        for v in _vrstice
    ]
    mo.vstack(
        [
            mo.ui.table(_rows, selection=None, pagination=False, show_download=False, label="out/takse.log"),
            mo.md("PDF-ji: " + ", ".join(p.name for p in _pdfji)) if _pdfji else mo.md("*(še brez odločb)*"),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
