"""cakanje.py: the QR code and the pending-request table shape. No emulator, no model."""

from lipica.hosts.zig_api import Zahteva
from lipica.stage import cakanje


def _zahteva(request_id: str = "r1", *, podpisnik: str | None = None, popolna: bool = True) -> Zahteva:
    data = {
        "vloga_id": "VL-2026-0048",
        "listek": 51,
        "stranka": "Bojan Krivec",
        "postopek": "UE-02 Registracija psa",
        "popolna": popolna,
        "manjkajoce": [] if popolna else ["potrdilo o označitvi (čip)"],
        "podpisnik": podpisnik,
    }
    return Zahteva(instance_id="VL-2026-0048", request_id=request_id, data=data)


def test_qr_png_is_a_real_png():
    png = cakanje.qr_png("http://192.168.1.5:8000")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_vrstica_flattens_the_request_for_a_table_row():
    row = cakanje.vrstica(_zahteva())
    assert row["vloga"] == "VL-2026-0048"
    assert row["stranka"] == "Bojan Krivec"
    assert row["preverjanje"] == "popolna"
    assert row["request_id"] == "r1"


def test_vrstica_flags_an_incomplete_application():
    row = cakanje.vrstica(_zahteva(popolna=False))
    assert row["preverjanje"] == "nepopolna: potrdilo o označitvi (čip)"


def test_vrstica_shows_the_signer_for_a_dual_approval_request():
    row = cakanje.vrstica(_zahteva(podpisnik="vodja oddelka"))
    assert row["podpisnik"] == "vodja oddelka"


def test_tabela_is_one_row_per_request_in_order():
    zahteve = [_zahteva("r1"), _zahteva("r2", podpisnik="vodja oddelka")]
    rows = cakanje.tabela(zahteve)
    assert [r["request_id"] for r in rows] == ["r1", "r2"]


def test_najdi_returns_the_matching_request():
    zahteve = [_zahteva("r1"), _zahteva("r2")]
    assert cakanje.najdi(zahteve, "r2") is zahteve[1]


def test_najdi_is_none_once_the_request_is_gone():
    assert cakanje.najdi([_zahteva("r1")], "answered-elsewhere") is None


def test_telefon_tece_sees_a_listening_port_and_not_a_closed_one():
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        assert cakanje.telefon_tece(port)
    assert not cakanje.telefon_tece(port)  # closed now: nothing answers
