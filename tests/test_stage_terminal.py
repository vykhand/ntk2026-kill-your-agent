"""terminal.py: ANSI log text -> HTML. No process, no rich console attached to a real terminal."""

from lipica.stage import terminal


def test_ansi_colour_becomes_an_inline_style_span():
    html = terminal.ansi_to_html("\x1b[32mOK\x1b[0m")
    assert "<span" in html and "color: #008000" in html
    assert "OK" in html


def test_plain_text_survives_without_ansi():
    html = terminal.ansi_to_html("plain log line")
    assert "plain log line" in html


def test_empty_log_still_renders_a_placeholder():
    html = terminal.ansi_to_html("")
    assert "še ni izpisa" in html


def test_output_is_a_scrollable_dark_panel_auto_scrolled_to_bottom():
    html = terminal.ansi_to_html("x", height="300px")
    assert "height:300px" in html
    assert "overflow-y:auto" in html
    assert "background:#1A1A1A" in html
    assert "scrollTop=e.scrollHeight" in html  # auto-scroll script


def test_html_is_escaped_not_executable_markup():
    html = terminal.ansi_to_html("<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
