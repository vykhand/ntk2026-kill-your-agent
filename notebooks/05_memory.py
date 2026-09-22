import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full", app_title="Teach it once")


@app.cell(hide_code=True)
def _():
    import inspect

    import marimo as mo

    from lipica import fixtures_io, llm, spomin
    from lipica.stage import checks, process, terminal, ucenje

    WORKER = "act4"
    EMA = "ID-TEST-005"  # the citizen the "Apply" / "Forget" buttons act on (VL-2026-0052)
    return (
        EMA,
        WORKER,
        checks,
        fixtures_io,
        inspect,
        llm,
        mo,
        process,
        spomin,
        terminal,
        ucenje,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Teach it once

    Coach the referent once. Foundry memory stores it. The next citizen, in a fresh session, gets it
    applied — the model judges whether the rule holds, the code decides what happens next.

    _Cloud: your Foundry project (`FOUNDRY_PROJECT_ENDPOINT` in `.env`). Every control below runs the real
    `uv run act4 ...` CLI as a subprocess — same commands as the terminal fallback._
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
    ## The memory, in the code's own source
    """)
    return


@app.cell(hide_code=True)
def _(inspect, mo, spomin):
    mo.md(
        "Every application run reads the office scope and writes nothing to it — the stock provider "
        "injects hits as a *user* message, which lost to the rulebook two runs out of three, so this one "
        "injects them as instructions with an explicit precedence statement instead:"
    )
    mo.ui.code_editor(
        value=inspect.getsource(spomin.ReadOnlyFoundryMemoryProvider),
        disabled=True,
        show_copy_button=False,
        min_height=320,
    )
    return


@app.cell(hide_code=True)
def _(inspect, mo, spomin):
    mo.md("The coaching run is the only writer, and it *awaits* the extraction instead of firing and forgetting:")
    mo.ui.code_editor(
        value=inspect.getsource(spomin.AwaitedFoundryMemoryProvider.after_run),
        disabled=True,
        show_copy_button=False,
        min_height=260,
    )
    return


@app.cell(hide_code=True)
def _(mo, spomin):
    mo.md(f"One sentence, given to the referent once (`SPOMIN_NAVODILO={spomin.NAVODILO_VARIANTA}`):")
    mo.md(f"> {spomin.NAVODILO}")
    return


@app.cell(hide_code=True)
def _(inspect, llm, mo):
    mo.md(
        "The model evaluates every learned procedure it was handed; the code, not the model, enforces the "
        "consequence of whichever one holds:"
    )
    mo.ui.code_editor(value=inspect.getsource(llm.uveljavi_postopke), disabled=True, show_copy_button=False, min_height=260)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run it
    """)
    return


@app.cell(hide_code=True)
def _(WORKER, mo, process):
    get_tek, set_tek = mo.state(process.reattach(WORKER))
    return get_tek, set_tek


@app.cell(hide_code=True)
def _(EMA, fixtures_io, mo, spomin):
    _oznake = {
        "referent (office rules)": spomin.SCOPE_REFERENT,
        f"ID-TEST-004 ({fixtures_io.stranka('ID-TEST-004').ime})": "ID-TEST-004",
        f"{EMA} ({fixtures_io.stranka(EMA).ime})": EMA,
        f"ID-TEST-006 ({fixtures_io.stranka('ID-TEST-006').ime})": "ID-TEST-006",
    }
    obseg = mo.ui.dropdown(options=_oznake, value="referent (office rules)", label="scope to list")
    obseg
    return (obseg,)


@app.cell(hide_code=True)
def _(mo):
    mo.callout(
        mo.md(
            "**Verification is read-only.** `store` and `list` are safe to click any time. "
            "`Coach` / `Apply` / `Delete` / `Forget` / `Restore` / `Clean` are wired below — wired, not "
            "rehearsed here — because every one of them writes to the shared cloud memory store."
        ),
        kind="warn",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    store_btn = mo.ui.run_button(label="Store (read-only)")
    list_btn = mo.ui.run_button(label="List memories")
    coach_btn = mo.ui.run_button(label="Coach", kind="warn")
    apply_ema_btn = mo.ui.run_button(label="Apply → Ema", kind="warn")
    revert_filip_btn = mo.ui.run_button(label="Apply → Filip (after delete)", kind="warn")
    delete_btn = mo.ui.run_button(label="Delete selected id", kind="danger")
    forget_ema_btn = mo.ui.run_button(label="Forget Ema (GDPR)", kind="danger")
    restore_btn = mo.ui.run_button(label="Restore post-coaching", kind="danger")
    clean_btn = mo.ui.run_button(label="Clean (rehearsal reset)", kind="danger")
    mo.vstack(
        [
            mo.hstack([store_btn, list_btn], justify="start", gap=1),
            mo.hstack([coach_btn, apply_ema_btn, revert_filip_btn], justify="start", gap=1),
            mo.hstack([delete_btn, forget_ema_btn], justify="start", gap=1),
            mo.hstack([restore_btn, clean_btn], justify="start", gap=1),
        ]
    )
    return (
        apply_ema_btn,
        clean_btn,
        coach_btn,
        delete_btn,
        forget_ema_btn,
        list_btn,
        restore_btn,
        revert_filip_btn,
        store_btn,
    )


@app.cell(hide_code=True)
def _(mo, process, set_tek, store_btn):
    mo.stop(not store_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "store")))
    mo.md("`uv run act4 store` started")
    return


