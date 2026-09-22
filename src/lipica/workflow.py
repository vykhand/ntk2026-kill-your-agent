"""THE workflow. One definition, two hosts (in-process for Act 1, Durable Task for Act 2+).

    SprejmiVlogo -> PreveriPriloge -> ČakanjeNaŽig -> IzdajOdločbo
                          ^               |
                          '--- zavrnjeno --'   (Act 3: the citizen brings the missing attachment)

Executor ids are Slovene on purpose: the Durable Task extension registers each one as an activity named
`dafx-vloga-<id>`, and that is what the DTS dashboard shows. Messages between executors are plain JSON
dicts (the durable codec pickles anything else, which would make dashboard payloads unreadable); each
executor re-hydrates its Pydantic model on the first line. What differs between acts is decided by the
host through constructor flags: `IzdajOdlocbo(idempotent=...)`, `CakanjeNaZig(hitl=...)`.

No `from __future__ import annotations` here on purpose: the @response_handler validator reads the
`ctx: WorkflowContext[...]` annotation as a real object, not a string.
"""

import asyncio
from typing import Never

from agent_framework import Executor, Workflow, WorkflowBuilder, WorkflowContext, handler, response_handler
from rich.markup import escape

from lipica import fixtures_io, pravilnik, runstate
from lipica.config import nastavitve
from lipica.console import console, korak, opozorilo
from lipica.domain import PreverjanjePrilog, SprejetaVloga, Zig
from lipica.listek import narisi_listek
from lipica.llm import preveri_priloge
from lipica.odlocba import eur, izdaj_odlocbo

WORKFLOW_NAME = "vloga"  # must be ASCII for the durable host; activities become dafx-vloga-<executor id>
ID_SPREJMI, ID_PREVERI, ID_CAKANJE, ID_IZDAJ = "SprejmiVlogo", "PreveriPriloge", "ČakanjeNaŽig", "IzdajOdločbo"
ID_ZIG_REFERENT, ID_ZIG_VODJA = "ŽigReferenta", "ŽigVodje"  # the dual-approval signers (rulebook: "dvojna odobritev")


def zahteva_za_zig(prev: PreverjanjePrilog, *, podpisnik: str | None = None) -> dict:
    """What the phone sees. A plain dict: it lands verbatim in the scheduler's custom status."""
    s = prev.sprejeta
    return {
        "vloga_id": prev.vloga_id,
        "stranka": s.stranka.ime,
        "postopek": f"{s.vloga.postopek} {s.vloga.naziv}",
        "listek": s.listek_stevilka,
        "priloge": s.vloga.priloge,
        "popolna": prev.popolna,
        "manjkajoce": prev.manjkajoce,
        "obrazlozitev": prev.obrazlozitev,
        "vir": prev.vir,
        "podpisnik": podpisnik,
        "preverjanje": prev.model_dump(mode="json"),
    }


def dopolnitev_za(prev: PreverjanjePrilog, zahtevano: list[str]) -> list[str]:
    """What the citizen has to bring after a rejection: the reviewer's list, else the check's list,
    else the rulebook's most-often-forgotten attachment for the procedure."""
    if zahtevano:
        return zahtevano
    if prev.manjkajoce:
        return list(prev.manjkajoce)
    return [pravilnik.postopek(prev.sprejeta.vloga.postopek).najpogosteje_manjka]


class SprejmiVlogo(Executor):
    """Intake: load the application, print the queue ticket."""

    def __init__(self, id: str = ID_SPREJMI) -> None:
        super().__init__(id=id)

    @handler
    async def sprejmi(self, vloga_id: str, ctx: WorkflowContext[dict]) -> None:
        runstate.set_step(vloga_id, self.id)
        vloga = fixtures_io.vloga(vloga_id)
        stranka = fixtures_io.stranka(vloga.stranka_id)
        stevilka = runstate.naslednja_stevilka_listka()
        sprejeta = SprejetaVloga(
            vloga=vloga,
            stranka=stranka,
            listek_stevilka=stevilka,
            na_vrsti=max(1, stevilka - 35),
            datum_obravnave=fixtures_io.datum_obravnave(),
        )
        korak(self.id, f"{vloga.id} · {stranka.ime} · {vloga.postopek}")
        console.print(narisi_listek(stevilka, sprejeta.na_vrsti, vloga.id, vloga.postopek, vloga.naziv), style="cyan")
        await ctx.send_message(sprejeta.model_dump(mode="json"))


