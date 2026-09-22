"""DevUI: MAF's second generated view of the workflow graph — it lights up per executor during a run.

    uv run python scripts/devui.py      ->  http://127.0.0.1:8090

Registers the same Workflow object the notebooks build (idempotent odločbe, auto-stamped: this is a
graph to watch, not a rehearsal of the kill). Bound to localhost only; no auth on a laptop-only
demo server. Notebook 01's "Open in DevUI" button starts this as a subprocess via `stage.process`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_framework_devui import serve  # noqa: E402

from lipica.workflow import build_workflow  # noqa: E402

PORT = 8090


def main() -> None:
    workflow = build_workflow(idempotent=True, hitl=False)
    serve(entities=[workflow], host="127.0.0.1", port=PORT, auth_enabled=False, auto_open=False)


if __name__ == "__main__":
    main()
