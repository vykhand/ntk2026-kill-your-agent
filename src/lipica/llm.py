"""The one LLM step of the workflow (PreveriPriloge) and the backend switch behind it.

LLM_BACKEND=mock    deterministic rulebook check, no model (tests, panic mode)
LLM_BACKEND=ollama  local model through Ollama; offline once the model is pulled
LLM_BACKEND=azure   Azure OpenAI deployment (the cloud primary)

Clients are constructed per call on purpose: under the Durable Task extension every activity runs in a
fresh event loop on a worker thread, so a module-global async client would be bound to a dead loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import re

from agent_framework import Message
from pydantic import BaseModel, ValidationError

from lipica import pravilnik
from lipica.console import opozorilo
from lipica.domain import PreverjanjePrilog, SprejetaVloga


class OdgovorReferenta(BaseModel):
    """What the model must return. Slovene field values, ASCII field names."""

    popolna: bool
    manjkajoce: list[str]
    obrazlozitev: str


def make_chat_client(backend: str):
    if backend == "ollama":
        from agent_framework.ollama import OllamaChatClient

        return OllamaChatClient(model=os.environ.get("OLLAMA_MODEL", "gpt-oss:20b"))
    if backend == "azure":
        from agent_framework.openai import OpenAIChatCompletionClient

        api_key = os.environ.get("AZURE_OPENAI_API_KEY") or None
        credential = None
        if not api_key:
            from azure.identity import AzureCliCredential

            credential = AzureCliCredential()
        return OpenAIChatCompletionClient(
            model=os.environ["AZURE_OPENAI_CHAT_COMPLETION_MODEL"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=api_key,
            credential=credential,
        )
    raise ValueError(f"Neznan LLM_BACKEND={backend!r} (mock | ollama | azure)")


def model_label(backend: str) -> str:
    if backend == "ollama":
        return "ollama:" + os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
    if backend == "azure":
        return "azure:" + os.environ.get("AZURE_OPENAI_CHAT_COMPLETION_MODEL", "?")
    return "pravilnik"


NAVODILA = """Si referent na Upravni enoti Zgornja Lipica. Preveri, ali je vloga popolna.
Upoštevaj IZKLJUČNO spodnji izvleček pravilnika in seznam "Zahtevane priloge za to vlogo", v katerem so
pogoji že razrešeni: zahtevaj samo priloge, označene z OBVEZNA; prilog, označenih z NI POTREBNA, ne zahtevaj.
Priloga je priložena, če je v seznamu priloženih prilog navedena z enakim ali očitno enakovrednim opisom
(npr. "dokazilo o lastništvu (izjava rejca)" ustreza zahtevi "dokazilo o lastništvu").
Odgovori v slovenščini, z JSON objektom s polji: popolna (true/false), manjkajoce (seznam manjkajočih
OBVEZNIH prilog, prazen če je vloga popolna), obrazlozitev (največ tri stavki, uradniško vljudno)."""


NAVODILA_S_SPOMINOM = """Si referent na Upravni enoti Zgornja Lipica. Preveri, ali je vloga popolna.
Upoštevaj izvleček pravilnika in seznam "Zahtevane priloge za to vlogo", v katerem so pogoji pravilnika že razrešeni.
Poleg pravilnika VELJAJO tudi naučeni postopki urada iz tvojega spomina (blok "Naučeni postopki urada", če je
prisoten) in imajo PREDNOST pred seznamom: če naučeni postopek ob izpolnjenem pogoju zahteva prilogo, ki je po
seznamu "NI POTREBNA po pravilniku", jo vseeno zahtevaj (vloga je potem nepopolna) in v obrazložitvi navedi, da to
zahteva postopek urada. Podatek "prejšnji dokument ... star N let" uporabi za pogoje v naučenih postopkih.
Če naučeni postopek naroča, da stranko vnaprej opozoriš na kaj, to opozorilo vključi v obrazložitev.
Priloga je priložena, če je v seznamu priloženih prilog navedena z enakim ali očitno enakovrednim opisom.
Odgovori v slovenščini, z JSON objektom s polji v tem vrstnem redu:
postopki_urada: za VSAK zapis iz bloka "Naučeni postopki urada" en objekt: postopek (kratek povzetek zapisa),
pogoj (DOBESEDNI prag iz zapisa, npr. "prejšnja izkaznica starejša od deset let", ne prag iz pravilnika), podatek
(ustrezni podatek iz vloge, npr. "prejšnja izkaznica je stara 12 let"), velja (true, če je pogoj izpolnjen; true tudi,
kadar zapis nima pogoja), zahtevana_priloga (priloga, ki jo postopek zahteva, kadar velja; null, če zahteva le
opozorilo), opozorilo (besedilo opozorila stranki ali null); prazen seznam, če bloka ni;
popolna (true/false); manjkajoce (seznam manjkajočih prilog, prazen če je vloga popolna); obrazlozitev (največ
štirje stavki, uradniško vljudno, vključno z opozorili iz postopkov urada)."""


class OcenaPostopka(BaseModel):
    postopek: str
    pogoj: str
    podatek: str
    velja: bool
    zahtevana_priloga: str | None = None
    opozorilo: str | None = None


class OdgovorReferentaSpomin(BaseModel):
    """Act 4 answer: the model evaluates every learned procedure BEFORE it decides (field order = generation order);
    the code then enforces the consequence of every procedure that holds."""

    postopki_urada: list[OcenaPostopka]
    popolna: bool
    manjkajoce: list[str]
    obrazlozitev: str


def uveljavi_postopke(odgovor: OdgovorReferentaSpomin, priloge: list[str]) -> tuple[bool, list[str], list[str]]:
    """The model judged each procedure; a procedure that holds and demands an attachment that is not attached makes
    the application incomplete, whatever the model wrote in `popolna`. Returns (popolna, manjkajoce, lines)."""
    manjka = list(odgovor.manjkajoce)
    lines: list[str] = []
    for o in odgovor.postopki_urada:
        line = f"{o.pogoj}; {o.podatek} → {'pogoj velja' if o.velja else 'pogoj ne velja'}"
        if o.velja and o.zahtevana_priloga:
            if any(pravilnik._matches(o.zahtevana_priloga, s) for s in priloge):
                line += f" → {o.zahtevana_priloga} je priložena"
            else:
                line += f" → zahtevam: {o.zahtevana_priloga}"
                if not any(pravilnik._matches(o.zahtevana_priloga, m) for m in manjka):
                    manjka.append(o.zahtevana_priloga)
        if o.velja and o.opozorilo:
            line += f" → opozorilo: {o.opozorilo}"
        lines.append(line)
    return (not manjka, manjka, lines)


async def preveri_priloge_z_agentom(s: SprejetaVloga, agent, *, session=None) -> PreverjanjePrilog:
    """Act 4: the same check, routed through `Agent.run` so the memory providers fire (research §5)."""
    options: dict = {"response_format": OdgovorReferentaSpomin, "temperature": 0}
    try:
        response = await agent.run(sestavi_prompt(s), session=session, options=options)
    except Exception as e:  # some reasoning models reject temperature; the deterministic field order still helps
        if "temperature" not in str(e).lower():
            raise
        options.pop("temperature")
        response = await agent.run(sestavi_prompt(s), session=session, options=options)
    try:
        odgovor = response.value
        if not isinstance(odgovor, OdgovorReferentaSpomin):
            odgovor = OdgovorReferentaSpomin.model_validate_json(response.text)
    except ValidationError:
        m = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not m:
            raise
        odgovor = OdgovorReferentaSpomin.model_validate(json.loads(m.group(0)))
    popolna, manjka, lines = uveljavi_postopke(odgovor, s.vloga.priloge)
    return PreverjanjePrilog(
        vloga_id=s.vloga.id,
        popolna=popolna,
        manjkajoce=manjka,
        obrazlozitev=odgovor.obrazlozitev,
        vir="azure+spomin:" + os.environ.get("AZURE_OPENAI_CHAT_COMPLETION_MODEL", "?"),
        sprejeta=s,
        postopki_urada=lines,
    )


def sestavi_prompt(s: SprejetaVloga) -> str:
    p = pravilnik.postopek(s.vloga.postopek)
    starost = s.stranka.dokument.starost_let(s.datum_obravnave)
    priloge = "\n".join(f"- {x}" for x in s.vloga.priloge) or "- (nič)"
    zahtevane = "\n".join(
        f"- {req.split(' — ')[0]}: {'OBVEZNA' if required else 'NI POTREBNA po pravilniku (pogoj pravilnika ni izpolnjen)'}"
        for req, required in pravilnik.zahtevane_priloge(s.vloga, s.stranka, s.datum_obravnave)
    )
    return f"""{pravilnik.splosne_dolocbe()}

