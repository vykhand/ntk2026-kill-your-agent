"""Notebook 05 helpers: parsing `uv run act4 list` output for the delete dropdown.

Everything else is shared (`stage.process` starts every `act4` subcommand as a real subprocess,
`stage.terminal` renders its output); this module only knows the one thing specific to Act 4's CLI: the
shape of `spomin.izpisi_zapise`'s two-line-per-item listing (see `lipica.hosts.act4.cmd_list` and
`cmd_coach`, which both print through it).
"""

from __future__ import annotations

import re

from rich.text import Text

# `izpisi_zapise` prints, per memory item:
#   "  <memory_id>  <kind>  <timestamp>"
#   "     <content>"
# two leading spaces then two-space-separated columns; the content line is indented five spaces, and the
# empty-store line ("  (spomin je prazen)") has single spaces between its words — neither ever matches.
_ZAPIS = re.compile(r"^ {2}(\S+) {2}(\S+) {2}", re.MULTILINE)


def memory_ids(log_text: str) -> list[tuple[str, str]]:
    """`(memory_id, kind)` pairs, oldest-printed-first, from a worker log — ANSI (the real subprocess
    output; `FORCE_COLOR=1` per `stage.process.start`) or already-plain text alike."""
    if not log_text:
        return []
    plain = Text.from_ansi(log_text).plain
    return [(m.group(1), m.group(2)) for m in _ZAPIS.finditer(plain)]
