"""Act 3: the phone. `uv run zig`  ->  http://<laptop-ip>:8000 over the hotspot.

Two big buttons per application parked in ČakanjeNaŽig:
  ✅ Odobri in žigosaj           -> the žig lands on the odločba
  ❌ Zavrni — manjka priloga     -> resume with payload: the workflow loops back to PreveriPriloge
"""

from __future__ import annotations

import html
import os

import uvicorn
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from lipica import pravilnik
from lipica.hosts.zig_api import Zahteva, cakajoce, lan_ip, make_client, odgovori

app = FastAPI(title="Upravna enota Zgornja Lipica · Žig")

CSS = """
body{font-family:-apple-system,Helvetica,Arial,sans-serif;background:#f4f1ea;margin:0;padding:16px;color:#222}
h1{font-size:22px;margin:0 0 4px} .sub{color:#666;font-size:14px;margin-bottom:16px}
.card{background:#fff;border-radius:16px;padding:18px;margin-bottom:18px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.id{font-family:ui-monospace,Menlo,monospace;font-size:15px;color:#555}
.who{font-size:24px;font-weight:700;margin:6px 0} .what{font-size:17px;margin-bottom:8px}
.ok{color:#1a7f37;font-weight:600} .bad{color:#b42318;font-weight:600}
.obr{font-size:15px;color:#444;background:#faf8f2;border-left:4px solid #d8cfb8;padding:8px 10px;margin:8px 0 14px}
button{width:100%;border:0;border-radius:14px;font-size:26px;font-weight:700;padding:26px 12px;margin-top:12px;color:#fff}
.odobri{background:#1a7f37} .zavrni{background:#b42318}
input[type=text]{width:100%;box-sizing:border-box;font-size:17px;padding:12px;border:1px solid #ccc;border-radius:10px;margin-top:6px}
.empty{font-size:20px;color:#666;text-align:center;padding:60px 10px}
"""


def _card(z: Zahteva) -> str:
    d = z.data
    manjka = d.get("manjkajoce") or []
    stanje = '<span class="ok">popolna</span>' if d.get("popolna") else f'<span class="bad">nepopolna · manjka: {html.escape(", ".join(manjka))}</span>'
    sifra = str(d.get("postopek", "")).split(" ")[0]
    try:
        privzeto = manjka[0] if manjka else pravilnik.postopek(sifra).najpogosteje_manjka
    except KeyError:
        privzeto = ""
    podpisnik = f' · <b>podpis: {html.escape(str(d["podpisnik"]))}</b>' if d.get("podpisnik") else ""
    return f"""
<div class="card">
  <div class="id">{html.escape(z.instance_id)} · listek št. {html.escape(str(d.get('listek', '?')))}{podpisnik}</div>
  <div class="who">{html.escape(str(d.get('stranka', '')))}</div>
  <div class="what">{html.escape(str(d.get('postopek', '')))}</div>
  <div>Preverjanje prilog ({html.escape(str(d.get('vir', '')))}): {stanje}</div>
  <div class="obr">{html.escape(str(d.get('obrazlozitev', '')))}</div>
  <form method="post" action="/odgovor">
    <input type="hidden" name="instance_id" value="{html.escape(z.instance_id)}">
    <input type="hidden" name="request_id" value="{html.escape(z.request_id)}">
    <button class="odobri" name="odobreno" value="1">✅ Odobri in žigosaj</button>
    <label>Manjkajoča priloga (za zavrnitev):
      <input type="text" name="dopolnitev" value="{html.escape(privzeto)}"></label>
    <button class="zavrni" name="odobreno" value="0">❌ Zavrni — manjka priloga</button>
  </form>
</div>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    zahteve = cakajoce(make_client())
    body = "".join(_card(z) for z in zahteve) or '<div class="empty">Trenutno nobena vloga ne čaka na žig.<br>Stran se osveži sama.</div>'
    return f"""<!doctype html><html lang="sl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="3">
<title>Žig · UE Zgornja Lipica</title><style>{CSS}</style></head><body>
<h1>Upravna enota Zgornja Lipica</h1><div class="sub">Okence za žig · referent</div>{body}</body></html>"""


@app.post("/odgovor")
def odgovor(instance_id: str = Form(), request_id: str = Form(), odobreno: str = Form(), dopolnitev: str = Form("")) -> RedirectResponse:
    z = Zahteva(instance_id=instance_id, request_id=request_id, data={})
    odgovori(
        make_client(),
        z,
        odobreno=odobreno == "1",
        odobril="telefon",
        dopolnitev=[dopolnitev.strip()] if dopolnitev.strip() else [],
    )
    return RedirectResponse("/", status_code=303)


def main() -> None:
    port = int(os.environ.get("ZIG_PORT", "8000"))
    print(f"Telefon: http://{lan_ip()}:{port}   (isti hotspot kot prenosnik)")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
