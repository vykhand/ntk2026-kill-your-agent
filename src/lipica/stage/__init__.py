"""Stage plumbing the marimo notebooks import: launching and killing the real worker processes,
turning their logs and the scheduler's own state into things a projector-sized cell can show.

Nothing here is workflow logic — that stays in `lipica.workflow` and the hosts. This package only
watches it from outside, the way the presenter does. Kept small and obvious: the audience may see
these modules imported in a cell.

    process    — start/kill9/tail a worker subprocess (`uv run act2`, ...)
    terminal   — ANSI worker log -> dark, monospace HTML
    dag        — the live DAG: MAF's own mermaid text, coloured by state
    scheduler  — what the Durable Task scheduler currently knows about the queue
    ledger     — out/takse.log + out/odlocbe/*.pdf as rows, duplicates flagged
    checks     — the status strip: emulator, model, worker, DevUI
"""
