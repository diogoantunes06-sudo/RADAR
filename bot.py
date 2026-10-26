#!/usr/bin/env python3
"""
Robo do Radar: atualiza cotacoes e indicadores da carteira.

Le:   ativos.json  (a lista do que acompanhar)
      analise.json (preco-alvo, LPA, VPA e valor patrimonial, que mudam pouco)
      config.json  (premissas dos calculos)
Grava: dados.json  (o site le este arquivo)

Fontes: Yahoo Finance (cotacao, historico de 1 ano e proventos) e Banco Central (Selic).
Reserva opcional: brapi.dev, se houver o segredo BRAPI_TOKEN.
So usa a biblioteca padrao do Python.
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

PASTA = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (radar-carteira)", "Accept": "application/json"}
BRT = timezone(timedelta(hours=-3))


def ler(nome, padrao=None):
    try:
        with open(os.path.join(PASTA, nome), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def gravar(nome, dados):
    with open(os.path.join(PASTA, nome), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")


def baixar(url, tentativas=3):
    erro = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            erro = e
            time.sleep(2 * (i + 1))
    raise erro


# ---------------------------------------------------------------- fontes
def yahoo(ticker):
    """Cotacao atual, fechamento anterior, serie diaria de 1 ano e proventos de 1 ano."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}.SA"
           "?range=1y&interval=1d&events=div")
    r = baixar(url)["chart"]["result"][0]
    meta = r["meta"]
    fech = [c for c in r["indicators"]["quote"][0].get("close", []) if c is not None]
    divs = [{"data": datetime.fromtimestamp(d["date"], timezone.utc).strftime("%Y-%m-%d"), "valor": d["amount"]}
            for d in (r.get("events", {}).get("dividends", {}) or {}).values()]
    preco = meta.get("regularMarketPrice") or (fech[-1] if fech else None)
    # se o pregao de hoje ja esta na serie (ultimo valor = preco atual), o fechamento anterior e o penultimo
    if len(fech) >= 2 and abs(fech[-1] - preco) < 1e-6:
        anterior = fech[-2]
    else:
        anterior = fech[-1] if fech else None
    return {"preco": preco, "anterior": anterior, "min52": min(fech) if fech else None,
            "max52": max(fech) if fech else None, "proventos": sorted(divs, key=lambda d: d["data"]),
            "nome_longo": meta.get("longName") or meta.get("shortName"), "fonte": "Yahoo Finance"}


def brapi(ticker, token):
    url = f"https://brapi.dev/api/quote/{ticker}?range=1y&interval=1d&dividends=true&token={token}"
    r = baixar(url)["results"][0]
    fech = [h["close"] for h in r.get("historicalDataPrice", []) if h.get("close") is not None]
    divs = [{"data": d["paymentDate"][:10], "valor": d["rate"]}
            for d in (r.get("dividendsData", {}) or {}).get("cashDividends", []) if d.get("paymentDate")]
    return {"preco": r["regularMarketPrice"], "anterior": r.get("regularMarketPreviousClose"),
            "min52": min(fech) if fech else r.get("fiftyTwoWeekLow"), "max52": max(fech) if fech else r.get("fiftyTwoWeekHigh"),
            "proventos": sorted(divs, key=lambda d: d["data"]), "nome_longo": r.get("longName"), "fonte": "brapi.dev"}


def cotacao(ticker):
    try:
        return yahoo(ticker)
    except Exception as e:
        print(f"{ticker}: Yahoo falhou ({e})")
    token = os.environ.get("BRAPI_TOKEN")
    if token:
        try:
            return brapi(ticker, token)
        except Exception as e:
            print(f"{ticker}: brapi falhou ({e})")
    return None


def selic(reserva):
    try:
        d = baixar("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json")
        return float(d[-1]["valor"].replace(",", ".")), "Banco Central"
    except Exception as e:
        print(f"Selic: Banco Central falhou ({e}); usando a reserva do config.json")
        return reserva, "config.json"


