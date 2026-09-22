"""The result panel: `out/takse.log` + `out/odlocbe/*.pdf`, read back as rows.

A duplicate charge (the whole point of Act 1 / notebook 02) is not hidden or summarised away here —
every row past an application's first is flagged `podvojeno=True`, in ledger order.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from lipica import runstate


@dataclasses.dataclass(frozen=True)
class Vrstica:
    """One issued odločba, straight from a `takse.log` line (see `lipica.odlocba.izdaj_odlocbo`)."""

    cas: str
    vloga_id: str
    stranka: str
    stevilka: str
    taksa: str
    podvojeno: bool = False  # True on every row past an application's first


def _parsiraj(line: str) -> Vrstica | None:
    deli = [d.strip() for d in line.split("|")]
    if len(deli) != 5:
        return None
    cas, vloga_id, stranka, stevilka, taksa = deli
    return Vrstica(cas=cas, vloga_id=vloga_id, stranka=stranka, stevilka=stevilka, taksa=taksa)


def vrstice(out_dir: Path | None = None) -> list[Vrstica]:
    """Every issued odločba, oldest first, with duplicates (same `vloga_id` twice) flagged."""
    log = (out_dir or runstate.OUT_DIR) / "takse.log"
    if not log.exists():
        return []
    zapisi = [v for line in log.read_text(encoding="utf-8").splitlines() if (v := _parsiraj(line))]
    videno: set[str] = set()
    out: list[Vrstica] = []
    for v in zapisi:
        if v.vloga_id in videno:
            v = dataclasses.replace(v, podvojeno=True)
        videno.add(v.vloga_id)
        out.append(v)
    return out


def pdfji(out_dir: Path | None = None) -> list[Path]:
    """Every issued odločba PDF, oldest first."""
    d = (out_dir or runstate.OUT_DIR) / "odlocbe"
    if not d.exists():
        return []
    return sorted(d.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
