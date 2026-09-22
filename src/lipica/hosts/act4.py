"""Act 4: the agent that learns. `uv run act4 <ukaz>`   (cloud: your Foundry project, see .env.example)

    store                 show whether the memory store exists and how it is defined (read-only)
    store-create --yes    THE one create call
    coach   [VL-2026-0051]   process A, then coach the referent once; wait for the extraction, print what was stored
    apply   [VL-2026-0052]   process B (12-year-old document) with a fresh session; print what the referent read
    revert  [VL-2026-0053]   same as apply, for C after the rule was deleted
    list    [scope]          memory items verbatim (default: referent)
    delete  <memory_id>      delete one item live
    forget  <scope>          delete a citizen's whole scope (GDPR)
    snapshot <ime> / restore <ime> / clean     rehearsal reset: fixtures/spomin/<ime>.json
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import subprocess
import sys

from rich.markup import escape

from lipica import fixtures_io, spomin
from lipica.console import console, korak, naslov, opozorilo
from lipica.domain import SprejetaVloga
from lipica.llm import NAVODILA_S_SPOMINOM, make_chat_client, preveri_priloge_z_agentom, sestavi_prompt  # noqa: F401

# Optional: the subscription that holds the Foundry project. When set, every command pins the az CLI to it.
SUBSCRIPTION = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
VLOGA_A, VLOGA_B, VLOGA_C = "VL-2026-0051", "VL-2026-0052", "VL-2026-0053"
SCOPES = [spomin.SCOPE_REFERENT, "ID-TEST-004", "ID-TEST-005", "ID-TEST-006"]


def preveri_az() -> None:
    """The az CLI default can drift between logins: pin it every time, refuse to continue if that fails."""
    if SUBSCRIPTION:
        r = subprocess.run(["az", "account", "set", "--subscription", SUBSCRIPTION], capture_output=True, text=True)
        if r.returncode != 0:
            opozorilo("az account set ni uspel: " + r.stderr.strip()[-200:])
            sys.exit(1)
    r = subprocess.run(["az", "account", "show", "--query", "[name,user.name]", "-o", "tsv"], capture_output=True, text=True)
    console.print(f"[dim]azure: {' · '.join(r.stdout.split())}  ·  {spomin.ENDPOINT}  ·  shramba {spomin.STORE}[/]")


def sprejeta(vloga_id: str) -> SprejetaVloga:
    v = fixtures_io.vloga(vloga_id)
    s = fixtures_io.stranka(v.stranka_id)
    return SprejetaVloga(vloga=v, stranka=s, listek_stevilka=0, na_vrsti=0, datum_obravnave=fixtures_io.datum_obravnave())


def izpisi_preverjanje(r) -> None:
    for p in r.postopki_urada:
        console.print(f"   [magenta]naučeni postopek:[/] {escape(p)}")
    if r.popolna:
        korak("PreveriPriloge", f"[green]popolna[/] ({escape(r.vir)})")
    else:
        korak("PreveriPriloge", f"[red]nepopolna[/] ({escape(r.vir)}) · manjka: {escape(', '.join(r.manjkajoce))}")
    console.print(f"   [italic]{escape(r.obrazlozitev)}[/]")


async def cmd_store(sp: spomin.Spomin, create: bool) -> None:
    st = await sp.shramba()
    if st:
        console.print(f"shramba [bold]{st.name}[/] obstaja · {st.id} · {st.definition}")
        return
    console.print(f"shramba [bold]{spomin.STORE}[/] še ne obstaja v projektu.")
    console.print("definicija, ki bi jo ustvaril:")
    console.print(escape(str(sp.definicija().as_dict())))
    if not create:
        console.print("[dim]ustvari z: uv run act4 store-create --yes  (po odobritvi lastnika)[/]")
        return
    st = await sp.ustvari_shrambo()
    console.print(f"[green]ustvarjena[/] shramba {st.name} · {st.id}")


async def cmd_coach(pc, sp: spomin.Spomin, vloga_id: str) -> None:
    """Application A is checked WITHOUT writing to memory; only the coaching turn is stored (when
    both turns were written, the service consolidated the rule into the application's generic
    'only mandatory attachments' preference and lost it)."""
    naslov("Referent se uči", f"vloga {vloga_id}, nato eno navodilo; spomin: obseg '{spomin.SCOPE_REFERENT}'")
    s = sprejeta(vloga_id)
    chat = make_chat_client("azure")
    console.rule(f"Vloga {vloga_id} · {s.stranka.ime} · dokument star {s.stranka.dokument.starost_let(s.datum_obravnave)} let")
    referent = spomin.referent_agent(pc, chat, NAVODILA_S_SPOMINOM, coaching=False)  # reads memory, writes nothing
    izpisi_preverjanje(await preveri_priloge_z_agentom(s, referent))
    console.rule(f"Navodilo referentu, enkrat (varianta: {spomin.NAVODILO_VARIANTA})")
    console.print(f"[bold yellow]{escape(spomin.NAVODILO)}[/]")
    items: list = []
    for poskus in range(1, 4):
        ucenec = spomin.referent_agent(pc, chat, spomin.NAVODILA_UCENJE, coaching=True)  # awaited write to 'referent'
        r = await ucenec.run(spomin.NAVODILO)
        console.print(f"   [italic]{escape(r.text)}[/]")
        items = await sp.seznam(spomin.SCOPE_REFERENT)
        if spomin.zapis_vsebuje_pravilo(items):
            break
        opozorilo(f"   Foundry je navodilo posplošil in izgubil pogoj (poskus {poskus}); ponavljam navodilo.")
    spomin.izpisi_zapise(items, "Spomin referenta po učenju (dobesedno)")


async def cmd_apply(pc, sp: spomin.Spomin, vloga_id: str, title: str) -> None:
    s = sprejeta(vloga_id)
    naslov(title, f"vloga {vloga_id} · {s.stranka.ime} · dokument star {s.stranka.dokument.starost_let(s.datum_obravnave)} let · nova seja")
    hits = await sp.isci(spomin.SCOPE_REFERENT, sestavi_prompt(s))
    spomin.izpisi_zapise(hits, "Kar referent prebere iz spomina za to vlogo")
    agent = spomin.referent_agent(pc, make_chat_client("azure"), NAVODILA_S_SPOMINOM, coaching=False, stranka_scope=s.stranka.id)
    console.rule("Preverjanje prilog")
    izpisi_preverjanje(await preveri_priloge_z_agentom(s, agent))


async def cmd_list(sp: spomin.Spomin, scope: str) -> None:
    spomin.izpisi_zapise(await sp.seznam(scope), f"Spomin · obseg '{scope}'")


async def cmd_delete(sp: spomin.Spomin, memory_id: str) -> None:
    ok = await sp.izbrisi(memory_id)
    console.print(f"{'[green]izbrisano[/]' if ok else '[red]ni izbrisano[/]'} · {memory_id}")


async def cmd_forget(sp: spomin.Spomin, scope: str) -> None:
    n = len(await sp.seznam(scope))
    ok = await sp.pozabi(scope)
    console.print(f"{'[green]pozabljeno[/]' if ok else '[red]ni pozabljeno[/]'} · obseg '{scope}' · {n} zapisov · pravica do pozabe, tokrat uradno")


async def cmd_snapshot(sp: spomin.Spomin, ime: str) -> None:
    data = await sp.posnetek(ime, SCOPES)
    console.print(f"posnetek [bold]{ime}[/]: " + ", ".join(f"{k}={len(v)}" for k, v in data.items()) + f" → fixtures/spomin/{ime}.json")


async def cmd_restore(sp: spomin.Spomin, ime: str) -> None:
    out = await sp.obnovi(ime)
    console.print(f"obnovljeno iz [bold]{ime}[/]: " + ", ".join(f"{k}={len(v)}" for k, v in out.items()))


async def cmd_clean(sp: spomin.Spomin) -> None:
    res = await sp.pocisti(SCOPES)
    console.print("čisto: " + ", ".join(f"{k}={'da' if v else 'ne'}" for k, v in res.items()))


async def run(a: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("agent_framework_foundry._memory_provider").setLevel(logging.WARNING)
    os.environ.setdefault("AZURE_OPENAI_CHAT_COMPLETION_MODEL", spomin.CHAT_MODEL)
    preveri_az()
    async with spomin.klient() as (pc, sp):
        if a.ukaz == "store":
            await cmd_store(sp, create=False)
        elif a.ukaz == "store-create":
            if not a.yes:
                opozorilo("store-create zahteva --yes")
                sys.exit(2)
            await cmd_store(sp, create=True)
        elif a.ukaz == "coach":
            await cmd_coach(pc, sp, a.arg or VLOGA_A)
        elif a.ukaz == "apply":
            await cmd_apply(pc, sp, a.arg or VLOGA_B, "Referent uporabi naučeno")
        elif a.ukaz == "revert":
            await cmd_apply(pc, sp, a.arg or VLOGA_C, "Po izbrisu pravila")
        elif a.ukaz == "list":
            await cmd_list(sp, a.arg or spomin.SCOPE_REFERENT)
        elif a.ukaz == "delete":
            await cmd_delete(sp, a.arg)
        elif a.ukaz == "forget":
            await cmd_forget(sp, a.arg)
        elif a.ukaz == "snapshot":
            await cmd_snapshot(sp, a.arg or "post-coaching")
        elif a.ukaz == "restore":
            await cmd_restore(sp, a.arg or "post-coaching")
        elif a.ukaz == "clean":
            await cmd_clean(sp)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ukaz", choices=["store", "store-create", "coach", "apply", "revert", "list", "delete", "forget", "snapshot", "restore", "clean"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.ukaz in {"delete", "forget"} and not a.arg:
        ap.error(f"{a.ukaz} needs an argument")
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
