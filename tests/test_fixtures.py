from pathlib import Path

from lipica import fixtures_io, pravilnik
from lipica.domain import PreverjanjePrilog, SprejetaVloga, Zig
from lipica.listek import narisi_listek
from lipica.odlocba import eur, izdaj_odlocbo, stevilka_odlocbe


def test_eur_formatting():
    assert eur(18.9) == "18,90 €" and eur(0) == "brez takse" and eur(3.5) == "3,50 €"


def test_pravilnik_has_15_procedures():
    p = pravilnik.postopki()
    assert len(p) == 15
    assert p["UE-01"].taksa_eur == 18.90
    assert p["UE-04"].taksa_eur == 0.0
    assert p["UE-03"].dvojna_odobritev and p["UE-05"].dvojna_odobritev
    assert not p["UE-01"].dvojna_odobritev
    assert p["UE-02"].najpogosteje_manjka == "potrdilo o označitvi (čip)"
    assert p["UE-01"].priloge[0] == "prejšnja osebna izkaznica"
    assert pravilnik.splosne_dolocbe().startswith("## 0.")


def test_fixture_cross_references():
    for v in fixtures_io.vloge().values():
        fixtures_io.stranka(v.stranka_id)
        pravilnik.postopek(v.postopek)
    assert all(vid in fixtures_io.vloge() for vid in fixtures_io.JUTRANJA_VRSTA)


def _check(vloga_id):
    v = fixtures_io.vloga(vloga_id)
    s = fixtures_io.stranka(v.stranka_id)
    return pravilnik.preveri_po_pravilniku(v, s, fixtures_io.datum_obravnave())


def test_deterministic_checker_matches_scenario():
    assert _check("VL-2026-0047")[0]  # Acts 1-2: complete
    assert _check("VL-2026-0050")[0]  # Acts 1-2 second in queue: complete
    popolna, manjka, _ = _check("VL-2026-0048")  # Act 3 reject path
    assert not popolna and manjka == ["potrdilo o označitvi (čip)"]
    assert _check("VL-2026-0049")[0]  # Act 3 stretch: complete
    assert _check("VL-2026-0052")[0]  # Act 4 B: 12-year-old document passes the 15-year rulebook rule
    popolna, manjka, _ = _check("VL-2026-0054")  # 17-year-old document trips it
    assert not popolna and manjka == ["fotografija"]


def test_document_age():
    """The Act 4 story: 6-year-old (A), 12-year-old (B), 11-year-old (C) documents around the coached 10-year rule."""
    d = fixtures_io.datum_obravnave()
    ages = {sid: fixtures_io.stranka(sid).dokument.starost_let(d) for sid in ("ID-TEST-001", "ID-TEST-004", "ID-TEST-005", "ID-TEST-006", "ID-TEST-007")}
    assert ages == {"ID-TEST-001": 5, "ID-TEST-004": 6, "ID-TEST-005": 12, "ID-TEST-006": 11, "ID-TEST-007": 17}


def test_listek_box_is_rectangular():
    box = narisi_listek(47, 12, "VL-2026-0047", "UE-01", "Podaljšanje osebne izkaznice")
    lines = box.splitlines()
    assert len({len(line) for line in lines}) == 1
    assert "Vaša številka:         47" in box


def test_odlocba_number_switch():
    assert stevilka_odlocbe("VL-2026-0047", idempotent=True) == stevilka_odlocbe("VL-2026-0047", idempotent=True)
    assert stevilka_odlocbe("VL-2026-0047", idempotent=False) != stevilka_odlocbe("VL-2026-0047", idempotent=False)


def test_odlocba_pdf_and_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr("lipica.odlocba.OUT_DIR", tmp_path)
    v = fixtures_io.vloga("VL-2026-0047")
    s = fixtures_io.stranka(v.stranka_id)
    sprejeta = SprejetaVloga(vloga=v, stranka=s, listek_stevilka=47, na_vrsti=12, datum_obravnave=fixtures_io.datum_obravnave())
    prev = PreverjanjePrilog(vloga_id=v.id, popolna=True, manjkajoce=[], obrazlozitev="ok", vir="pravilnik", sprejeta=sprejeta)
    z = Zig(vloga_id=v.id, odobreno=True, odobril="referent", preverjanje=prev)

    first = izdaj_odlocbo(z, idempotent=True, out_dir=tmp_path)
    second = izdaj_odlocbo(z, idempotent=True, out_dir=tmp_path)
    assert Path(first.pdf_path).exists() and first.zig
    assert second.ze_izdana and second.stevilka == first.stevilka
    assert (tmp_path / "takse.log").read_text().count("\n") == 1

    a = izdaj_odlocbo(z, idempotent=False, out_dir=tmp_path)
    b = izdaj_odlocbo(z, idempotent=False, out_dir=tmp_path)
    assert a.stevilka != b.stevilka
    assert (tmp_path / "takse.log").read_text().count("\n") == 3
