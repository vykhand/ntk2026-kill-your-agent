"""ucenje.py: memory ids parsed out of `act4 list`'s own rendering. No emulator, no model, no cloud."""

import io

from rich.console import Console

from lipica.stage import ucenje


def _render_like_izpisi_zapise(*rows: tuple[str, str, str, str]) -> str:
    """Reproduce `lipica.spomin.izpisi_zapise`'s exact `console.print` calls (real ANSI, real ▶
    markup), so the parser is proven against the renderer it actually has to survive, not a guess."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, color_system="standard", width=120)
    console.rule("Spomin · obseg 'referent'")
    for memory_id, kind, timestamp, content in rows:
        console.print(f"  [dim]{memory_id}[/]  [magenta]{kind}[/]  {timestamp}")
        console.print(f"     {content}")
    return buf.getvalue()


def test_parses_ids_and_kinds_out_of_real_ansi_rendered_output():
    text = _render_like_izpisi_zapise(
        ("mem_abc123", "procedural", "16.09. 10:00", "Za vloge, starejše od deset let, ..."),
        ("mem_def456", "user_profile", "16.09. 10:05", "Stranka želi obvestila po e-pošti."),
    )
    assert "\x1b[" in text  # this is really ANSI, not a plain string
    assert ucenje.memory_ids(text) == [("mem_abc123", "procedural"), ("mem_def456", "user_profile")]


def test_parses_plain_text_the_same_way():
    text = "  mem_abc123  procedural  16.09. 10:00\n     content here\n"
    assert ucenje.memory_ids(text) == [("mem_abc123", "procedural")]


def test_empty_store_line_is_not_mistaken_for_an_item():
    text = _render_like_izpisi_zapise()  # no rows: izpisi_zapise prints "  (spomin je prazen)"
    text += "  (spomin je prazen)\n"
    assert ucenje.memory_ids(text) == []


def test_empty_log_is_an_empty_list():
    assert ucenje.memory_ids("") == []


def test_content_lines_are_not_mistaken_for_item_headers():
    # a content line indented 5 spaces, starting with a token that could look like an id
    text = "     mem_should_not_match here\n"
    assert ucenje.memory_ids(text) == []
