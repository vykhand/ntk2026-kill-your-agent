"""Generate the fillable form PDFs referenced by fixtures/pravilnik.md §2.

Usage:  uv run python scripts/gen_obrazci.py
Output: fixtures/obrazci/UE-0x_*.pdf  (AcroForm text fields + checkboxes)

Everything here is fictional: the office, the procedures, the fields.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "obrazci"

# DejaVu ships with most systems and covers č/š/ž; fall back to Helvetica (no diacritics) if absent.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


def register_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont("Obrazec", candidate))
            return "Obrazec"
    return "Helvetica"


FORMS: list[dict] = [
    {
        "šifra": "UE-01",
        "naziv": "Vloga za podaljšanje osebne izkaznice",
        "taksa": "18,90 €",
        "polja": ["Ime in priimek", "Naslov", "Številka prejšnje izkaznice", "Datum izdaje prejšnje izkaznice"],
        "priloge": [
            "prejšnja osebna izkaznica",
            "potrdilo o plačilu takse",
            "fotografija (le če je prejšnja izkaznica starejša od 15 let)",
        ],
    },
    {
        "šifra": "UE-02",
        "naziv": "Vloga za registracijo psa",
        "taksa": "12,00 €",
        "polja": ["Ime in priimek lastnika", "Naslov", "Ime psa", "Pasma / opis", "Številka čipa"],
        "priloge": [
            "potrdilo o cepljenju proti steklini",
            "potrdilo o označitvi (čip)",
            "dokazilo o lastništvu",
        ],
    },
    {
        "šifra": "UE-03",
        "naziv": "Vloga za dovoljenje za postavitev čebelnjaka",
        "taksa": "25,00 €",
        "polja": ["Ime in priimek", "Naslov", "Parcelna številka", "Število panjev", "Št. vpisa v register čebelarjev"],
        "priloge": [
            "skica lokacije z razdaljami do sosednjih parcel",
            "pisno soglasje lastnikov parcel v radiju 30 m",
            "potrdilo o vpisu v register čebelarjev",
        ],
    },
    {
        "šifra": "UE-05",
        "naziv": "Vloga za dovoljenje za javno prireditev",
        "taksa": "40,00 €",
        "polja": ["Organizator", "Naslov", "Naziv prireditve", "Datum in ura", "Pričakovano število obiskovalcev"],
        "priloge": [
            "program prireditve",
            "načrt varovanja",
            "pisno soglasje lastnika zemljišča",
            "potrdilo o plačilu takse",
        ],
    },
]


def draw_form(spec: dict, font: str) -> Path:
    slug = spec["naziv"].lower().replace(" ", "-")
    for a, b in (("č", "c"), ("š", "s"), ("ž", "z")):
        slug = slug.replace(a, b)
    path = OUT / f"{spec['šifra']}_{slug}.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"{spec['šifra']} {spec['naziv']} (izmišljen obrazec)")
    width, height = A4
    x0, y = 20 * mm, height - 25 * mm

    c.setFont(font, 9)
    c.drawString(x0, y, "UPRAVNA ENOTA ZGORNJA LIPICA (izmišljena)  ·  Obrazec " + spec["šifra"])
    y -= 12 * mm
    c.setFont(font, 16)
    c.drawString(x0, y, spec["naziv"])
    y -= 8 * mm
    c.setFont(font, 9)
    c.drawString(x0, y, f"Upravna taksa: {spec['taksa']}   ·   Pravilnik št. 7/2026, postopek {spec['šifra']}")
    y -= 14 * mm

    form = c.acroForm
    c.setFont(font, 10)
    for i, label in enumerate(spec["polja"]):
        c.drawString(x0, y, label + ":")
        form.textfield(
            name=f"polje_{i}", x=x0 + 65 * mm, y=y - 3 * mm, width=100 * mm, height=8 * mm,
            borderWidth=0.5, forceBorder=True, fontSize=10,
        )
        y -= 13 * mm

    y -= 4 * mm
    c.setFont(font, 11)
    c.drawString(x0, y, "Priložene priloge (označite):")
    y -= 9 * mm
    c.setFont(font, 10)
    for i, priloga in enumerate(spec["priloge"]):
        form.checkbox(name=f"priloga_{i}", x=x0, y=y - 2 * mm, size=5 * mm, borderWidth=0.5)
        c.drawString(x0 + 8 * mm, y, priloga)
        y -= 9 * mm

    y -= 10 * mm
    c.drawString(x0, y, "Datum:")
    form.textfield(name="datum", x=x0 + 20 * mm, y=y - 3 * mm, width=40 * mm, height=8 * mm, borderWidth=0.5, forceBorder=True)
    c.drawString(x0 + 90 * mm, y, "Podpis stranke:")
    form.textfield(name="podpis", x=x0 + 125 * mm, y=y - 3 * mm, width=50 * mm, height=8 * mm, borderWidth=0.5, forceBorder=True)

    c.setFont(font, 7)
    c.drawString(x0, 15 * mm, "Izmišljen obrazec za konferenčno demonstracijo. Ne uporabljajte za resnične postopke.")
    c.showPage()
    c.save()
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    font = register_font()
    for spec in FORMS:
        print("written", draw_form(spec, font).relative_to(ROOT))


if __name__ == "__main__":
    main()
