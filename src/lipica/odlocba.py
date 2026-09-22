"""Issue the odločba: a PDF with (after approval) a big red žig, plus a fee ledger line.

The number is the idempotency switch of the whole talk:
    non-idempotent: ODL-2026-<random>           (Act 1: restart => second odločba, second fee)
    idempotent:     ODL-2026-<hash of vloga id>  (Act 2+: re-issue is a no-op)
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from lipica.domain import Odlocba, Zig
from lipica.pravilnik import postopek
from lipica.runstate import OUT_DIR, ensure_dirs

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
_FONT: str | None = None


def _font() -> str:
    global _FONT
    if _FONT is None:
        _FONT = "Helvetica"
        for c in FONT_CANDIDATES:
            if Path(c).exists():
                pdfmetrics.registerFont(TTFont("Odlocba", c))
                _FONT = "Odlocba"
                break
    return _FONT


def eur(znesek: float) -> str:
    """Slovene money: comma decimal, and no fee is 'brez takse', as in the rulebook."""
    return "brez takse" if znesek == 0 else f"{znesek:.2f}".replace(".", ",") + " €"


def stevilka_odlocbe(vloga_id: str, idempotent: bool) -> str:
    if idempotent:
        return "ODL-2026-" + hashlib.sha256(vloga_id.encode()).hexdigest()[:6].upper()
    return "ODL-2026-" + uuid.uuid4().hex[:6].upper()


def _narisi_zig(c: canvas.Canvas, x: float, y: float, datum: str) -> None:
    c.saveState()
    c.translate(x, y)
    c.rotate(14)
    c.setStrokeColorRGB(0.78, 0.08, 0.08)
    c.setFillColorRGB(0.78, 0.08, 0.08)
    c.setFillAlpha(0.85)
    c.setStrokeAlpha(0.85)
    r = 30 * mm
    c.setLineWidth(2.2)
    c.circle(0, 0, r, stroke=1, fill=0)
    c.setLineWidth(0.9)
    c.circle(0, 0, r - 3.5 * mm, stroke=1, fill=0)
    f = _font()
    c.setFont(f, 9)
    c.drawCentredString(0, r - 11 * mm, "UPRAVNA ENOTA")
    c.drawCentredString(0, r - 15.5 * mm, "ZGORNJA LIPICA")
    c.setFont(f, 30)
    c.drawCentredString(0, -4 * mm, "ŽIG")
    c.setFont(f, 8.5)
    c.drawCentredString(0, -r + 13 * mm, "ODOBRENO")
    c.drawCentredString(0, -r + 9 * mm, datum)
    c.restoreState()


def _narisi_pdf(path: Path, o: Odlocba, z: Zig) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"Odločba {o.stevilka} (izmišljena)")
    f = _font()
    width, height = A4
    x0, y = 22 * mm, height - 28 * mm
    s = z.preverjanje.sprejeta

    c.setFont(f, 9)
    c.drawString(x0, y, "UPRAVNA ENOTA ZGORNJA LIPICA (izmišljena)  ·  Oddelek za splošne zadeve")
    y -= 14 * mm
    c.setFont(f, 20)
    c.drawString(x0, y, f"ODLOČBA št. {o.stevilka}")
    y -= 12 * mm
    c.setFont(f, 10.5)
    for line in [
        f"Vloga:      {o.vloga_id}  ·  čakalni listek št. {s.listek_stevilka}",
        f"Stranka:    {s.stranka.ime}  ({s.stranka.id})",
        f"Naslov:     {s.stranka.naslov}",
        f"Postopek:   {o.postopek}  {o.naziv}",
        f"Datum:      {s.datum_obravnave.strftime('%d.%m.%Y')}",
    ]:
        c.drawString(x0, y, line)
        y -= 7 * mm

    y -= 6 * mm
    c.setFont(f, 12)
    c.drawString(x0, y, "Na podlagi Pravilnika št. 7/2026 in preverjenih prilog se vlogi")
    y -= 8 * mm
    c.setFont(f, 16)
    c.drawString(x0, y, "U G O D I .")
    y -= 12 * mm
    c.setFont(f, 10.5)
    c.drawString(x0, y, "Obrazložitev preverjanja prilog:")
    y -= 6.5 * mm
    c.setFont(f, 9.5)
    for chunk in _wrap(z.preverjanje.obrazlozitev, 95):
        c.drawString(x0, y, chunk)
        y -= 5.5 * mm
    y -= 6 * mm
    c.setFont(f, 10.5)
    c.drawString(x0, y, f"Upravna taksa: {eur(o.taksa_eur)}" + ("  (zaračunana ob izdaji)" if o.taksa_eur else ""))
    y -= 7 * mm
    c.drawString(x0, y, f"Odobril: {z.odobril}" + (f"  ·  {z.opomba}" if z.opomba else ""))

    c.setFont(f, 9)
    c.drawString(x0, 40 * mm, "Odločba je veljavna le z uradnim žigom (Pravilnik 0.4).")
    if o.zig:
        _narisi_zig(c, width - 60 * mm, 62 * mm, s.datum_obravnave.strftime("%d.%m.%Y"))
    else:
        c.setFont(f, 11)
        c.drawString(width - 95 * mm, 60 * mm, "[ žig manjka: čaka na odobritev ]")

    c.setFont(f, 7)
    c.drawString(x0, 15 * mm, "Izmišljen dokument za konferenčno demonstracijo. Ne uporabljajte za resnične postopke.")
    c.showPage()
    c.save()


def _wrap(text: str, n: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def izdaj_odlocbo(z: Zig, idempotent: bool, out_dir: Path | None = None) -> Odlocba:
    """The side effect. Writes a PDF and charges the fee (a ledger line). Non-idempotent by default."""
    ensure_dirs()
    out = (out_dir or OUT_DIR) / "odlocbe"
    out.mkdir(parents=True, exist_ok=True)
    p = postopek(z.preverjanje.sprejeta.vloga.postopek)
    stevilka = stevilka_odlocbe(z.vloga_id, idempotent)
    pdf = out / f"{stevilka}.pdf"
    o = Odlocba(
        stevilka=stevilka,
        vloga_id=z.vloga_id,
        stranka_ime=z.preverjanje.sprejeta.stranka.ime,
        postopek=p.sifra,
        naziv=p.naziv,
        taksa_eur=p.taksa_eur,
        zig=z.odobreno,
        pdf_path=str(pdf),
        izdana=datetime.now().isoformat(timespec="seconds"),
    )
    if idempotent and pdf.exists():
        o.ze_izdana = True
        return o
    # Render to a temp file, charge the fee, then publish the PDF atomically: the final path is the single
    # "issued" marker, so a kill anywhere in between is replayed as a clean re-issue (at-least-once delivery).
    tmp = pdf.with_suffix(".pdf.tmp")
    _narisi_pdf(tmp, o, z)
    with (OUT_DIR / "takse.log").open("a", encoding="utf-8") as ledger:
        ledger.write(f"{o.izdana} | {o.vloga_id} | {o.stranka_ime} | {o.stevilka} | {eur(o.taksa_eur)}\n")
    os.replace(tmp, pdf)
    return o
