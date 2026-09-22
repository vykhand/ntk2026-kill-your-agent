import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Wait for a human")


@app.cell(hide_code=True)
def _():
    import inspect

    import marimo as mo

    from lipica import fixtures_io
    from lipica.hosts import zig_api
    from lipica.stage import cakanje, checks, dag, process, scheduler, terminal
    from lipica.workflow import CakanjeNaZig, build_workflow

    WORKFLOW = build_workflow(idempotent=True, hitl=True)  # the graph shape never depends on hitl/idempotent
    WORKER = "act3"  # same top-level .run/act3.pid whether it's uv_run("act3") or uv_run("act3-dvojna")
    TELEFON = "zig"
    client, raw = scheduler.client_pair("nb-04")  # one pair, reused by every live cell below
    return (
        CakanjeNaZig,
        TELEFON,
        WORKER,
        WORKFLOW,
        cakanje,
        checks,
        client,
        dag,
        fixtures_io,
        inspect,
        mo,
        process,
        raw,
        scheduler,
        terminal,
        zig_api,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Wait for a human

    `ctx.request_info(...)` parks the workflow — no loop, no timer, no cost — until a human answers.
    Reject and the citizen's application loops back through `PreveriPriloge`; the beehive permit needs
    two signatures, in parallel.
    """)
    return


@app.cell(hide_code=True)
def _(WORKER, checks, mo):
    mo.ui.table(
        [{"preverba": p.ime, "v redu": "da" if p.ok else "ne", "podrobnosti": p.podrobnost} for p in checks.trak(WORKER)],
        selection=None,
        pagination=False,
        label="status",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## The wait, in the workflow's own source
    """)
    return


@app.cell(hide_code=True)
def _(CakanjeNaZig, inspect, mo):
    mo.md(
        """
        `PreveriPriloge` hands `ČakanjeNaŽig` a `PreverjanjePrilog`. Auto-stamped while `hitl=False`;
        from here on it asks a human and simply stops:
        """
    )
    mo.ui.code_editor(value=inspect.getsource(CakanjeNaZig.cakaj), disabled=True, show_copy_button=False, min_height=260)
    return


@app.cell(hide_code=True)
def _(CakanjeNaZig, inspect, mo):
    mo.md("Whoever answers — the phone, `zig_api.odgovori`, or the buttons below — resumes here:")
    mo.ui.code_editor(value=inspect.getsource(CakanjeNaZig.odgovor), disabled=True, show_copy_button=False, min_height=180)
    return


@app.cell(hide_code=True)
def _(CakanjeNaZig, inspect, mo):
    mo.md(
        "The beehive permit needs the referent **and** the vodja oddelka: `ČakanjeNaŽig` fans out to two "
        "`Podpisnik` executors and `zberi` collects both before it decides:"
    )
    mo.ui.code_editor(value=inspect.getsource(CakanjeNaZig.zberi), disabled=True, show_copy_button=False, min_height=220)
    return