{p.besedilo}

## Vloga {s.vloga.id}
- Postopek: {p.sifra} {p.naziv}
- Stranka: {s.stranka.ime} ({s.stranka.id})
- Prejšnji dokument: {s.stranka.dokument.vrsta} {s.stranka.dokument.stevilka}, izdan {s.stranka.dokument.datum_izdaje.isoformat()} (star {starost} let na dan {s.datum_obravnave.isoformat()})
- Opomba stranke: {s.vloga.opomba_stranke or "(brez)"}

## Zahtevane priloge za to vlogo (pogoji razrešeni)
{zahtevane}

## Priložene priloge
{priloge}
"""


def _parse(text: str) -> OdgovorReferenta:
    """Defensive parse: models without JSON mode sometimes wrap the object in prose or fences."""
    try:
        return OdgovorReferenta.model_validate_json(text)
    except ValidationError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise
        return OdgovorReferenta.model_validate(json.loads(m.group(0)))


def _po_pravilniku(s: SprejetaVloga, vir: str) -> PreverjanjePrilog:
    popolna, manjka, obr = pravilnik.preveri_po_pravilniku(s.vloga, s.stranka, s.datum_obravnave)
    return PreverjanjePrilog(vloga_id=s.vloga.id, popolna=popolna, manjkajoce=manjka, obrazlozitev=obr, vir=vir, sprejeta=s)


async def _vprasaj_model(s: SprejetaVloga, backend: str, timeout: float) -> OdgovorReferenta:
    client = make_chat_client(backend)
    response = await asyncio.wait_for(
        client.get_response(
            [Message("system", [NAVODILA]), Message("user", [sestavi_prompt(s)])],
            options={"response_format": OdgovorReferenta},
        ),
        timeout=timeout,
    )
    try:
        odgovor = response.value  # parsed by the client; raises ValidationError on non-JSON text
        if isinstance(odgovor, OdgovorReferenta):
            return odgovor
    except ValidationError:
        pass
    return _parse(response.text)


async def preveri_priloge(s: SprejetaVloga, backend: str, *, timeout: float = 90, fallback: bool = True) -> PreverjanjePrilog:
    if backend == "mock":
        return _po_pravilniku(s, "pravilnik")
    try:
        odgovor = await _vprasaj_model(s, backend, timeout)
    except Exception as e:  # model down, timeout, unparsable output: the show must go on, visibly
        if not fallback:
            raise
        opozorilo(f"   model ni odgovoril ({type(e).__name__}): preverjam po pravilniku")
        return _po_pravilniku(s, f"pravilnik (rezerva, {model_label(backend)}: {type(e).__name__})")
    return PreverjanjePrilog(
        vloga_id=s.vloga.id,
        popolna=odgovor.popolna,
        manjkajoce=odgovor.manjkajoce,
        obrazlozitev=odgovor.obrazlozitev,
        vir=model_label(backend),
        sprejeta=s,
    )
