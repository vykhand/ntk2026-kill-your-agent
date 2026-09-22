import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _():
    import contextlib
    import inspect
    import io
    import time

    import marimo as mo
    from agent_framework import WorkflowContext

    from lipica import fixtures_io
    from lipica.stage import blocks, checks, dag, process, terminal
    from lipica.workflow import PreveriPriloge, build_workflow

    return (
        PreveriPriloge,
        WorkflowContext,
        blocks,
        build_workflow,
        checks,
        contextlib,
        dag,
        fixtures_io,
        inspect,
        io,
        mo,
        process,
        terminal,
        time,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Build it
    **Microsoft Agent Framework**: executors, edges, context — the graph the framework draws for you,
    not one we hand-drew.
    """)
    return


@app.cell(hide_code=True)
def _(checks, mo):
    mo.ui.table(
        [{"preverba": p.ime, "stanje": "OK" if p.ok else "—", "podrobnost": p.podrobnost} for p in checks.trak()],
        selection=None,
        pagination=False,
        show_download=False,
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### The morning queue
    Two applications, in order. The second one is where notebook `02_crash` lands the kill.
    """)
    return


@app.cell(hide_code=True)
def _(fixtures_io, mo):
    _vrstice = []
    for _vloga_id in fixtures_io.JUTRANJA_VRSTA:
        _vloga = fixtures_io.vloga(_vloga_id)
        _stranka = fixtures_io.stranka(_vloga.stranka_id)
        _vrstice.append(
            {
                "vloga": _vloga.id,
                "stranka": _stranka.ime,
                "postopek": f"{_vloga.postopek} · {_vloga.naziv}",
                "priloge": ", ".join(_vloga.priloge),
            }
        )
    mo.ui.table(_vrstice, selection=None, pagination=False, show_download=False, label="jutranja vrsta")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### An executor is a step
    `@handler` marks the method MAF calls when a message arrives; `ctx` is how the step talks to the
    rest of the graph. Real source, straight from `lipica.workflow`.
    """)
    return


@app.cell(hide_code=True)
def _(PreveriPriloge, inspect, mo):
    mo.md(f"""
    ```python\n{inspect.getsource(PreveriPriloge)}\n```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Context: send · yield · ask a human
    Three verbs cover every executor. `WorkflowContext`'s own bodies are MAF's internal tracing —
    the signature and its first line of doc are the part that matters here.
    """)
    return


@app.cell(hide_code=True)
def _(WorkflowContext, blocks, mo):
    _sig = "\n\n".join(blocks.podpis(getattr(WorkflowContext, m)) for m in ("send_message", "yield_output", "request_info"))
    mo.md(f"```python\n{_sig}\n```")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### Edges: `WorkflowBuilder`
    Typed messages flow along the edges you declare. `build_workflow` is the office's whole graph,
    in one function.
    """)
    return


@app.cell(hide_code=True)
def _(build_workflow, inspect, mo):
    mo.md(f"""
    ```python\n{inspect.getsource(build_workflow)}\n```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## The interactive DAG
    MAF draws the picture (`WorkflowViz(workflow).to_mermaid()`); the checkboxes below only decide
    which edges exist. Off: the base chain. On: the rejection loop, then the dual-signature fan-in.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    zavrnitev_cb = mo.ui.checkbox(value=False, label="+ rejection loop (ČakanjeNaŽig → PreveriPriloge)")
    dvojna_cb = mo.ui.checkbox(value=False, label="+ two signatures (referent + vodja oddelka, fan-in)")
    mo.hstack([zavrnitev_cb, dvojna_cb], justify="start", gap=2)
    return dvojna_cb, zavrnitev_cb


@app.cell(hide_code=True)
def _(blocks, dag, dvojna_cb, mo, zavrnitev_cb):
    _varianta = blocks.gradi_varianto(zavrnitev=zavrnitev_cb.value, dvojna=dvojna_cb.value)
    mo.mermaid(dag.mermaid(_varianta, {}))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run one application, in the kernel
    Safe here — nothing gets killed in this notebook. MAF's own event stream fills the table below
    as each executor runs; `02_crash` is where the same run happens as a subprocess instead.
    """)
    return


@app.cell(hide_code=True)
def _(fixtures_io, mo):
    vloga_izbira = mo.ui.dropdown(options=fixtures_io.JUTRANJA_VRSTA, value=fixtures_io.JUTRANJA_VRSTA[0], label="vloga")
    zazeni_btn = mo.ui.run_button(label="▶ Run", kind="success")
    mo.hstack([vloga_izbira, zazeni_btn], justify="start", gap=2)
    return vloga_izbira, zazeni_btn


@app.cell(hide_code=True)
async def _(
    build_workflow,
    contextlib,
    io,
    mo,
    terminal,
    vloga_izbira,
    zazeni_btn,
):
    mo.stop(not zazeni_btn.value, mo.md("*(press Run)*"))

    _wf = build_workflow(idempotent=True, hitl=False)
    _dogodki: list[dict[str, str]] = []
    _buf = io.StringIO()
    # The workflow's own `korak(...)` prints go straight to stdout (rich); captured here so the cell's
    # output is the table below plus a tidy terminal panel, not raw ANSI escapes in marimo's console.
    with contextlib.redirect_stdout(_buf):
        _stream = _wf.run(vloga_izbira.value, stream=True)
        async for _ev in _stream:
            if _ev.type in ("executor_invoked", "executor_completed", "output"):
                _dogodki.append({"dogodek": _ev.type, "izvajalec": _ev.executor_id or "", "podatki": str(_ev.data)[:140]})
        _rezultat = await _stream.get_final_response()
    _odlocbe = [o for o in _rezultat.get_outputs() if isinstance(o, dict) and "stevilka" in o]
    _sporocilo = (
        mo.md(f"**Odločba:** {_odlocbe[0]['stevilka']} · {_odlocbe[0]['taksa_eur']:.2f} €")
        if _odlocbe
        else mo.md("*(ni odločbe — poziv k dopolnitvi)*")
    )
    mo.vstack(
        [
            mo.ui.table(_dogodki, selection=None, pagination=False, show_download=False, label="dogodki"),
            _sporocilo,
            mo.Html(terminal.ansi_to_html(_buf.getvalue(), height="220px")),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## The graph, live: DevUI
    `agent-framework-devui` is MAF's other generated view — the same graph, lighting up per executor
    as a run goes through it.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    devui_btn = mo.ui.run_button(label="Open in DevUI")
    devui_btn
    return (devui_btn,)


@app.cell(hide_code=True)
def _(checks, devui_btn, mo, process, time):
    mo.stop(not devui_btn.value, mo.md("*(press the button)*"))

    _d = process.reattach("devui") or process.start("devui", process.uv_run("python", "scripts/devui.py"))
    _deadline = time.monotonic() + 8
    _preverba = checks.devui()
    while time.monotonic() < _deadline and not _preverba.ok:
        time.sleep(0.3)
        _preverba = checks.devui()
    mo.callout(
        mo.md(f"pid {_d.pid} · [http://127.0.0.1:8090](http://127.0.0.1:8090)"),
        kind="success" if _preverba.ok else "warn",
        title="DevUI" if _preverba.ok else "DevUI is still starting — reload the link in a moment",
    )
    return


if __name__ == "__main__":
    app.run()
