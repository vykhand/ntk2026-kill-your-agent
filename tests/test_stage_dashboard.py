"""dashboard.py: pure logic only (deep-link format, header-based iframe check, act5_env.sh parsing).
No emulator, no azd, no network — `preveri_iframe` and `act5_env` are exercised against fakes."""

from __future__ import annotations

import stat
import urllib.error

import pytest

from lipica.stage import dashboard


def test_emulator_deep_link_matches_the_readme_scheme():
    url = dashboard.emulator_deep_link("http://localhost:8082", "VL-2026-0050")
    assert url == "http://localhost:8082/subscriptions/local/schedulers/emulator/taskhubs/default/orchestrations/VL-2026-0050"


def test_dashboard_iframe_embeds_the_url_verbatim():
    html = dashboard.dashboard_iframe("http://localhost:8082/x", height="500px")
    assert '<iframe src="http://localhost:8082/x"' in html
    assert 'height="500px"' in html


class _FakeResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_preveri_iframe_ok_when_no_blocking_headers(monkeypatch):
    monkeypatch.setattr(dashboard.urllib.request, "urlopen", lambda *a, **k: _FakeResponse({"Content-Type": "text/html"}))
    okvir = dashboard.preveri_iframe("http://localhost:8082")
    assert okvir.lahko is True


def test_preveri_iframe_blocked_by_x_frame_options(monkeypatch):
    monkeypatch.setattr(dashboard.urllib.request, "urlopen", lambda *a, **k: _FakeResponse({"X-Frame-Options": "DENY"}))
    okvir = dashboard.preveri_iframe("http://example.invalid")
    assert okvir.lahko is False and "DENY" in okvir.razlog


def test_preveri_iframe_blocked_by_csp_frame_ancestors(monkeypatch):
    monkeypatch.setattr(
        dashboard.urllib.request, "urlopen", lambda *a, **k: _FakeResponse({"Content-Security-Policy": "frame-ancestors 'self'"})
    )
    okvir = dashboard.preveri_iframe("http://example.invalid")
    assert okvir.lahko is False and "frame-ancestors" in okvir.razlog


def test_preveri_iframe_unreachable_is_not_lahko(monkeypatch):
    def _boom(*a, **k):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(dashboard.urllib.request, "urlopen", _boom)
    okvir = dashboard.preveri_iframe("http://localhost:1")
    assert okvir.lahko is False and "URLError" in okvir.razlog


def test_prijazna_napaka_no_login():
    from azure.identity import CredentialUnavailableError

    msg = dashboard.prijazna_napaka(CredentialUnavailableError("Please run 'az login'"))
    assert "az login" in msg and "Traceback" not in msg


def test_prijazna_napaka_wrong_tenant():
    from azure.core.exceptions import ClientAuthenticationError

    msg = dashboard.prijazna_napaka(ClientAuthenticationError("AADSTS50020 ..."))
    assert "tenant" in msg


def test_prijazna_napaka_falls_back_to_type_and_message():
    msg = dashboard.prijazna_napaka(ValueError("boom"))
    assert msg == "ValueError: boom"


def _fake_scripts_dir(tmp_path):
    d = tmp_path / "scripts"
    d.mkdir()
    return d


def test_act5_env_parses_export_lines(tmp_path, monkeypatch):
    script = _fake_scripts_dir(tmp_path) / "act5_env.sh"
    script.write_text("#!/usr/bin/env bash\necho 'export DTS_ENDPOINT=https://example.durabletask.io'\necho 'export DTS_TASKHUB=lipica'\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    env = dashboard.act5_env()
    assert env == {"DTS_ENDPOINT": "https://example.durabletask.io", "DTS_TASKHUB": "lipica"}


def test_act5_env_raises_with_the_scripts_own_message_on_failure(tmp_path, monkeypatch):
    script = _fake_scripts_dir(tmp_path) / "act5_env.sh"
    script.write_text("#!/usr/bin/env bash\necho 'no azd environment yet' >&2\nexit 1\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    with pytest.raises(dashboard.Act5NiPripravljen, match="no azd environment yet"):
        dashboard.act5_env()
