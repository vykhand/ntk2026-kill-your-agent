"""The queue ticket: an ASCII box printed at intake."""

from __future__ import annotations


def narisi_listek(stevilka: int, na_vrsti: int, vloga_id: str, postopek: str, naziv: str) -> str:
    width = 40
    lines = [
        "UPRAVNA ENOTA ZGORNJA LIPICA",
        "ČAKALNI LISTEK",
        "",
        f"Vaša številka:       {stevilka:>4}",
        f"Trenutno na vrsti:   {na_vrsti:>4}",
        "",
        f"Vloga:     {vloga_id}",
        f"Postopek:  {postopek}",
        naziv[: width - 4],
        "",
        "Malica: 10.30–11.00",
    ]
    top = "┌" + "─" * (width - 2) + "┐"
    bottom = "└" + "─" * (width - 2) + "┘"
    body = [f"│ {line.ljust(width - 4)} │" for line in lines]
    return "\n".join([top, *body, bottom])
