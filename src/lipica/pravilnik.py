"""Parse fixtures/pravilnik.md into procedures, plus a deterministic attachment checker
used by the `mock` LLM backend and by tests. The LLM path gets the raw section text instead."""

from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from lipica.domain import Postopek, Stranka, Vloga

ROOT = Path(__file__).resolve().parents[2]
PRAVILNIK = ROOT / "fixtures" / "pravilnik.md"

_SECTION = re.compile(r"^### (UE-\d{2}) (.+)$", re.MULTILINE)
_FIELD = re.compile(r"^- \*\*(.+?):\*\*\s*(.*?)(?=^- \*\*|\Z)", re.MULTILINE | re.DOTALL)
_LABEL = re.compile(r"^\([a-z]\)\s*")
_STOP = {"o", "v", "z", "s", "in", "ali", "na", "do", "iz", "za", "m", "k"}


def _fields(section: str) -> dict[str, str]:
    return {k.strip(): " ".join(v.replace("**", "").split()) for k, v in _FIELD.findall(section)}


def _priloge(text: str) -> list[str]:
    items = []
    for raw in text.split(";"):
        item = _LABEL.sub("", raw.strip().rstrip("."))
        if item:
            items.append(item)
    return items


def _taksa(text: str) -> float:
    m = re.search(r"(\d+),(\d{2})\s*€", text)
    return float(f"{m.group(1)}.{m.group(2)}") if m else 0.0


@lru_cache(maxsize=1)
def splosne_dolocbe() -> str:
    text = PRAVILNIK.read_text(encoding="utf-8")
    start, end = text.index("## 0."), text.index("## 1.")
    return text[start:end].strip()


@lru_cache(maxsize=1)
def postopki() -> dict[str, Postopek]:
    text = PRAVILNIK.read_text(encoding="utf-8")
    heads = list(_SECTION.finditer(text))
    result: dict[str, Postopek] = {}
    for i, h in enumerate(heads):
        stop = heads[i + 1].start() if i + 1 < len(heads) else text.index("## 2.")
        section = text[h.start():stop].strip()
        f = _fields(section)
        result[h.group(1)] = Postopek(
            sifra=h.group(1),
            naziv=h.group(2).strip(),
            priloge=_priloge(f.get("Priloge", "")),
            taksa_eur=_taksa(f.get("Taksa", "")),
            rok=f.get("Rok", ""),
            dvojna_odobritev="dvojna" in f.get("Odobritev", "").lower(),
            najpogosteje_manjka=f.get("Najpogosteje manjka", ""),
            besedilo=section,
        )
    return result


def postopek(sifra: str) -> Postopek:
    try:
        return postopki()[sifra]
    except KeyError as e:
        raise KeyError(f"Postopek {sifra} ni v pravilniku") from e


# ---- deterministic checker (mock backend) ------------------------------------------------------


def _tokens(s: str) -> set[str]:
    s = s.split("(")[0].split(" — ")[0].lower()
    return {t for t in re.findall(r"[\wčšžćđ]+", s) if t not in _STOP}


def _matches(required: str, submitted: str) -> bool:
    """Most of the required item's content words must appear in the submitted one."""
    a, b = _tokens(required), _tokens(submitted)
    return bool(a and b) and len(a & b) / len(a) >= 0.6


def _pogojna_priloga_obvezna(item: str, stranka: Stranka, na_dan: date) -> bool:
    """Rulebook conditionals. Only UE-01 (c) exists: photo iff previous document older than N years."""
    m = re.search(r"starejša od (\d+) let", item)
    if m and item.lower().startswith("fotografija"):
        return stranka.dokument.starost_let(na_dan) > int(m.group(1))
    return True


def zahtevane_priloge(vloga: Vloga, stranka: Stranka, na_dan: date) -> list[tuple[str, bool]]:
    """Every attachment the rulebook lists for this procedure, with the conditionals resolved for this
    citizen: (item, required). Shared by the deterministic checker and the LLM prompt, so the model never
    has to do date arithmetic."""
    p = postopek(vloga.postopek)
    return [
        (req, not ("obvezna le" in req and not _pogojna_priloga_obvezna(req, stranka, na_dan)))
        for req in p.priloge
    ]


def preveri_po_pravilniku(vloga: Vloga, stranka: Stranka, na_dan: date) -> tuple[bool, list[str], str]:
    """Return (popolna, manjkajoče, obrazložitev) purely from the rulebook."""
    p = postopek(vloga.postopek)
    manjka: list[str] = []
    for req, required in zahtevane_priloge(vloga, stranka, na_dan):
        if not required:
            continue
        if not any(_matches(req, s) for s in vloga.priloge):
            manjka.append(req.split(" — ")[0])
    if manjka:
        obr = f"Po pravilniku {p.sifra} manjka: " + "; ".join(manjka) + "."
    else:
        obr = f"Vse obvezne priloge po pravilniku {p.sifra} so priložene (preverjene zahteve: {len(p.priloge)})."
    return (not manjka, manjka, obr)
