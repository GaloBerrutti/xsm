#!/usr/bin/env python3
"""Recalcula las semanas cerradas con precios publicos de Bybit y las compara con datos/cierres/.

    python verificar.py              todas
    python verificar.py 2026-10-19   una

Solo biblioteca estandar. Reglas de la cuenta: README.md.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.bybit.com"
COMISION = 0.001
MINUTO, HORA = 60_000, 3_600_000
DATOS = Path(__file__).resolve().parent / "datos"
TOL = 1e-9


def ms(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()) * 1000


def texto(t: int) -> str:
    return datetime.fromtimestamp(t / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pedir(ruta: str, params: dict):
    url, err = API + ruta + "?" + urllib.parse.urlencode(params), None
    for i in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verificar.py)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.load(r)
            if d.get("retCode") == 0:
                return d["result"]
            err = d.get("retMsg")
        except Exception as e:
            err = e
        time.sleep(1 + 2 * i)
    raise RuntimeError(f"{ruta} {params}: {err}")


def velas(par: str, iv: str, desde: int, hasta: int) -> list:
    """(inicio, apertura, maximo, minimo) con desde <= inicio < hasta, en orden."""
    out, fin = {}, hasta - 1
    while fin >= desde:
        lote = pedir("/v5/market/kline", {"category": "linear", "symbol": par, "interval": iv,
                                          "start": desde, "end": fin, "limit": 1000})["list"]
        for x in lote:
            t = int(x[0])
            if desde <= t < hasta:
                out[t] = (t, float(x[1]), float(x[2]), float(x[3]))
        if len(lote) < 1000:
            break
        fin = min(int(x[0]) for x in lote) - 1
    return [out[t] for t in sorted(out)]


def precio_en(par: str, t: int) -> float:
    v = velas(par, "1", t, t + MINUTO)
    if not v:
        raise RuntimeError(f"{par}: sin vela en {texto(t)}")
    return v[0][1]


def toca(v, lado: str, lim: float) -> bool:
    return v[3] <= lim if lado == "compra" else v[2] >= lim


def llenado(par: str, lado: str, lim: float, desde: int, hasta: int):
    """Primer minuto de [desde, hasta) que llega al limite, o None."""
    if hasta <= desde:
        return None
    for h in velas(par, "60", desde - desde % HORA, hasta):
        if h[0] >= desde and h[0] + HORA <= hasta and not toca(h, lado, lim):
            continue
        for m in velas(par, "1", max(h[0], desde), min(h[0] + HORA, hasta)):
            if toca(m, lado, lim):
                return m[0]
    return None


def financiacion(par: str, desde: int, hasta: int) -> float:
    tasas, fin = {}, hasta
    while True:
        lote = pedir("/v5/market/funding/history", {"category": "linear", "symbol": par,
                                                    "startTime": desde, "endTime": fin, "limit": 200})["list"]
        for x in lote:
            ts = int(x["fundingRateTimestamp"])
            if desde < ts < hasta:
                tasas[ts] = float(x["fundingRate"])
        if len(lote) < 200:
            break
        fin = min(int(x["fundingRateTimestamp"]) for x in lote) - 1
        if fin <= desde:
            break
    tot = 0.0
    for ts in sorted(tasas):
        tot += tasas[ts]
    return tot


def posicion(p: dict, ini: int, corte: int, fin: int, sigue: bool) -> dict:
    x = p["peso"] if p["lado"] == "compra" else -p["peso"]
    f = {"par": p["par"], "lado": p["lado"], "peso": p["peso"], "tipo": p["tipo"]}
    if p["tipo"] == "sigue":
        ent, desde, com = precio_en(p["par"], ini), ini, 0.0
        f["estado"] = "sigue"
    elif p["tipo"] == "orden":
        m = llenado(p["par"], p["lado"], p["limite"], ini, corte)
        if m is None:
            f.update(estado="no_llego", resultado=0.0)
            return f
        ent, desde, com = p["limite"], m, COMISION
        f.update(estado="llenada", llenada_utc=texto(m))
    else:
        raise ValueError(p["tipo"])
    sal = precio_en(p["par"], fin)
    fu = financiacion(p["par"], desde, fin)
    sc = 0.0 if sigue else COMISION
    r = x * (sal / ent - 1) - p["peso"] * (com + sc) - x * fu
    f.update(entrada=ent, salida=sal, sale=not sigue, financiacion=fu, resultado=r)
    return f


def cerrar(sem: dict, sig: dict, c0: float) -> dict:
    ini, corte, fin = ms(sem["inicio_utc"]), ms(sig["corte_utc"]), ms(sig["inicio_utc"])
    siguen = {(p["par"], p["lado"]) for p in sig["posiciones"] if p["tipo"] == "sigue"}
    fs = [posicion(p, ini, corte, fin, (p["par"], p["lado"]) in siguen) for p in sem["posiciones"]]
    tot = 0.0
    for f in fs:
        tot += f["resultado"]
    return {"semana": sem["semana"], "inicio_utc": sem["inicio_utc"], "corte_utc": sig["corte_utc"],
            "fin_utc": sig["inicio_utc"], "posiciones": fs, "resultado": tot,
            "cuenta_inicio": c0, "cuenta_fin": c0 * (1 + tot)}


def coherencia(ci: dict, sig: dict) -> list:
    abiertas = {(f["par"], f["lado"]) for f in ci["posiciones"] if f["estado"] in ("llenada", "sigue")}
    out = []
    for p in sig["posiciones"]:
        k = (p["par"], p["lado"])
        if p["tipo"] == "sigue" and k not in abiertas:
            out.append(f"{p['par']}: 'sigue' sin posicion abierta")
        if p["tipo"] == "orden" and k in abiertas:
            out.append(f"{p['par']}: abierta del mismo lado y con orden nueva")
    return out


def leer(carpeta: str, s: str) -> dict:
    return json.loads((DATOS / carpeta / f"{s}.json").read_text(encoding="utf-8"))


def diferencias(a: dict, b: dict) -> list:
    out = []
    if len(a["posiciones"]) != len(b["posiciones"]):
        out.append("distinta cantidad de posiciones")
    for x, y in zip(a["posiciones"], b["posiciones"]):
        if x.get("estado") != y.get("estado") or x.get("llenada_utc") != y.get("llenada_utc"):
            out.append(f"{x['par']}: {x.get('estado')} {x.get('llenada_utc', '')} / {y.get('estado')} {y.get('llenada_utc', '')}")
        elif abs(x["resultado"] - y["resultado"]) > TOL:
            out.append(f"{x['par']}: {x['resultado']:+.6%} / {y['resultado']:+.6%}")
    if abs(a["resultado"] - b["resultado"]) > TOL:
        out.append(f"semana: {a['resultado']:+.6%} / {b['resultado']:+.6%}")
    return out


def main(argv: list) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    semanas = json.loads((DATOS / "indice.json").read_text(encoding="utf-8"))["semanas"]
    pedidas = set(argv) or set(semanas)
    c0, malas, vistas = 1.0, 0, 0
    for i, s in enumerate(semanas):
        if i + 1 == len(semanas) or not (DATOS / "cierres" / f"{s}.json").exists():
            print(f"{s}  en curso")
            continue
        pub = leer("cierres", s)
        if s not in pedidas:
            c0 = pub["cuenta_fin"]
            continue
        sig = leer("ordenes", semanas[i + 1])
        calc = cerrar(leer("ordenes", s), sig, c0)
        dif = coherencia(calc, sig) + diferencias(pub, calc)
        if abs(pub["cuenta_inicio"] - c0) > TOL:
            dif.append("cuenta inicial distinta de la final de la semana anterior")
        vistas += 1
        if dif:
            malas += 1
            print(f"{s}  no coincide")
            for d in dif:
                print("    " + d)
        else:
            print(f"{s}  coincide  {calc['resultado']:+.2%}")
        c0 = calc["cuenta_fin"]
    print(f"\n{vistas} revisadas, {malas} con diferencias")
    return 1 if malas else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
