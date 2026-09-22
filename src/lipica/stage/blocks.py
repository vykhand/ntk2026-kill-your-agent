"""Notebook 01 ("Build it") only: building the interactive DAG's three graph variants, and trimming
MAF's own source for a projector-sized teaching cell.

Nothing here touches the real workflow the acts run (`lipica.workflow.build_workflow`) — the variant
builder below exists only so the notebook's checkboxes can show *why* each edge is in the graph, one
at a time; the real graph always has all of them (see `lipica.workflow.build_workflow`'s docstring).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable

from agent_framework import Workflow, WorkflowBuilder

from lipica.workflow import (
    ID_ZIG_REFERENT,
    ID_ZIG_VODJA,
    WORKFLOW_NAME,
    CakanjeNaZig,
    IzdajOdlocbo,
    Podpisnik,
    PreveriPriloge,
    SprejmiVlogo,
)


def gradi_varianto(*, zavrnitev: bool, dvojna: bool) -> Workflow:
    """Base chain (`SprejmiVlogo -> PreveriPriloge -> ČakanjeNaŽig -> IzdajOdločbo`) always present;
    the rejection loop and the dual-signature fan-in are added independently, one `WorkflowBuilder`
    call per flag, for the checkboxes to show live."""
    sprejmi, preveri, cakanje = SprejmiVlogo(), PreveriPriloge(), CakanjeNaZig(hitl=False)
    izdaj = IzdajOdlocbo(idempotent=True)
    builder = (
        WorkflowBuilder(name=WORKFLOW_NAME, start_executor=sprejmi)
        .add_edge(sprejmi, preveri)
        .add_edge(preveri, cakanje)
        .add_edge(cakanje, izdaj)
    )
    if zavrnitev:
        builder = builder.add_edge(cakanje, preveri)
    if dvojna:
        referent = Podpisnik(ID_ZIG_REFERENT, vloga="referent")
        vodja = Podpisnik(ID_ZIG_VODJA, vloga="vodja oddelka")
        builder = builder.add_edge(cakanje, referent).add_edge(cakanje, vodja).add_fan_in_edges([referent, vodja], cakanje)
    return builder.build()


def brez_docstringa(vir: str) -> str:
    """`inspect.getsource(...)` with its leading docstring removed: still the real source (drifts with
    the function, unlike a hand-copied snippet), just without the wall of prose a teaching cell has no
    room for. A no-op if there is no docstring to strip."""
    vir = textwrap.dedent(vir)
    node = ast.parse(vir).body[0]
    body = getattr(node, "body", None)
    doc = body[0] if body else None
    if not (isinstance(doc, ast.Expr) and isinstance(doc.value, ast.Constant) and isinstance(doc.value.value, str)):
        return vir.rstrip() + "\n"
    lines = vir.splitlines()
    lines = lines[: doc.lineno - 1] + lines[doc.end_lineno :]
    if doc.lineno - 1 < len(lines) and lines[doc.lineno - 1].strip() == "":
        del lines[doc.lineno - 1]
    return "\n".join(lines).rstrip() + "\n"


def podpis(fn: Callable[..., object]) -> str:
    """One line of real signature plus the docstring's first sentence — for `WorkflowContext` methods,
    whose full bodies are MAF's internal plumbing (spans, tracing), not something the office cares about."""
    sig = inspect.signature(fn)
    prvi_stavek = next(iter((inspect.getdoc(fn) or "").strip().splitlines()), "")
    ime = getattr(fn, "__qualname__", getattr(fn, "__name__", str(fn)))
    return f"{ime}{sig}\n    \"\"\"{prvi_stavek}\"\"\""
