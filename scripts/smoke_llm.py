"""Warm-up and sanity check for the LLM backend: run PreveriPriloge's model call on a few fixtures, no workflow.

    uv run python scripts/smoke_llm.py                      # backend from .env / LLM_BACKEND
    LLM_BACKEND=ollama OLLAMA_MODEL=qwen2.5:7b uv run python scripts/smoke_llm.py VL-2026-0047 VL-2026-0048

Prints the model's Slovene verdict next to the rulebook's deterministic one, and the latency. Use it in the
pre-stage checklist (warm the model, eyeball the Slovene) and when choosing a model.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lipica import fixtures_io, pravilnik  # noqa: E402
from lipica.config import nastavitve  # noqa: E402
from lipica.domain import SprejetaVloga  # noqa: E402
from lipica.llm import model_label, preveri_priloge  # noqa: E402

DEFAULT = ["VL-2026-0047", "VL-2026-0050", "VL-2026-0048", "VL-2026-0054"]


async def main(ids: list[str]) -> int:
    backend = nastavitve().llm_backend
    print(f"backend: {backend} ({model_label(backend)})")
    failures = 0
    for vid in ids:
        v = fixtures_io.vloga(vid)
        s = fixtures_io.stranka(v.stranka_id)
        sprejeta = SprejetaVloga(vloga=v, stranka=s, listek_stevilka=0, na_vrsti=0, datum_obravnave=fixtures_io.datum_obravnave())
        ok, manjka, _ = pravilnik.preveri_po_pravilniku(v, s, sprejeta.datum_obravnave)
        t0 = time.perf_counter()
        r = await preveri_priloge(sprejeta, backend)
        dt = time.perf_counter() - t0
        agree = r.popolna == ok
        failures += 0 if agree else 1
        print(f"\n{vid}  {v.postopek}  {dt:5.1f} s  {'OK' if agree else 'DISAGREES WITH RULEBOOK'}  [{r.vir}]")
        if r.vir.startswith("pravilnik"):
            failures += 1  # the model did not answer; the rulebook fallback did
        print(f"  pravilnik: popolna={ok} manjka={manjka}")
        print(f"  model:     popolna={r.popolna} manjka={r.manjkajoce}")
        print(f"  obrazložitev: {r.obrazlozitev}")
    return failures


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:] or DEFAULT)))
