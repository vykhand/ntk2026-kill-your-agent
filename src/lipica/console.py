"""Projector-friendly terminal output. One colour per executor, big and boring on purpose."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

console = Console(highlight=False)

BARVE = {
    "SprejmiVlogo": "cyan",
    "PreveriPriloge": "yellow",
    "ČakanjeNaŽig": "magenta",
    "IzdajOdločbo": "green",
}


def korak(executor: str, msg: str) -> None:
    barva = BARVE.get(executor, "white")
    console.print(f"[bold {barva}]▶ {executor:<15}[/] {msg}")


def opozorilo(msg: str) -> None:
    console.print(f"[bold red]{msg}[/]")


def naslov(title: str, subtitle: str = "") -> None:
    console.print(Panel.fit(f"[bold]{title}[/]" + (f"\n{subtitle}" if subtitle else ""), border_style="blue"))


def blok(text: str, barva: str = "cyan") -> None:
    console.print(f"[{barva}]{text}[/]")