# ---------------------------------------------------------------- calculos
def r2(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(v, 2)


def pct(a, b):
    return None if a is None or not b else round((a / b - 1) * 100, 1)


def grupo_fundo(segmento):
    """Tijolo se divide pelo tipo de imovel; papel fica junto; fiagro pelo que tem na carteira."""
    if not segmento:
        return "Outros fundos"
    base, _, det = (p.strip() for p in segmento.partition(":"))
    if base == "Tijolo" and det:
        return det[0].upper() + det[1:]
    if base == "Papel":
        return "Papel (recebíveis)"
    if base == "Fiagro" and det:
        return {"CRA": "Recebíveis do agro (CRA)", "terras": "Terras agrícolas"}.get(det, det[0].upper() + det[1:])
    return segmento


def calcular(ativo, q, an, cfg, cdi_liq, hoje):
    preco = q["preco"]
    corte = (hoje - timedelta(days=365)).strftime("%Y-%m-%d")
    prov12 = sum(d["valor"] for d in q["proventos"] if d["data"] >= corte)
    dy = prov12 / preco * 100 if preco else None
    r = {
        **ativo, "preco": r2(preco), "var_dia_pct": pct(preco, q["anterior"]),
        "min52": r2(q["min52"]), "max52": r2(q["max52"]),
        "proventos_12m": round(prov12, 4), "dy": r2(dy),
        "ultimos_proventos": q["proventos"][-6:][::-1],
        "fonte_cotacao": q["fonte"], "sinais": [],
    }
    if ativo["tipo"] == "acao":
        teto = prov12 / (cfg["bazin_dy_minimo_pct"] / 100)
        r["preco_teto"] = r2(teto)
        r["margem_teto_pct"] = pct(teto, preco)
        r["teto_nome"] = f"Bazin ({cfg['bazin_dy_minimo_pct']}%)"
        for k in ("alvo_medio", "alvo_min", "alvo_max", "n_analistas", "origem_alvo", "data_alvo", "lpa", "vpa"):
            r[k] = an.get(k)
        r["potencial_pct"] = pct(an.get("alvo_medio"), preco)
        r["grupo"] = an.get("setor") or "Outras ações"
        lpa, vpa = an.get("lpa"), an.get("vpa")
        if lpa and vpa and lpa > 0 and vpa > 0:
            r["graham"] = r2(math.sqrt(22.5 * lpa * vpa))
            r["pl"] = r2(preco / lpa)
            r["pvp"] = r2(preco / vpa)
        if r["potencial_pct"] is not None:
            r["sinais"].append("abaixo do alvo" if r["potencial_pct"] > 0 else "acima do alvo")
        if r["margem_teto_pct"] is not None and r["margem_teto_pct"] > 0:
            r["sinais"].append("abaixo do teto")
    else:
        teto = prov12 / (cdi_liq / 100)
        r["preco_teto"] = r2(teto)
        r["margem_teto_pct"] = pct(teto, preco)
        r["teto_nome"] = "CDI líquido"
        r["segmento"] = an.get("segmento")
        r["grupo"] = grupo_fundo(an.get("segmento"))
        vp = an.get("vp_cota")
        r["vp_cota"] = vp
        r["pvp"] = r2(preco / vp) if vp else None
        r["dy_vs_cdi"] = r2(dy / cdi_liq) if dy else None
        if dy and dy > cdi_liq:
            r["sinais"].append("rende acima do CDI")
        if r["pvp"] is not None and r["pvp"] < 1:
            r["sinais"].append("abaixo do VP")
    return r


# ---------------------------------------------------------------- principal
def main():
    ativos = ler("ativos.json", [])
    analise = ler("analise.json", {})
    cfg = {"bazin_dy_minimo_pct": 6, "cdi_menos_selic_pp": 0.10, "ir_sobre_cdi_pct": 15, "selic_reserva_pct": 13.75,
           **ler("config.json", {})}
    anterior = {a["ticker"]: a for a in (ler("dados.json", {}) or {}).get("ativos", [])}

    taxa, fonte_selic = selic(cfg["selic_reserva_pct"])
    cdi_liq = (taxa - cfg["cdi_menos_selic_pp"]) * (1 - cfg["ir_sobre_cdi_pct"] / 100)
    agora = datetime.now(BRT)
    hoje = agora.replace(tzinfo=None)

    saida, falhas = [], []
    for a in ativos:
        a = {"nome": a["ticker"], **{k: v for k, v in a.items() if k != "quantidade"}, "ticker": a["ticker"].upper().strip()}
        q = cotacao(a["ticker"])
        if q is None or q["preco"] is None:
            falhas.append(a["ticker"])
            if a["ticker"] in anterior:  # mantem o ultimo valor conhecido
                velho = dict(anterior[a["ticker"]])
                velho.update({k: a[k] for k in ("nome", "tipo")})
                velho["desatualizado"] = True
                saida.append(velho)
            continue
        saida.append(calcular(a, q, analise.get(a["ticker"], {}), cfg, cdi_liq, hoje))
        time.sleep(0.4)

    vars_dia = [r["var_dia_pct"] for r in saida if r.get("var_dia_pct") is not None and not r.get("desatualizado")]
    dados = {
        "atualizado_em": agora.strftime("%Y-%m-%d %H:%M"),
        "selic": taxa, "fonte_selic": fonte_selic, "cdi_liquido": round(cdi_liq, 2),
        "premissas": cfg, "analise_coletada_em": analise.get("coletado_em"),
        "resumo": {
            "n_ativos": len(saida),
            "em_alta": sum(1 for v in vars_dia if v > 0), "em_baixa": sum(1 for v in vars_dia if v < 0),
            "var_media_pct": round(sum(vars_dia) / len(vars_dia), 2) if vars_dia else None,
        },
        "falhas": falhas,
        "ativos": saida,
    }
    gravar("dados.json", dados)
    print(f"{len(saida)} ativos, falhas: {falhas or 'nenhuma'}")
    if len(falhas) == len(ativos) and ativos:
        sys.exit("Nenhuma cotacao foi baixada.")


if __name__ == "__main__":
    main()
