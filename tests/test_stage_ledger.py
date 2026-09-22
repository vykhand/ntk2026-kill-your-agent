"""ledger.py: out/takse.log + out/odlocbe/*.pdf as rows, duplicates flagged. Files only, no workflow."""

from lipica.stage import ledger


def _write(out_dir, *lines: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "takse.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_empty_ledger_is_an_empty_list(tmp_path):
    assert ledger.vrstice(tmp_path) == []


def test_single_charge_is_not_flagged(tmp_path):
    _write(tmp_path, "2026-09-16T10:00:00 | VL-2026-0047 | Anica Lipovšek | ODL-2026-AAA111 | 18,90 €")
    (rows := ledger.vrstice(tmp_path))
    assert len(rows) == 1 and rows[0].podvojeno is False
    assert rows[0].vloga_id == "VL-2026-0047" and rows[0].taksa == "18,90 €"


def test_second_charge_for_the_same_application_is_flagged_duplicate(tmp_path):
    _write(
        tmp_path,
        "2026-09-16T10:00:00 | VL-2026-0047 | Anica Lipovšek | ODL-2026-AAA111 | 18,90 €",
        "2026-09-16T10:05:00 | VL-2026-0050 | Filip Novak | ODL-2026-BBB222 | brez takse",
        "2026-09-16T10:10:00 | VL-2026-0047 | Anica Lipovšek | ODL-2026-CCC333 | 18,90 €",
    )
    rows = ledger.vrstice(tmp_path)
    assert [r.podvojeno for r in rows] == [False, False, True]
    assert rows[2].vloga_id == "VL-2026-0047" and rows[2].stevilka == "ODL-2026-CCC333"


def test_malformed_lines_are_skipped_not_raised(tmp_path):
    _write(tmp_path, "not a ledger line", "2026-09-16T10:00:00 | VL-2026-0047 | Anica | ODL-1 | 18,90 €")
    rows = ledger.vrstice(tmp_path)
    assert len(rows) == 1


def test_pdfji_lists_odlocbe_oldest_first(tmp_path):
    d = tmp_path / "odlocbe"
    d.mkdir(parents=True)
    (d / "ODL-2026-B.pdf").write_bytes(b"b")
    (d / "ODL-2026-A.pdf").write_bytes(b"a")
    import os
    import time

    os.utime(d / "ODL-2026-B.pdf", (time.time() - 10, time.time() - 10))
    paths = ledger.pdfji(tmp_path)
    assert [p.name for p in paths] == ["ODL-2026-B.pdf", "ODL-2026-A.pdf"]


def test_pdfji_empty_when_no_odlocbe_dir(tmp_path):
    assert ledger.pdfji(tmp_path) == []
