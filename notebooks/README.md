# The six notebooks

Interactive marimo notebooks: the demo for the talk. Each one is a
control panel — the worker it drives always runs as a real subprocess (`uv run act2`, ...), never
in-process, so `kill -9` kills the worker and never the notebook kernel.

Launch the whole directory and pick a notebook from marimo's own file list:

```bash
make notebooks     # uv run marimo edit notebooks --port 2718
```

Nothing runs until a button is pressed — opening a notebook only renders markdown, code and the
static DAG.

## Notebooks

| File | Beat | Purpose |
|---|---|---|
| `01_build.py` | Build it | MAF building blocks (`Executor`, edges, context); the interactive DAG; run one application in the kernel; open DevUI |
| `02_crash.py` | Kill it | In-process host, `kill -9` mid-`PreveriPriloge`, the double charge |
| `03_durable.py` | Bring it back | Durable Task extension + DTS emulator: history, replay, exactly-once ledger |
| `04_human.py` | Wait for a human | `request_info`, the phone page, parked at zero cost, the two-signature fan-in |
| `05_memory.py` | Teach it once | Foundry memory: coach, apply, list, delete, forget (cloud) |
| `06_azure.py` | Same code, scheduler in Azure | Same controls as `03`, against the Azure Durable Task Scheduler |

## Notes

- `pyproject.toml` sets `[tool.marimo.runtime] auto_instantiate = true`: opening a notebook runs its cells
  (only markdown, source and tables — every side effect is behind a button). With a user-level marimo
  default of `false`, notebooks would open showing stale cached output with nothing executed.
- Delete `notebooks/__marimo__/` if a notebook ever shows stale output after a server restart.
- `05_memory` and `06_azure` need `az login`. For `06_azure`, log in to the tenant that holds the scheduler:
  `az login --tenant <DTS_TENANT>` (`act5/README.md`).
- In `04_human`, ✅ Approve / ❌ Reject answer the selected row, or the first waiting request (the table is
  rebuilt every second, which drops a selection).

## Shared plumbing

All six import `lipica.stage` (`src/lipica/stage/`): `process` (start/kill9/tail a worker),
`terminal` (ANSI log -> HTML), `dag` (MAF's own mermaid, coloured by state), `scheduler` (the Durable
Task queue table), `ledger` (`out/takse.log` + `out/odlocbe/*.pdf`), `checks` (the status strip). See
that package's docstrings before adding another way to do any of this.

## Companion

```bash
make devui   # agent-framework-devui on http://127.0.0.1:8090 — MAF's other generated graph view
```

Ports: DTS gRPC 8080, DTS dashboard 8082, phone page 8000, marimo 2718, DevUI 8090.
