"""Act 4: the referent's memory, in Foundry Agent Service (preview).

Two scopes in one store:
  "referent"      the office's procedures; written ONLY by the coaching run, read by every application run
  "ID-TEST-00x"   one scope per citizen; written by that citizen's application runs (the GDPR beat deletes it)

Everything here is an in-project data-plane call. Nothing is provisioned except, once,
the memory store itself (`ustvari_shrambo`).
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator

from agent_framework import Agent, AgentSession, ContextProvider, Message, SessionContext
from agent_framework.foundry import FoundryMemoryProvider
from azure.ai.projects.aio import AIProjectClient
from azure.ai.projects.models import (
    MemoryItem,
    MemoryItemKind,
    MemorySearchOptions,
    MemoryStoreDefaultDefinition,
    MemoryStoreDefaultOptions,
)
from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import AzureCliCredential
from rich.markup import escape

from lipica import config  # noqa: F401  (loads .env before the settings below are read)
from lipica.console import console, korak
from lipica.pravilnik import ROOT

# Your Foundry project, e.g. https://<account>.services.ai.azure.com/api/projects/<project> (see .env.example)
ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "")
SUBSCRIPTION = os.environ.get("AZURE_SUBSCRIPTION_ID", "")  # optional: pins which az login answers for the project
STORE = os.environ.get("MEMORY_STORE_NAME", "ue-lipica-spomin")
CHAT_MODEL = os.environ.get("FOUNDRY_MODEL", "gpt-5.4-mini")
EMBEDDING_MODEL = os.environ.get("FOUNDRY_EMBEDDING_MODEL", "text-embedding-3-large")
SCOPE_REFERENT = "referent"
SNAP_DIR = ROOT / "fixtures" / "spomin"

# The coaching line, in two wordings: "spec" = the original one, "predlog" = the reworded one.
# First live run: the spec wording was stored as "applications older than ten
# years" and the model rightly found it inapplicable to a 12-year-old document. SPOMIN_NAVODILO selects.
NAVODILA_VARIANTE = {
    "spec": (
        "Za vloge, starejše od deset let, vedno zahtevaj novo fotografijo. "
        "Stranko vnaprej opozori na najpogosteje manjkajočo prilogo."
    ),
    "predlog": (
        "Če je prejšnja osebna izkaznica stranke starejša od deset let, vedno zahtevaj novo fotografijo, "
        "tudi če je pravilnik ne zahteva. Stranko vnaprej opozori na prilogo, ki jo stranke pri tem postopku "
        "najpogosteje pozabijo."
    ),
}
NAVODILO_VARIANTA = os.environ.get("SPOMIN_NAVODILO", "predlog").strip().lower()
NAVODILO = NAVODILA_VARIANTE.get(NAVODILO_VARIANTA, NAVODILA_VARIANTE["predlog"])

# Instructions for the coaching turn only (never stored: system text is not written). The acknowledgment repeats
# the condition and the demand verbatim, so the extractor sees the concrete rule twice and keeps it concrete.
NAVODILA_UCENJE = (
    "Si referent na Upravni enoti Zgornja Lipica. Vodja oddelka ti daje navodilo za delo. Potrdi ga z enim ali "
    "dvema stavkoma v slovenščini, brez JSON, tako da dobesedno ponoviš pogoj (starost prejšnje osebne izkaznice) in "
    "zahtevo (nova fotografija; vnaprejšnje opozorilo na najpogosteje pozabljeno prilogo)."
)


def zapis_vsebuje_pravilo(items: list) -> bool:
    """Did the extraction keep the concrete rule? (photo + the ten-year condition)"""
    for m in items:
        t = m.content.lower()
        if "fotografij" in t and ("deset" in t or "10 let" in t or "10-ih" in t):
            return True
    return False

# Creation-time steering of what the service extracts and in which language (research §2: `user_profile_details`).
PODROBNOSTI_PROFILA = (
    "Zapisuj spomine v slovenščini. Beleži postopkovna pravila, ki jih referent dobi od vodje: katere dodatne "
    "priloge zahtevati in pod katerimi pogoji (npr. starost prejšnjega dokumenta), ter kako stranko vnaprej opozoriti. "
    "Pravilo zapiši kot navodilo referentu, dobesedno in s pogojem. Ne beleži tehničnih podrobnosti o obliki odgovora."
)
KONTEKST_REFERENT = (
    "## Naučeni postopki urada (iz spomina referenta)\n"
    "Ta navodila vodje oddelka veljajo POLEG pravilnika in imajo PREDNOST pred seznamom 'Zahtevane priloge za to "
    "vlogo': če navodilo ob izpolnjenem pogoju zahteva prilogo, ki je po seznamu 'NI POTREBNA po pravilniku', jo "
    "vseeno zahtevaj, vlogo označi kot nepopolno in v obrazložitvi navedi, da to zahteva postopek urada. "
    "Naučeni postopek lahko določa STROŽJI pogoj kot pravilnik (npr. nižjo starostno mejo dokumenta): pogoj in "
    "številko vzemi DOBESEDNO iz naučenega postopka, NE iz pravilnika, in ju primerjaj s podatkom 'prejšnji dokument "
    "... star N let'. Če navodilo naroča opozorilo stranki, ga vključi."
)
KONTEKST_STRANKA = "## Zapisi o stranki\nIz prejšnjih obiskov te stranke:"


@asynccontextmanager
async def klient() -> AsyncIterator[tuple[AIProjectClient, "Spomin"]]:
    """The project client for an existing Foundry project; `az login` identity, Foundry User on the account.
    With AZURE_SUBSCRIPTION_ID set it is pinned to that subscription, so it works whichever az login is the default."""
    if not ENDPOINT:
        raise SystemExit("FOUNDRY_PROJECT_ENDPOINT is not set (see .env.example)")
    async with AzureCliCredential(subscription=SUBSCRIPTION or None) as cred, AIProjectClient(endpoint=ENDPOINT, credential=cred) as pc:
        yield pc, Spomin(pc)


class Spomin:
    """Thin wrapper over `pc.beta.memory_stores` with the demo's conventions (store name, scopes, snapshots)."""

    def __init__(self, pc: AIProjectClient, store: str = STORE) -> None:
        self.pc = pc
        self.ms = pc.beta.memory_stores
        self.store = store

    # ---- store --------------------------------------------------------------------------------
    def definicija(self) -> MemoryStoreDefaultDefinition:
        return MemoryStoreDefaultDefinition(
            chat_model=CHAT_MODEL,
            embedding_model=EMBEDDING_MODEL,
            options=MemoryStoreDefaultOptions(
                user_profile_enabled=True,
                user_profile_details=PODROBNOSTI_PROFILA,
                chat_summary_enabled=False,
                procedural_memory_enabled=True,  # creation-time only
                default_ttl_seconds=timedelta(0),  # never expire: rehearsals span weeks
            ),
        )

    async def izbrisi_shrambo(self) -> bool:
        """Irreversible for the store's contents; used once to re-create the (empty) store with new options."""
        r = await self.ms.delete(name=self.store)
        return bool(r.deleted)

    async def shramba(self):
        try:
            return await self.ms.get(name=self.store)
        except ResourceNotFoundError:
            return None

    async def ustvari_shrambo(self):
        """THE one create call of Act 4 (`uv run act4 store-create --yes`)."""
        return await self.ms.create(
            name=self.store,
            description="Upravna enota Zgornja Lipica: spomin referenta (NTK 2026, demo)",
            definition=self.definicija(),
        )

    # ---- items ----------------------------------------------------------------------------------
    async def seznam(self, scope: str, kind: str | MemoryItemKind | None = None) -> list[MemoryItem]:
        return [m async for m in self.ms.list_memories(name=self.store, scope=scope, kind=kind, limit=100)]

    async def zapisi(self, scope: str, content: str, kind: str | MemoryItemKind = MemoryItemKind.PROCEDURAL) -> MemoryItem:
        return await self.ms.create_memory(name=self.store, scope=scope, content=content, kind=kind)

    async def izbrisi(self, memory_id: str) -> bool:
        r = await self.ms.delete_memory(name=self.store, memory_id=memory_id)
        return bool(r.deleted)

    async def pozabi(self, scope: str) -> bool:
        """The right to be forgotten: every memory in one citizen's scope, the store untouched."""
        r = await self.ms.delete_scope(name=self.store, scope=scope)
        return bool(r.deleted)

    async def isci(self, scope: str, besedilo: str, max_memories: int = 5) -> list[MemoryItem]:
        """What the provider would inject for this text (contextual search)."""
        res = await self.ms.search_memories(
            name=self.store,
            scope=scope,
            items=[{"role": "user", "type": "message", "content": besedilo}],
            options=MemorySearchOptions(max_memories=max_memories),
        )
        return [hit.memory_item for hit in res.memories]

    # ---- snapshots (reset scripts) -----------------------------------------------------------------
    async def posnetek(self, ime: str, scopes: list[str]) -> dict[str, list[dict]]:
        data = {scope: [m.as_dict() for m in await self.seznam(scope)] for scope in scopes}
        SNAP_DIR.mkdir(parents=True, exist_ok=True)
        (SNAP_DIR / f"{ime}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    async def pocisti(self, scopes: list[str]) -> dict[str, bool]:
        return {scope: await self.pozabi(scope) for scope in scopes}

    async def obnovi(self, ime: str) -> dict[str, list[MemoryItem]]:
        """Clean the scopes in the snapshot, then re-create every item. Ids change: never keep ids across a restore."""
        data = json.loads((SNAP_DIR / f"{ime}.json").read_text(encoding="utf-8"))
        await self.pocisti(list(data))
        out: dict[str, list[MemoryItem]] = {}
        for scope, items in data.items():
            out[scope] = [await self.zapisi(scope, d["content"], d["kind"]) for d in items]
        return out


# ---- providers ---------------------------------------------------------------------------------------


class AwaitedFoundryMemoryProvider(FoundryMemoryProvider):
    """`after_run` re-implemented so `agent.run()` returns only after the extraction finished, and the operations
    are printed as they land. The stock provider fires the update and drops the poller (research §4)."""

    async def after_run(self, *, agent: Any, session: AgentSession, context: SessionContext, state: dict[str, Any]) -> None:
        msgs: list[Message] = list(context.input_messages)
        if context.response and context.response.messages:
            msgs.extend(context.response.messages)
        items = [
            {"role": m.role, "type": "message", "content": m.text}
            for m in msgs
            if m.role in {"user", "assistant"} and m.text and m.text.strip()
        ]
        if not items:
            return
        poller = await self.project_client.beta.memory_stores.begin_update_memories(
            name=self.memory_store_name,
            scope=self.scope,
            items=items,
            previous_update_id=state.get("previous_update_id"),
            update_delay=0,
            polling_interval=2,
        )
        state["previous_update_id"] = poller.update_id
        korak("Spomin", f"zapisujem v obseg [bold]{escape(self.scope)}[/] … (čakam, da Foundry izlušči zapise)")
        result = await poller.result()
        ops = list(result.memory_operations or [])
        if not ops:
            korak("Spomin", "Foundry ni zapisal ničesar novega")
        for op in ops:
            item = op.memory_item
            korak("Spomin", f"{op.kind} · {item.kind} · {item.memory_id} · {escape(item.content)}")


class ReadOnlyFoundryMemoryProvider(FoundryMemoryProvider):
    """Reads the shared office scope on application runs and never writes to it. The stock provider injects the
    hits as a *user* message; gpt-5.4-mini then sided with the rulebook's "NI POTREBNA" line in two runs out of
    three, so the hits go in as instructions with an explicit precedence statement."""

    async def before_run(self, *, agent: Any, session: AgentSession, context: SessionContext, state: dict[str, Any]) -> None:
        text = "\n".join(m.text for m in context.input_messages if m.text)
        if not text.strip():
            return
        try:
            res = await self.project_client.beta.memory_stores.search_memories(
                name=self.memory_store_name,
                scope=self.scope,
                items=[{"role": "user", "type": "message", "content": text}],
                options=MemorySearchOptions(max_memories=5),
            )
        except Exception as e:  # memory is non-critical: the check still runs on the rulebook alone
            korak("Spomin", f"[red]iskanje v spominu ni uspelo ({type(e).__name__})[/]")
            return
        contents = [h.memory_item.content for h in res.memories if h.memory_item.content]
        korak("Spomin", f"iz obsega [bold]{escape(self.scope)}[/] prebral {len(contents)} zapisov" + (": " + escape(" | ".join(c[:70] for c in contents)) if contents else ""))
        if contents:
            context.extend_instructions(self.source_id, self.context_prompt + "\n" + "\n".join(f"- {c}" for c in contents))

    async def after_run(self, *, agent: Any, session: AgentSession, context: SessionContext, state: dict[str, Any]) -> None:
        return


class ListingMemoryProvider(ContextProvider):
    """Fallback for the retrieval path (research §8.1): inject every item of a scope, no semantic search.
    Used when SPOMIN_NACIN=list."""

    def __init__(self, source_id: str, *, spomin: Spomin, scope: str, context_prompt: str) -> None:
        super().__init__(source_id)
        self.spomin, self.scope, self.context_prompt = spomin, scope, context_prompt

    async def before_run(self, *, agent: Any, session: AgentSession, context: SessionContext, state: dict[str, Any]) -> None:
        items = await self.spomin.seznam(self.scope)
        if items:
            context.extend_instructions(self.source_id, self.context_prompt + "\n" + "\n".join(f"- {m.content}" for m in items))


def referent_agent(pc: AIProjectClient, chat_client: Any, instructions: str, *, coaching: bool, stranka_scope: str | None = None) -> Agent:
    """Coaching run: the office scope, awaited writes. Application run: office scope read-only + the citizen's scope."""
    nacin = os.environ.get("SPOMIN_NACIN", "search").strip().lower()
    providers: list[ContextProvider] = []
    if coaching:
        providers.append(
            AwaitedFoundryMemoryProvider("spomin_referent", project_client=pc, memory_store_name=STORE, scope=SCOPE_REFERENT, context_prompt=KONTEKST_REFERENT)
        )
    else:
        if nacin == "list":
            providers.append(ListingMemoryProvider("spomin_referent", spomin=Spomin(pc), scope=SCOPE_REFERENT, context_prompt=KONTEKST_REFERENT))
        else:
            providers.append(
                ReadOnlyFoundryMemoryProvider("spomin_referent", project_client=pc, memory_store_name=STORE, scope=SCOPE_REFERENT, context_prompt=KONTEKST_REFERENT)
            )
        if stranka_scope:
            providers.append(  # fire-and-forget: the application run must not wait on extraction
                FoundryMemoryProvider("spomin_stranka", project_client=pc, memory_store_name=STORE, scope=stranka_scope, context_prompt=KONTEKST_STRANKA, update_delay=0)
            )
    return Agent(client=chat_client, instructions=instructions, context_providers=providers)


def izpisi_zapise(items: list[MemoryItem], naslov: str) -> None:
    console.rule(naslov)
    if not items:
        console.print("  (spomin je prazen)")
    for m in items:
        console.print(f"  [dim]{m.memory_id}[/]  [magenta]{m.kind}[/]  {m.updated_at.strftime('%d.%m. %H:%M') if hasattr(m.updated_at, 'strftime') else m.updated_at}")
        console.print(f"     {escape(m.content)}")