class PreveriPriloge(Executor):
    """The LLM step. The kill lands here: "referent je šel na malico"."""

    def __init__(self, id: str = ID_PREVERI) -> None:
        super().__init__(id=id)

    @handler
    async def preveri(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        sprejeta = SprejetaVloga.model_validate(msg)
        n = nastavitve()
        runstate.set_step(sprejeta.vloga.id, self.id)
        if sprejeta.dopolnitev:
            korak(self.id, f"{sprejeta.vloga.id} · dopolnitev prejeta: {escape(', '.join(sprejeta.dopolnitev))}")
        korak(self.id, f"{sprejeta.vloga.id} · referent pregleduje priloge (priloge: {len(sprejeta.vloga.priloge)})")
        for preostalo in range(int(n.malica_seconds), 0, -1):
            console.print(f"   [yellow]… pregled v teku, {preostalo} s[/]")
            await asyncio.sleep(1)
        rezultat = await preveri_priloge(sprejeta, n.llm_backend, timeout=n.llm_timeout, fallback=n.llm_fallback)
        vir = escape(rezultat.vir)
        if rezultat.popolna:
            korak(self.id, f"[green]popolna[/] ({vir}) · {escape(rezultat.obrazlozitev)}")
        else:
            korak(self.id, f"[red]nepopolna[/] ({vir}) · manjka: {escape(', '.join(rezultat.manjkajoce))}")
        await ctx.send_message(rezultat.model_dump(mode="json"))


class CakanjeNaZig(Executor):
    """Waiting for the stamp. Auto-stamped when `hitl=False`; with `hitl=True` the workflow parks here
    until a human answers on the phone, for as long as it takes, at zero compute."""

    def __init__(self, id: str = ID_CAKANJE, *, hitl: bool = False) -> None:
        super().__init__(id=id)
        self.hitl = hitl

    @handler
    async def cakaj(self, msg: dict, ctx: WorkflowContext[dict, dict]) -> None:
        prev = PreverjanjePrilog.model_validate(msg)
        runstate.set_step(prev.vloga_id, self.id)
        if not self.hitl:
            if not prev.popolna:
                korak(self.id, f"{prev.vloga_id} · poziv k dopolnitvi: {escape(', '.join(prev.manjkajoce))}")
                await ctx.yield_output({"vloga_id": prev.vloga_id, "stanje": "poziv_k_dopolnitvi", "manjkajoce": prev.manjkajoce})
                return
            zig = Zig(vloga_id=prev.vloga_id, odobreno=True, odobril="referent (samodejni žig)", preverjanje=prev)
            korak(self.id, f"{prev.vloga_id} · žig odobren")
            await ctx.send_message(zig.model_dump(mode="json"), target_id=ID_IZDAJ)
            return

        if pravilnik.postopek(prev.sprejeta.vloga.postopek).dvojna_odobritev:
            korak(self.id, f"{prev.vloga_id} · [magenta]dvojna odobritev[/] · referent in vodja oddelka, vzporedno")
            for target in (ID_ZIG_REFERENT, ID_ZIG_VODJA):
                await ctx.send_message(prev.model_dump(mode="json"), target_id=target)
            return

        korak(self.id, f"{prev.vloga_id} · [magenta]čakam na žig[/] · referent odloči na telefonu")
        await ctx.request_info(request_data=zahteva_za_zig(prev), response_type=dict)

    @response_handler
    async def odgovor(self, original_request: dict, response: dict, ctx: WorkflowContext[dict]) -> None:
        """The phone answered: {"odobreno": bool, "odobril": <channel>, "opomba": str, "dopolnitev": [str]}"""
        prev = PreverjanjePrilog.model_validate(original_request["preverjanje"])
        runstate.set_step(prev.vloga_id, self.id)
        kanal = str(response.get("odobril") or "telefon")
        if response.get("odobreno"):
            await self._zigosaj(prev, odobril=f"referent ({kanal})", opomba=str(response.get("opomba") or ""), ctx=ctx)
            return
        await self._vrni_v_dopolnitev(prev, dopolnitev_za(prev, [str(x) for x in (response.get("dopolnitev") or [])]), ctx)

    @handler
    async def zberi(self, podpisi: list[dict], ctx: WorkflowContext[dict]) -> None:
        """Fan-in of the two signers. Both approved -> žig; any rejection -> the citizen completes the application."""
        prev = PreverjanjePrilog.model_validate(podpisi[0]["preverjanje"])
        runstate.set_step(prev.vloga_id, self.id)
        zavrnili = [p for p in podpisi if not p.get("odobreno")]
        if not zavrnili:
            await self._zigosaj(prev, odobril=" + ".join(str(p.get("odobril")) for p in podpisi), opomba="", ctx=ctx)
            return
        zahtevano = [str(x) for p in zavrnili for x in (p.get("dopolnitev") or [])]
        korak(self.id, f"{prev.vloga_id} · zavrnil: {escape(', '.join(str(p.get('podpisnik')) for p in zavrnili))}")
        await self._vrni_v_dopolnitev(prev, dopolnitev_za(prev, zahtevano), ctx)

    async def _zigosaj(self, prev: PreverjanjePrilog, *, odobril: str, opomba: str, ctx: WorkflowContext[dict]) -> None:
        zig = Zig(vloga_id=prev.vloga_id, odobreno=True, odobril=odobril, opomba=opomba, preverjanje=prev)
        korak(self.id, f"{prev.vloga_id} · [green]žig odobren[/] · {escape(zig.odobril)}")
        await ctx.send_message(zig.model_dump(mode="json"), target_id=ID_IZDAJ)

    async def _vrni_v_dopolnitev(self, prev: PreverjanjePrilog, dopolnitev: list[str], ctx: WorkflowContext[dict]) -> None:
        korak(self.id, f"{prev.vloga_id} · [red]zavrnjeno[/] · manjka: {escape(', '.join(dopolnitev))} · stranka dopolni vlogo")
        s = prev.sprejeta.model_copy(deep=True)
        s.vloga.priloge = [*s.vloga.priloge, *[d for d in dopolnitev if d not in s.vloga.priloge]]
        s.dopolnitev = dopolnitev
        await ctx.send_message(s.model_dump(mode="json"), target_id=ID_PREVERI)


class Podpisnik(Executor):
    """One signature of a dual approval: the referent and the vodja oddelka each get their own phone card,
    in parallel; ČakanjeNaŽig collects both (fan-in)."""

    def __init__(self, id: str, *, vloga: str) -> None:
        super().__init__(id=id)
        self.vloga = vloga

    @handler
    async def podpisi(self, msg: dict, ctx: WorkflowContext) -> None:
        prev = PreverjanjePrilog.model_validate(msg)
        runstate.set_step(prev.vloga_id, self.id)
        korak(self.id, f"{prev.vloga_id} · [magenta]čakam na podpis[/] · {self.vloga}")
        await ctx.request_info(request_data=zahteva_za_zig(prev, podpisnik=self.vloga), response_type=dict)

    @response_handler
    async def odgovor(self, original_request: dict, response: dict, ctx: WorkflowContext[dict]) -> None:
        odobreno = bool(response.get("odobreno"))
        kanal = str(response.get("odobril") or "telefon")
        korak(self.id, f"{original_request['vloga_id']} · {'[green]podpisano[/]' if odobreno else '[red]zavrnjeno[/]'} · {self.vloga} ({kanal})")
        await ctx.send_message({
            "podpisnik": self.vloga,
            "odobreno": odobreno,
            "odobril": f"{self.vloga} ({kanal})",
            "dopolnitev": [str(x) for x in (response.get("dopolnitev") or [])],
            "preverjanje": original_request["preverjanje"],
        })


class IzdajOdlocbo(Executor):
    """The side effect: PDF + fee. `idempotent=False` re-issues on every retry; `idempotent=True` doesn't."""

    def __init__(self, id: str = ID_IZDAJ, *, idempotent: bool = False) -> None:
        super().__init__(id=id)
        self.idempotent = idempotent

    @handler
    async def izdaj(self, msg: dict, ctx: WorkflowContext[Never, dict]) -> None:
        zig = Zig.model_validate(msg)
        runstate.set_step(zig.vloga_id, self.id)
        odlocba = izdaj_odlocbo(zig, idempotent=self.idempotent)
        if odlocba.ze_izdana:
            korak(self.id, f"{zig.vloga_id} · odločba {odlocba.stevilka} je že izdana, nič novega")
        else:
            korak(self.id, f"{zig.vloga_id} · [bold]ODLOČBA {odlocba.stevilka}[/] · taksa: {eur(odlocba.taksa_eur)}" + (" · [red]ŽIG[/]" if odlocba.zig else ""))
            if not self.idempotent:
                opozorilo("   (številka odločbe je naključna: vsak ponovni zagon izda novo)")
        runstate.clear_step()
        await ctx.yield_output(odlocba.model_dump(mode="json"))


def build_workflow(*, idempotent: bool, hitl: bool = False) -> Workflow:
    """`idempotent` picks the fragile or durable IzdajOdlocbo; `hitl` parks ČakanjeNaŽig for a human."""
    sprejmi, preveri = SprejmiVlogo(), PreveriPriloge()
    cakanje = CakanjeNaZig(hitl=hitl)
    izdaj = IzdajOdlocbo(idempotent=idempotent)
    referent = Podpisnik(ID_ZIG_REFERENT, vloga="referent")
    vodja = Podpisnik(ID_ZIG_VODJA, vloga="vodja oddelka")
    return (
        WorkflowBuilder(name=WORKFLOW_NAME, start_executor=sprejmi)
        .add_edge(sprejmi, preveri)
        .add_edge(preveri, cakanje)
        .add_edge(cakanje, izdaj)
        .add_edge(cakanje, preveri)  # the rejection loop; ČakanjeNaŽig always names its target
        .add_edge(cakanje, referent)  # dual approval: fan out to both signers ...
        .add_edge(cakanje, vodja)
        .add_fan_in_edges([referent, vodja], cakanje)  # ... and collect both signatures
        .build()
    )
