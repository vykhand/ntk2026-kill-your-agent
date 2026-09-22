"""Loaders for the synthetic fixtures."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache

from lipica.domain import Stranka, Vloga
from lipica.pravilnik import ROOT

FIXTURES = ROOT / "fixtures"

# The morning queue processed by Acts 1 and 2, in order. The kill lands during the second one.
JUTRANJA_VRSTA = ["VL-2026-0047", "VL-2026-0050"]
# Act 3: the dog registration with the missing čip (reject on the phone, the citizen brings it, approve).
AKT3_VRSTA = ["VL-2026-0048"]
# Act 3 stretch: the beehive permit needs the referent AND the vodja oddelka (rulebook: dvojna odobritev).
AKT3_DVOJNA_VRSTA = ["VL-2026-0049"]


@lru_cache(maxsize=1)
def stranke() -> dict[str, Stranka]:
    data = json.loads((FIXTURES / "stranke.json").read_text(encoding="utf-8"))
    return {s["id"]: Stranka.model_validate(s) for s in data["stranke"]}


@lru_cache(maxsize=1)
def _vloge_raw() -> dict:
    return json.loads((FIXTURES / "vloge.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def vloge() -> dict[str, Vloga]:
    return {v["id"]: Vloga.model_validate(v) for v in _vloge_raw()["vloge"]}


def datum_obravnave() -> date:
    """Fixed processing date so document-age rules behave identically in every rehearsal."""
    return date.fromisoformat(_vloge_raw()["_datum_obravnave"])


def vloga(vloga_id: str) -> Vloga:
    try:
        return vloge()[vloga_id]
    except KeyError as e:
        raise KeyError(f"Vloga {vloga_id} ni med fixtures") from e


def stranka(stranka_id: str) -> Stranka:
    return stranke()[stranka_id]
