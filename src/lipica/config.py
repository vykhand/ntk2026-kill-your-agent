"""Demo knobs. Read from the environment and `.env`, except the ones that must never come from a file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from lipica.pravilnik import ROOT

_REAL_ENV = dict(os.environ)  # captured before .env is merged
# Explicit path, not bare load_dotenv(): its auto-discovery falls back to os.getcwd() whenever
# __main__ has no __file__ (marimo's kernel subprocesses, `python -c`, a REPL, ...), and a kernel's
# cwd is not guaranteed to be inside the repo tree — silently loading nothing and leaving every
# setting (LLM_BACKEND included) at its hard-coded default. Verified: the marimo notebooks were
# reporting `model: mock (brez modela)` in the status strip with LLM_BACKEND=ollama in .env.
load_dotenv(ROOT / ".env")


def _flag(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Nastavitve:
    llm_backend: str  # mock | ollama | azure  (see lipica.llm)
    malica_seconds: float  # visible countdown inside PreveriPriloge: the kill window
    llm_timeout: float  # seconds before a model call is abandoned
    llm_fallback: bool  # on model failure, fall back to the rulebook check with a visible warning
    kill_at: str  # "<Executor>[:<vloga id>]" for the rehearsal auto-kill; real environment only, never .env


def nastavitve() -> Nastavitve:
    return Nastavitve(
        llm_backend=os.environ.get("LLM_BACKEND", "mock").strip().lower(),
        malica_seconds=float(os.environ.get("MALICA_SECONDS", "6")),
        llm_timeout=float(os.environ.get("LLM_TIMEOUT", "90")),
        llm_fallback=_flag("LLM_FALLBACK", "1"),
        kill_at=_REAL_ENV.get("KILL_AT", "").strip(),
    )