@app.cell(hide_code=True)
def _(WORKFLOW, dag, mo):
    mo.md(
        "Same graph MAF draws everywhere else in this talk — the rejection loop and the two signers are "
        "real edges, not an illustration:"
    )
    mo.mermaid(dag.mermaid(WORKFLOW, {}))
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run it
    """)
    return


@app.cell(hide_code=True)
def _(TELEFON, WORKER, mo, process):
    get_delavec, set_delavec = mo.state(process.reattach(WORKER))
    get_telefon, set_telefon = mo.state(process.reattach(TELEFON))
    return get_delavec, get_telefon, set_delavec, set_telefon


@app.cell(hide_code=True)
def _(mo):
    dvojna = mo.ui.switch(label="beehive permit — dual signature (`uv run act3-dvojna`)", value=False)
    dvojna
    return (dvojna,)


@app.cell(hide_code=True)
def _(dvojna, fixtures_io):
    vloga_v_pregledu = fixtures_io.AKT3_DVOJNA_VRSTA[0] if dvojna.value else fixtures_io.AKT3_VRSTA[0]
    return (vloga_v_pregledu,)


@app.cell(hide_code=True)
def _(mo):
    zacni_delavca = mo.ui.run_button(label="▶ Start worker", kind="success")
    ubij = mo.ui.run_button(label="kill -9", kind="danger")
    zacni_telefon = mo.ui.run_button(label="📱 Start phone page", kind="success")
    mo.hstack([zacni_delavca, ubij, zacni_telefon], justify="start", gap=1)
    return ubij, zacni_delavca, zacni_telefon


@app.cell(hide_code=True)
def _(dvojna, mo, process, set_delavec, zacni_delavca):
    mo.stop(not zacni_delavca.value)
    ukaz = "act3-dvojna" if dvojna.value else "act3"
    set_delavec(process.start("act3", process.uv_run(ukaz)))
    mo.md(f"started `uv run {ukaz}`")
    return


@app.cell(hide_code=True)
def _(get_delavec, mo, ubij):
    mo.stop(not ubij.value)
    _d = get_delavec()
    if _d is None:
        mo.output.replace(mo.md("no worker to kill"))
    else:
        _umrl = _d.kill9()
        mo.output.replace(mo.md(f"`kill -9 {_d.pid}` · confirmed dead: {'yes' if _umrl else 'no'}"))
    return


@app.cell(hide_code=True)
def _(TELEFON, get_telefon, mo, process, set_telefon, zacni_telefon):
    mo.stop(not zacni_telefon.value)
    prejsnji = get_telefon()
    if prejsnji is not None and prejsnji.alive():
        mo.output.replace(mo.md(f"phone page already running · pid {prejsnji.pid}"))
    else:
        set_telefon(process.start(TELEFON, process.uv_run("zig")))
        mo.output.replace(mo.md("phone page starting …"))
    return


@app.cell(hide_code=True)
def _(cakanje, get_telefon, mo, zig_api):
    telefon = get_telefon()
    if telefon is None or not telefon.alive():
        mo.output.replace(mo.md("_phone page not running — press **Start phone page**._"))
    else:
        url = f"http://{zig_api.lan_ip()}:8000"
        mo.output.replace(
            mo.hstack(
                [
                    mo.image(src=cakanje.qr_png(url), width=170),
                    mo.md(f"### {url}\nSame hotspot as the laptop. The page refreshes itself every 3 s."),
                ],
                align="center",
                gap=2,
            )
        )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Waiting for the stamp
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    refresh = mo.ui.refresh(default_interval="1s")
    return (refresh,)


@app.cell(hide_code=True)
def _(client, get_delavec, mo, refresh, zig_api):
    try:
        zahteve = zig_api.cakajoce(client)
        napaka = None
    except Exception as e:  # the emulator can be briefly down (not started yet, mid-restart, ...)
        zahteve, napaka = [], f"{type(e).__name__}: emulator not reachable (`make emulator`?)"
    _d = get_delavec()
    aktivno = (_d is not None and _d.alive()) or bool(zahteve)
    if napaka:
        mo.output.replace(mo.md(f"_{napaka}_"))
    elif aktivno:
        mo.output.replace(mo.hstack([mo.md("_live_"), refresh], justify="start", gap=1))
    else:
        mo.output.replace(mo.md("_nothing waiting — press **Start worker**._"))
    return (zahteve,)


@app.cell(hide_code=True)
def _(get_delavec, mo, refresh, terminal):
    _ = refresh
    _d = get_delavec()
    if _d is None:
        mo.output.replace(mo.md("_worker log — not started yet._"))
    else:
        mo.output.replace(mo.Html(terminal.ansi_to_html(_d.tail(300))))
    return


@app.cell(hide_code=True)
def _(WORKFLOW, client, dag, mo, raw, scheduler, vloga_v_pregledu, zahteve):
    _ = zahteve  # ticks in step with the waiting-request poll above: the only way to see a phone tap land
    try:
        stanja = scheduler.stanja_dag(client, raw, vloga_v_pregledu)
    except Exception:
        stanja = {}
    mo.mermaid(dag.mermaid(WORKFLOW, stanja))
    return


@app.cell(hide_code=True)
def _(cakanje, mo, zahteve):
    if not zahteve:
        mo.output.replace(mo.md("_nič ne čaka na žig._"))
        izbira = None
    else:
        izbira = mo.ui.table(cakanje.tabela(zahteve), selection="single", pagination=False, label="waiting for the stamp")
        mo.output.replace(izbira)
    return (izbira,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Parked = `RUNNING` in the scheduler, no activity in flight, no process needed — kill the worker above and this table still shows the same request. The buttons answer the selected row, or the first one.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    odobri = mo.ui.run_button(label="✅ Approve", kind="success")
    zavrni_priloga = mo.ui.text(placeholder="missing attachment (optional)", label="reject — missing:")
    zavrni = mo.ui.run_button(label="❌ Reject", kind="danger")
    mo.hstack([odobri, zavrni_priloga, zavrni], justify="start", gap=1)
    return odobri, zavrni, zavrni_priloga


@app.cell(hide_code=True)
def _(cakanje, client, izbira, mo, odobri, zahteve, zig_api):
    mo.stop(not odobri.value)
    # The table is rebuilt on every refresh tick, which drops a selection: no selection = the first request.
    _rows = (izbira.value if izbira else None) or []
    if not zahteve:
        mo.output.replace(mo.md("_nothing is waiting for the stamp._"))
    else:
        _z = cakanje.najdi(zahteve, _rows[0]["request_id"]) if _rows else zahteve[0]
        if _z is None:
            mo.output.replace(mo.md("_that request was already answered — the table will refresh._"))
        else:
            zig_api.odgovori(client, _z, odobreno=True, odobril="notebook")
            mo.output.replace(mo.md(f"✅ approved {_z.instance_id} — waiting for the next tick to refresh."))
    return


@app.cell(hide_code=True)
def _(cakanje, client, izbira, mo, zahteve, zavrni, zavrni_priloga, zig_api):
    mo.stop(not zavrni.value)
    _rows = (izbira.value if izbira else None) or []
    if not zahteve:
        mo.output.replace(mo.md("_nothing is waiting for the stamp._"))
    else:
        _z = cakanje.najdi(zahteve, _rows[0]["request_id"]) if _rows else zahteve[0]
        if _z is None:
            mo.output.replace(mo.md("_that request was already answered — the table will refresh._"))
        else:
            _dopolnitev = [zavrni_priloga.value.strip()] if zavrni_priloga.value.strip() else []
            zig_api.odgovori(client, _z, odobreno=False, odobril="notebook", dopolnitev=_dopolnitev)
            mo.output.replace(mo.md(f"❌ rejected {_z.instance_id} — it loops back through `PreveriPriloge`."))
    return


if __name__ == "__main__":
    app.run()
