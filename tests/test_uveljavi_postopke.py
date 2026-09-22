"""Act 4: the code enforces the consequence of every learned procedure the model judged to hold."""

from lipica.llm import OcenaPostopka, OdgovorReferentaSpomin, uveljavi_postopke

PRILOGE = ["prejšnja osebna izkaznica", "potrdilo o plačilu takse"]


def _odgovor(popolna, manjka, ocene):
    return OdgovorReferentaSpomin(postopki_urada=ocene, popolna=popolna, manjkajoce=manjka, obrazlozitev="x")


def test_model_contradiction_is_overruled():
    """Cycle 1 of the live acceptance: evaluation says the photo is demanded, popolna said true."""
    o = _odgovor(True, [], [OcenaPostopka(postopek="p", pogoj="starejša od deset let", podatek="12 let", velja=True, zahtevana_priloga="fotografija")])
    popolna, manjka, lines = uveljavi_postopke(o, PRILOGE)
    assert not popolna and manjka == ["fotografija"] and "zahtevam: fotografija" in lines[0]


def test_condition_not_met_keeps_the_model_verdict():
    o = _odgovor(True, [], [OcenaPostopka(postopek="p", pogoj="starejša od deset let", podatek="6 let", velja=False, zahtevana_priloga="fotografija")])
    popolna, manjka, lines = uveljavi_postopke(o, PRILOGE)
    assert popolna and manjka == [] and "pogoj ne velja" in lines[0]


def test_already_attached_and_warning_only():
    o = _odgovor(True, [], [
        OcenaPostopka(postopek="p", pogoj="vedno", podatek="-", velja=True, zahtevana_priloga="potrdilo o plačilu takse"),
        OcenaPostopka(postopek="q", pogoj="vedno", podatek="-", velja=True, opozorilo="pozabljena priloga"),
    ])
    popolna, manjka, lines = uveljavi_postopke(o, PRILOGE)
    assert popolna and manjka == [] and "je priložena" in lines[0] and "opozorilo:" in lines[1]


def test_no_duplicates_when_model_already_listed_it():
    o = _odgovor(False, ["fotografija"], [OcenaPostopka(postopek="p", pogoj="c", podatek="d", velja=True, zahtevana_priloga="fotografija")])
    assert uveljavi_postopke(o, PRILOGE)[1] == ["fotografija"]
