# kill -9 Your Agent

Demo code for the talk **"kill -9 Your Agent: durable AI workflows with Microsoft Agent Framework"**,
NT konferenca 2026, Portorož (Andy V. · AI BISTRO).

An agent works the counter at the fictional **Upravna enota Zgornja Lipica**, a Slovenian administrative
office. It checks applications with an LLM, waits for a human to stamp them, and issues a decision that
costs the citizen a fee. We build it, `kill -9` it halfway through, and bring it back. Without a
durable runtime, the restart charges the citizen twice. With one, the workflow picks up where it
stopped. The demo is in Slovene on purpose: the executor names show up in the Durable Task dashboard as
they are.

```
SprejmiVlogo  →  PreveriPriloge (LLM)  →  ČakanjeNaŽig (pause)  →  IzdajOdločbo (side effect)
```

There is one workflow definition, in `src/lipica/workflow.py`, and two hosts in `src/lipica/hosts/`. The
in-process host runs it as it is. The durable host hands the very same object to the Durable Task
extension of Microsoft Agent Framework.

## Setup (about 5 minutes)

You need [uv](https://docs.astral.sh/uv/) (it fetches Python 3.12) and Docker. For a real local model
you also need [Ollama](https://ollama.com).

```bash
uv sync                               # exact pins from uv.lock
cp .env.example .env                  # LLM_BACKEND=ollama|azure|mock, see the file
docker compose up -d                  # DTS emulator: gRPC 8080, dashboard http://localhost:8082
ollama pull gpt-oss:20b               # offline model (13 GB), once; qwen2.5:7b (4.7 GB) is the light option
make test
make warm                             # loads the model and checks it on the demo applications
```

The first four beats work offline, with the emulator in Docker and the model in Ollama.
`LLM_BACKEND=mock` needs no model at all: it runs a deterministic rulebook check. `LLM_BACKEND=azure` uses
an Azure OpenAI / Foundry deployment and needs an `az login` (see `.env.example`).

## The demo: six marimo notebooks

The talk runs from six [marimo](https://marimo.io) notebooks in `notebooks/`, one per beat. Each one:

- shows the real Agent Framework source;
- draws the workflow graph with MAF's own `WorkflowViz`, coloured live from the scheduler's history;
- drives the worker as a separate process, so `kill -9` kills the worker and never the notebook.

| Beat | Notebook | What it shows |
|---|---|---|
| Build it | `01_build` | MAF building blocks, the interactive graph, one run in the kernel, DevUI (`make devui`, :8090) |
| Kill it | `02_crash` | in-process worker, `kill -9` mid-step, the double charge in the fee ledger |
| Bring it back | `03_durable` | Durable Task worker + emulator, live scheduler table and graph, dashboard :8082 |
| Wait for a human | `04_human` | parked on `request_info`, phone page :8000 (QR), reject loop, two signatures |
| Teach it once | `05_memory` | Foundry memory: coach, apply, list, delete, forget (cloud, optional) |
| Same code, scheduler in Azure | `06_azure` | the `03` controls against an Azure Durable Task Scheduler (cloud, optional) |

```bash
make emulator && make warm      # emulator up, model loaded
make notebooks                  # marimo on :2718, pick a notebook from the directory view
```

`notebooks/README.md` has more on the notebooks and the shared plumbing in `src/lipica/stage/`.

## The same demo from a terminal

Every notebook button runs one of these commands, so you can run the whole story without the notebooks.
Use two panes: one runs the workflow, the other does the killing.

| Beat | Command | What you see |
|---|---|---|
| Kill it | `make act1`, then `make kill` during the second `PreveriPriloge`, then `make act1` again | the in-process run starts over: a new ticket number, a second decision, and a second fee for the first citizen (`make ledger`) |
| Bring it back | `make reset`, then `make act2`, then the same kill, then `make act2` again | the run resumes from the checkpoint: the same ticket number, exactly one decision and one fee each |
| Wait for a human | `make act3` + `make zig` | `ČakanjeNaŽig` parks the workflow at zero compute until the phone answers; ❌ loops back for the missing attachment, ✅ stamps the decision |
| Two signatures | `make act3-dvojna` | fan-out / fan-in: two approvals in parallel, then the stamp |
| Teach it once | `make act4-coach`, `make act4-apply`, … | see [Foundry memory](#optional-foundry-memory) |
| Scheduler in Azure | `make act5` | `act2` against a Durable Task Scheduler in Azure; see `act5/README.md` |

The first run processes two applications from `fixtures/vloge.json`: `VL-2026-0047` (renewing an ID card)
and `VL-2026-0050` (a permit to burn garden waste). The kill window is the countdown inside
`PreveriPriloge` (`MALICA_SECONDS`, default 6 s). To kill at the exact moment every time:

```bash
make act2 KILL_AT=PreveriPriloge:VL-2026-0050
```

**Without a phone:** `make odobri` approves the first application that waits for the stamp, and
`make zavrni` rejects it. `uv run python scripts/zig.py` lists what is waiting.

**Dashboard:** open http://localhost:8082 and choose task hub `default`, then the instance
`VL-2026-0050`. The history shows `dafx-vloga-PreveriPriloge` scheduled before the kill and completed
after the restart. Click any activity to see its input and output as plain JSON.

**Recovery:** running `make act2` again is always safe:

- a `RUNNING` instance is resumed;
- a `FAILED` one is purged and restarted, with the reason printed;
- a `COMPLETED` one is left alone.

If a model call fails or takes longer than `LLM_TIMEOUT`, `PreveriPriloge` prints a red warning and falls
back to the rulebook, so the run still finishes. `make kill` makes `make` report "Error 137". That is the
SIGKILL exit code, and it is expected. `make reset` wipes the ticket counter, the decisions, the fee
ledger and the emulator's instances.

## Optional: Foundry memory

`05_memory` and the `act4` commands use the memory of Azure AI Foundry Agent Service (preview). This is
the only part that needs an existing Foundry project, with:

- a chat deployment (`gpt-5.4-mini` in the talk);
- an embedding deployment (`text-embedding-3-large`);
- your `az login` identity holding the Foundry User role.

Fill in the Foundry block in `.env` (see `.env.example`), then:

```bash
uv run act4 store                 # does the memory store exist? (read-only)
uv run act4 store-create --yes    # once: creates the store in your project
make act4-coach                   # process VL-2026-0051, then coach the referent once
make act4-apply                   # VL-2026-0052: a different citizen, a fresh session, the rule applied unprompted
make act4-list                    # the stored items, verbatim
make act4-delete ID=<memory_id>   # delete one item live
make act4-revert                  # VL-2026-0053: the rule is gone
make act4-forget SCOPE=ID-TEST-005    # delete what the service remembered about one citizen
make act4-clean                   # empty every demo scope (the store stays)
```

Coaching is the only run that writes the office's rules. Application runs read them and never write
them back. `make act4-restore NAME=post-coaching` starts you in the coached state
(`fixtures/spomin/post-coaching.json`).

## Settings

What defines a beat is fixed in its host, not in `.env`. `act1` builds the workflow with
`IzdajOdlocbo(idempotent=False)`, which draws a random decision number. `act2` builds it with
`idempotent=True`, where the number is a hash of the application id. The rest lives in `.env` and
`src/lipica/config.py`:

| Variable | Default | Meaning |
|---|---|---|
| `LLM_BACKEND` | `mock` | `mock` / `ollama` / `azure` for `PreveriPriloge` |
| `OLLAMA_MODEL` | `gpt-oss:20b` | the pulled tag (`qwen2.5:7b` for speed) |
| `MALICA_SECONDS` | `6` | the countdown before the model call: the kill window |
| `LLM_TIMEOUT` / `LLM_FALLBACK` | `90` / `1` | the model call deadline; on failure, fall back to the rulebook with a red warning |
| `ZIG_PORT` | `8000` | the phone page's port (`make zig`) |
| `KILL_AT` | – | `Executor[:VlogaId]` arms `scripts/kill_during.py`; shell only, never `.env` |

## Layout

```
src/lipica/workflow.py     the four executors and the builder (ONE definition)
src/lipica/hosts/          inprocess.py, durable.py, act4.py (memory), telefon.py + zig_api.py (the phone page)
src/lipica/stage/          what the notebooks share: worker processes, live graph, scheduler table, ledger
src/lipica/llm.py          LLM backend switch + the attachment-check prompt
src/lipica/spomin.py       Foundry memory: the store, the read-only and the coaching providers
src/lipica/odlocba.py      the decision PDF with the stamp, the fee ledger, the idempotency switch
src/lipica/pravilnik.py    rulebook parser + deterministic checker (mock backend, tests)
notebooks/                 the six marimo notebooks
act5/                      azd template: a Durable Task Scheduler and one task hub
fixtures/                  pravilnik.md, stranke.json, vloge.json, obrazci/*.pdf (all fictional)
scripts/                   kill_during.py, reset.py, zig.py, devui.py, smoke_llm.py, gen_obrazci.py
```

## Pinned versions (September 2026)

| Package | Version | Status |
|---|---|---|
| agent-framework-core | 1.17.0 | GA |
| agent-framework-openai | 1.14.2 | GA |
| agent-framework-durabletask | 1.0.0b260730 | beta / public preview |
| agent-framework-ollama | 1.0.0b260813 | beta |
| agent-framework-foundry | 1.12.0 | memory is preview |
| agent-framework-devui | 1.0.0b260910 | beta |
| durabletask, durabletask-azuremanaged | 1.10.1 | GA |
| DTS emulator image | `latest` @ `sha256:3613230…` (pinned in `docker-compose.yml`) | in-memory only |

Everything on screen is fictional: the municipality, the procedures, the people, and the id formats.

## Useful links

Every link from the talk's slides and speaker notes.

**Microsoft Agent Framework**
- [Overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [GitHub](https://github.com/microsoft/agent-framework)
- [agent-framework-core on PyPI](https://pypi.org/project/agent-framework-core/)
- [Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/)
- [Executors](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/executors)
- [Edges](https://learn.microsoft.com/en-us/agent-framework/concepts/workflows/edges)
- [Checkpoints and resuming](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [Human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) (`ctx.request_info`, `@response_handler`)

**Seeing the graph: WorkflowViz and DevUI**
- [WorkflowViz](https://learn.microsoft.com/en-us/agent-framework/workflows/visualization): the graph generator (`to_mermaid` / `to_digraph` / `export`)
- [WorkflowViz API reference](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.workflowviz?view=agent-framework-python-latest)
- [WorkflowViz source](https://github.com/microsoft/agent-framework/blob/main/python/packages/core/agent_framework/_workflows/_viz.py)
- [WorkflowViz sample](https://github.com/microsoft/agent-framework/blob/main/python/samples/03-workflows/visualization/concurrent_with_visualization.py)
- [DevUI](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/ui/devui/)
- [DevUI README](https://github.com/microsoft/agent-framework/blob/main/python/packages/devui/README.md) (`serve(entities=[...])`)
- [DevUI samples](https://github.com/microsoft/agent-framework/tree/main/python/samples/02-agents/devui)
- [agent-framework-devui on PyPI](https://pypi.org/project/agent-framework-devui/)

**Durability: the Durable extension and the Durable Task Scheduler**
- [Durable extension](https://learn.microsoft.com/en-us/agent-framework/integrations/durable-extension)
- [Durable extension on GitHub](https://github.com/microsoft/agent-framework-durable-extension/tree/main/python) (Python)
- [agent-framework-durabletask on PyPI](https://pypi.org/project/agent-framework-durabletask/)
- [Durable Task docs](https://learn.microsoft.com/en-us/azure/durable-task/)
- [Durable Task Scheduler](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler)
- [Emulator, dashboard, creating a scheduler and task hub](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/develop-with-durable-task-scheduler)
- [Scheduler billing](https://learn.microsoft.com/en-us/azure/durable-task/scheduler/durable-task-scheduler-billing) (Consumption vs Dedicated)
- [Durable Task SDK for Python](https://github.com/microsoft/durabletask-python)
- [Orchestrator code constraints](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-code-constraints) (determinism, replay)

**Memory**
- [Foundry Agent Service memory](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/what-is-memory) (preview)
- [Create and use memory](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/memory-usage)

**The notebooks and the local model**
- [marimo docs](https://docs.marimo.io/)
- [`mo.ui.run_button`](https://docs.marimo.io/api/inputs/run_button/): every side effect in the notebooks sits behind one
- [`mo.ui.refresh`](https://docs.marimo.io/api/inputs/refresh/): drives the live tables and graph
- [`mo.mermaid`](https://docs.marimo.io/examples/markdown/mermaid/): draws the WorkflowViz output
- [gpt-oss on Ollama](https://ollama.com/library/gpt-oss): the local model

**Other durable workflow engines**
- [Temporal](https://docs.temporal.io/)
- [Dapr Workflow](https://docs.dapr.io/developing-applications/building-blocks/workflow/workflow-overview/)

## License

MIT, see [LICENSE](LICENSE).
