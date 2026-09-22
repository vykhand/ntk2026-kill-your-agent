"""Domain models. These are also the messages that flow between executors,
so they are plain Pydantic models: JSON-serialisable, and readable in the DTS dashboard."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class Dokument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    vrsta: str
    stevilka: str = Field(alias="številka")
    datum_izdaje: date

    def starost_let(self, na_dan: date) -> int:
        years = na_dan.year - self.datum_izdaje.year
        if (na_dan.month, na_dan.day) < (self.datum_izdaje.month, self.datum_izdaje.day):
            years -= 1
        return years


class Stranka(BaseModel):
    id: str
    ime: str
    naslov: str
    dokument: Dokument
    opomba: str = ""


class Vloga(BaseModel):
    id: str
    stranka_id: str
    postopek: str
    naziv: str
    priloge: list[str]
    opomba_stranke: str = ""
    akt: str = ""


class Postopek(BaseModel):
    sifra: str
    naziv: str
    priloge: list[str]
    taksa_eur: float
    rok: str
    dvojna_odobritev: bool
    najpogosteje_manjka: str
    besedilo: str  # the raw rulebook section, handed to the LLM verbatim


# ---- messages between executors --------------------------------------------------------------
# Each message carries its predecessor so no executor depends on shared state; the dashboard then
# shows the full context as every activity's input.


class SprejetaVloga(BaseModel):
    """SprejmiVlogo -> PreveriPriloge (and ČakanjeNaŽig -> PreveriPriloge again after a rejection)"""

    vloga: Vloga
    stranka: Stranka
    listek_stevilka: int
    na_vrsti: int
    datum_obravnave: date
    dopolnitev: list[str] = []  # attachments the citizen brought after a rejection (Act 3 loop)


class PreverjanjePrilog(BaseModel):
    """PreveriPriloge -> ČakanjeNaŽig"""

    vloga_id: str
    popolna: bool
    manjkajoce: list[str]
    obrazlozitev: str
    vir: str  # "pravilnik" (deterministic) or "llm:<model>"
    sprejeta: SprejetaVloga
    postopki_urada: list[str] = []  # Act 4: the model's evaluation of each learned procedure


class Zig(BaseModel):
    """ČakanjeNaŽig -> IzdajOdločbo"""

    vloga_id: str
    odobreno: bool
    odobril: str
    opomba: str = ""
    preverjanje: PreverjanjePrilog


class Odlocba(BaseModel):
    """IzdajOdločbo -> workflow output"""

    stevilka: str
    vloga_id: str
    stranka_ime: str
    postopek: str
    naziv: str
    taksa_eur: float
    zig: bool
    pdf_path: str
    izdana: str
    ze_izdana: bool = False  # True when an idempotent re-issue was skipped