@app.cell(hide_code=True)
def _(list_btn, mo, obseg, process, set_tek):
    mo.stop(not list_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "list", obseg.value)))
    mo.md(f"`uv run act4 list {obseg.value}` started")
    return


@app.cell(hide_code=True)
def _(coach_btn, mo, process, set_tek):
    mo.stop(not coach_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "coach")))
    mo.md("`uv run act4 coach` started")
    return


@app.cell(hide_code=True)
def _(apply_ema_btn, mo, process, set_tek):
    mo.stop(not apply_ema_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "apply")))
    mo.md("`uv run act4 apply` started (VL-2026-0052 · Ema)")
    return


@app.cell(hide_code=True)
def _(mo, process, revert_filip_btn, set_tek):
    mo.stop(not revert_filip_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "revert")))
    mo.md("`uv run act4 revert` started (VL-2026-0053 · Filip)")
    return


@app.cell(hide_code=True)
def _(EMA, forget_ema_btn, mo, process, set_tek):
    mo.stop(not forget_ema_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "forget", EMA)))
    mo.md(f"`uv run act4 forget {EMA}` started")
    return


@app.cell(hide_code=True)
def _(mo, process, restore_btn, set_tek):
    mo.stop(not restore_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "restore", "post-coaching")))
    mo.md("`uv run act4 restore post-coaching` started")
    return


@app.cell(hide_code=True)
def _(clean_btn, mo, process, set_tek):
    mo.stop(not clean_btn.value)
    set_tek(process.start("act4", process.uv_run("act4", "clean")))
    mo.md("`uv run act4 clean` started")
    return


@app.cell(hide_code=True)
def _(mo):
    refresh = mo.ui.refresh(default_interval="1s")
    return (refresh,)


@app.cell(hide_code=True)
def _(get_tek, mo, refresh, terminal):
    _tek = get_tek()
    if _tek is None:
        mo.output.replace(mo.md("_no command run yet — press **Store** or **List memories** to start._"))
    elif _tek.alive():
        mo.output.replace(mo.vstack([refresh, mo.Html(terminal.ansi_to_html(_tek.tail(400)))]))
    else:
        mo.output.replace(mo.Html(terminal.ansi_to_html(_tek.tail(400))))
    return


@app.cell(hide_code=True)
def _(get_tek, mo, refresh, ucenje):
    _ = refresh  # keep in step with the terminal panel while a command is still streaming
    _tek = get_tek()
    if _tek is None:
        izbira_izbrisa = None
        mo.output.replace(mo.md("_run **List memories** to populate the delete dropdown._"))
    else:
        parovi = ucenje.memory_ids(_tek.tail(4000))
        if not parovi:
            izbira_izbrisa = None
            mo.output.replace(mo.md("_no memory ids in the latest output — run **List memories** first._"))
        else:
            izbira_izbrisa = mo.ui.dropdown(
                options=[f"{mid} · {kind}" for mid, kind in parovi], label="delete which id?"
            )
            mo.output.replace(izbira_izbrisa)
    return (izbira_izbrisa,)


@app.cell(hide_code=True)
def _(delete_btn, izbira_izbrisa, mo, process, set_tek):
    mo.stop(not delete_btn.value)
    if not izbira_izbrisa or not izbira_izbrisa.value:
        mo.output.replace(mo.md("_pick an id from the dropdown above first._"))
    else:
        _memory_id = izbira_izbrisa.value.split(" · ")[0]
        set_tek(process.start("act4", process.uv_run("act4", "delete", _memory_id)))
        mo.output.replace(mo.md(f"`uv run act4 delete {_memory_id}` started"))
    return


if __name__ == "__main__":
    app.run()
