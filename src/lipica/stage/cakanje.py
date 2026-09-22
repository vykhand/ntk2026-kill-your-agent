"""Notebook 04 helpers: the phone's QR code and a table-friendly shape for a pending stamp request.

Everything else the notebook needs — starting/killing the worker, the live DAG, the scheduler table,
`zig_api.cakajoce`/`odgovori` themselves — already lives in `lipica.stage`/`lipica.hosts.zig_api`; this
module only adds the bits specific to this beat.
"""

from __future__ import annotations

import io
import socket

import qrcode

from lipica.hosts.zig_api import Zahteva


def telefon_tece(port: int = 8000, timeout: float = 0.5) -> bool:
    """True if something already answers on the phone page's port — this notebook's own `uv run zig`, one
    from an earlier kernel, or `make zig` in a terminal. A second `uv run zig` would only die with
    "address already in use", so the notebook reuses the running one instead."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def qr_png(url: str) -> bytes:
    """A PNG QR code for the phone URL (`mo.image` takes raw bytes)."""
    img = qrcode.make(url, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def vrstica(z: Zahteva) -> dict:
    """One `Zahteva` as a flat dict: a row of `mo.ui.table` the presenter can select."""
    d = z.data
    return {
        "vloga": d.get("vloga_id", z.instance_id),
        "listek": d.get("listek"),
        "stranka": d.get("stranka"),
        "postopek": d.get("postopek"),
        "podpisnik": d.get("podpisnik") or "",
        "preverjanje": "popolna" if d.get("popolna") else "nepopolna: " + ", ".join(d.get("manjkajoce") or []),
        "request_id": z.request_id,
    }


def tabela(zahteve: list[Zahteva]) -> list[dict]:
    """Every pending request, in `zig_api.cakajoce`'s order, as table rows."""
    return [vrstica(z) for z in zahteve]


def najdi(zahteve: list[Zahteva], request_id: str) -> Zahteva | None:
    """The `Zahteva` a selected table row refers to (it may have just been answered elsewhere — the
    phone, another notebook cell — in which case this is None and the table simply refreshes)."""
    return next((z for z in zahteve if z.request_id == request_id), None)
