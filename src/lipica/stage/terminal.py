"""ANSI worker log -> a dark, monospace HTML panel, auto-scrolled to the bottom.

rich already knows how to turn a child process's ANSI escapes (colour, bold — the workers are the
same `console.print`-driven output the terminal fallback shows) into styled HTML; this just wraps
that in a fixed-height, dark, projector-sized panel a notebook cell can hand to `mo.Html`.
"""

from __future__ import annotations

import io

from rich.console import Console
from rich.text import Text

BACKGROUND = "#1A1A1A"
FOREGROUND = "#F2F2F2"

# A bare <pre><code> fragment (no <html>/<head>/<style> wrapper) so it drops straight into the
# panel below; inline_styles=True means no separate stylesheet is needed.
_CODE_FORMAT = (
    '<pre style="margin:0;white-space:pre-wrap;word-break:break-word;'
    'font-family:Menlo,Consolas,monospace;font-size:15px;line-height:1.35;">'
    '<code style="font-family:inherit">{code}</code></pre>'
)


def ansi_to_html(text: str, *, height: str = "420px", width: int = 110) -> str:
    """Render a worker's raw stdout+stderr (as `Delavec.tail()` returns it) as a scrollable panel."""
    # `file=` a throwaway sink: without it, Console defaults to the real stdout, so every render
    # (a live panel re-renders every second) would also spam the marimo server's own terminal with
    # raw ANSI — `record=True` alone already gives `export_html()` everything it needs below.
    console = Console(record=True, width=width, color_system="truecolor", file=io.StringIO())
    console.print(Text.from_ansi(text) if text else Text("(še ni izpisa)", style="dim"))
    body = console.export_html(inline_styles=True, code_format=_CODE_FORMAT)
    # A unique-enough id per render so several panels on one page (or across a refresh) don't share
    # a scroll target; the content itself is the only thing that needs to change between renders.
    uid = f"term-{abs(hash((text, height))) % 10_000_000}"
    return (
        f'<div id="{uid}" style="height:{height};overflow-y:auto;background:{BACKGROUND};'
        f'color:{FOREGROUND};border-radius:8px;padding:10px 12px;box-sizing:border-box;">'
        f"{body}</div>"
        f'<script>(function(){{var e=document.getElementById("{uid}");'
        f"if(e)e.scrollTop=e.scrollHeight;}})();</script>"
    )
