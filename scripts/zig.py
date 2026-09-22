"""The stamp from the terminal, for rehearsals without a phone.

    uv run python scripts/zig.py                 # list applications waiting for the stamp
    uv run python scripts/zig.py odobri          # approve the first one waiting
    uv run python scripts/zig.py zavrni [priloga] # reject it; the citizen then brings <priloga>
    uv run python scripts/zig.py odobri vodja    # dual approval: pick the signer (referent | vodja)

curl alternative for the same thing is in README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lipica.hosts.zig_api import cakajoce, make_client, odgovori  # noqa: E402


def main() -> int:
    client = make_client("zig-cli")
    zahteve = cakajoce(client)
    if not zahteve:
        print("Nobena vloga ne čaka na žig.")
        return 1
    for z in zahteve:
        d = z.data
        stanje = "popolna" if d.get("popolna") else "nepopolna: " + ", ".join(d.get("manjkajoce") or [])
        kdo = f"  podpis: {d['podpisnik']}" if d.get("podpisnik") else ""
        print(f"{z.instance_id}  listek {d.get('listek')}  {d.get('stranka')}  {d.get('postopek')}  [{stanje}]{kdo}")
    if len(sys.argv) < 2:
        return 0
    ukaz, args = sys.argv[1], sys.argv[2:]
    z = zahteve[0]
    if args and args[0] in ("referent", "vodja"):  # pick a signer of a dual approval
        izbrani = [x for x in zahteve if str(x.data.get("podpisnik", "")).startswith(args[0])]
        if not izbrani:
            print(f"Ni zahteve za podpisnika '{args[0]}'.")
            return 1
        z, args = izbrani[0], args[1:]
    kdo = f" ({z.data['podpisnik']})" if z.data.get("podpisnik") else ""
    if ukaz == "odobri":
        odgovori(client, z, odobreno=True, odobril="terminal")
        print(f"✅ {z.instance_id}{kdo}: odobreno")
    elif ukaz == "zavrni":
        dopolnitev = [" ".join(args)] if args else []
        odgovori(client, z, odobreno=False, odobril="terminal", dopolnitev=dopolnitev)
        print(f"❌ {z.instance_id}{kdo}: zavrnjeno" + (f", stranka prinese: {dopolnitev[0]}" if dopolnitev else ""))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
