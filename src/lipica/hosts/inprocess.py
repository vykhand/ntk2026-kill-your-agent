"""Act 1: the fragile baseline. `uv run act1`

Runs the morning queue in-process, one application after another. Nothing is persisted between
executors. kill -9 during PreveriPriloge and start again: the whole queue runs again from the top,
the first citizen gets a second odločba with a new number, and is charged twice.
"""

from __future__ import annotations

import asyncio
import os

from lipica.config import nastavitve
from lipica.console import console
from lipica.fixtures_io import JUTRANJA_VRSTA
from lipica.hosts.common import banner, izpisi_izide, pokazi_takse, spawn_auto_kill, spusti_delavca, zasedi_delavca
from lipica.workflow import build_workflow

IDEMPOTENT = False  # Act 1 is the fragile one on purpose (tests may flip it via LIPICA_ACT1_IDEMPOTENT=1)


async def run() -> None:
    n = nastavitve()
    idempotent = IDEMPOTENT or os.environ.get("LIPICA_ACT1_IDEMPOTENT") == "1"
    banner("Krhki agent (in-process)", "kill -9 med PreveriPriloge → po ponovnem zagonu vse od začetka", n, idempotent=idempotent)
    zasedi_delavca("act1")
    spawn_auto_kill(n)
    try:
        for vloga_id in JUTRANJA_VRSTA:
            console.rule(f"Vloga {vloga_id}")
            workflow = build_workflow(idempotent=idempotent)
            result = await workflow.run(vloga_id)
            izpisi_izide(result.get_outputs())
        pokazi_takse()
    finally:
        spusti_delavca("act1")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
