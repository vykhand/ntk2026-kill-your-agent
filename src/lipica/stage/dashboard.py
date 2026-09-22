"""Glue for notebooks `03_durable` and `06_azure`: the Durable Task dashboard's own deep-link URL
scheme, whether it will let itself be framed, and the Act 5 (Azure) connection details.

Both notebooks show the *same* scheduler table and live DAG against a different endpoint (the
emulator vs. a real Durable Task Scheduler); only the dashboard link and the "how do we even find
the endpoint" step differ, so that is what lives here instead of in `stage.scheduler`.
"""

from __future__ import annotations

import subprocess
import urllib.request
from dataclasses import dataclass

from lipica.pravilnik import ROOT


def emulator_deep_link(dashboard: str, iid: str) -> str:
    """The emulator dashboard's URL scheme, straight from `README.md`'s stage run-sheet: subscription
    `local` and scheduler `emulator` are fixed strings baked into the container image, not real Azure
    ids. Only valid for the emulator — the Azure portal blade `DTS_DASHBOARD` points at has its own
    shape and is not an instance-level deep link (see `act5/infra/main.bicep`'s `dashboardUrl`)."""
    return f"{dashboard}/subscriptions/local/schedulers/emulator/taskhubs/default/orchestrations/{iid}"


@dataclass(frozen=True)
class Okvir:
    """Whether a URL's own response headers let it be embedded in an iframe."""

    lahko: bool
    razlog: str


def preveri_iframe(url: str, timeout: float = 2.0) -> Okvir:
    """A `X-Frame-Options` or CSP `frame-ancestors` header that would refuse us -> don't even try the
    iframe (marimo has no way to catch a browser-side frame refusal, so this is the only signal we get
    before rendering). No such header -> assume framing works."""
    try:
        with urllib.request.urlopen(  # noqa: S310 (localhost or an explicit, trusted dashboard URL only)
            urllib.request.Request(url, method="GET"), timeout=timeout
        ) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
    except Exception as e:
        return Okvir(False, f"{type(e).__name__}: {e}")
    xfo = headers.get("x-frame-options", "")
    if xfo:
        return Okvir(False, f"X-Frame-Options: {xfo}")
    if "frame-ancestors" in headers.get("content-security-policy", ""):
        return Okvir(False, "Content-Security-Policy: frame-ancestors")
    return Okvir(True, "no X-Frame-Options/CSP on the response")


def dashboard_iframe(url: str, *, height: str = "640px") -> str:
    """A raw `<iframe>` embed of `url`, for `mo.Html(...)`. `mo.iframe()` is the wrong tool here: it
    treats its argument as inline HTML *content* (wrapped in `srcdoc`), not a URL to fetch — it cannot
    point an iframe at another server."""
    return f'<iframe src="{url}" width="100%" height="{height}" style="border:1px solid #D9D9D9;border-radius:8px;"></iframe>'


def prijazna_napaka(e: Exception) -> str:
    """One clear line for a failed Azure query — never a raw traceback on stage. Covers the two usual
    failures: no `az login` at all, and a login that exists but cannot reach the scheduler's
    tenant (`AADSTS50020`, account not registered there).
    Imports are lazy: `notebooks/03_durable.py` imports this module too and never touches Azure."""
    from azure.core.exceptions import ClientAuthenticationError
    from azure.identity import CredentialUnavailableError

    if isinstance(e, CredentialUnavailableError):
        return "No Azure login. Run `az login` (see act5/README.md)."
    if isinstance(e, ClientAuthenticationError):
        return "Azure login exists but can't reach the scheduler's tenant. Run `az login --tenant <DTS_TENANT>`."
    import grpc

    if isinstance(e, grpc.RpcError):
        detail = e.code().name if hasattr(e, "code") else str(e)
        return f"Scheduler not reachable: {detail}."
    return f"{type(e).__name__}: {e}"


class Act5NiPripravljen(RuntimeError):
    """No azd environment yet, or `azd` itself is missing — `scripts/act5_env.sh` said so on stderr."""


def act5_env() -> dict[str, str]:
    """The same connection details `make act5` uses, straight from `scripts/act5_env.sh` (it reads the
    azd environment; nothing here calls `azd` a second way). Raises `Act5NiPripravljen` with the
    script's own message on failure, so a notebook cell can show one clean line instead of a
    `CalledProcessError` traceback."""
    r = subprocess.run(
        ["bash", str(ROOT / "scripts" / "act5_env.sh")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if r.returncode != 0:
        raise Act5NiPripravljen(r.stderr.strip() or "scripts/act5_env.sh failed")
    env: dict[str, str] = {}
    for line in r.stdout.splitlines():
        line = line.strip()
        if line.startswith("export "):
            k, _, v = line[len("export ") :].partition("=")
            if k:
                env[k] = v
    return env
