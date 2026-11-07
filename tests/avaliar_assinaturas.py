"""Avalia a conferência de assinaturas contra a planilha (o gabarito faz o papel da planilha).

Uso: python -m tests.avaliar_assinaturas <pasta_fotos> <pasta_gabaritos> [--cenarios]
--cenarios: em 3 fichas, testa também uma entrega falsa na planilha (deve dar "sem linha na ficha")
            e uma entrega tirada da planilha (deve aparecer em "fora da planilha").
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from heitor.agente.conferencia_assinaturas import conferir_assinaturas
from tests.avaliar_fotos import classe_assinatura

LIMIAR = 0.7


def planilha_do_gabarito(g: dict) -> list[dict]:
    cab = g.get("cabecalho", {})
    return [{"funcionario_id": cab.get("matricula") or g["ficha_id"], "nome": cab.get("nome", ""),
             "funcao": cab.get("funcao", ""), "linha": e["linha"], "data": e["data"], "epi": e["epi"],
             "qtd": e.get("qtd", 1), "ca": e.get("ca"), "motivo": e.get("motivo"), "assinatura": None,
             "confianca": {}, "origem": "planilha"} for e in g["entregas"]]


def main() -> None:
    pasta, gabs = Path(sys.argv[1]), Path(sys.argv[2])
    casos = []
    for f in sorted(gabs.glob("*.json")):
        g = json.loads(f.read_text())
        foto = pasta / g["fotos"][0]["arquivo"]
        if foto.exists():
            casos.append((foto, g))

    def rodar(caso):
        foto, g = caso
        t = time.time()
        return foto, g, conferir_assinaturas(foto, planilha_do_gabarito(g)), time.time() - t

    tot = dict(linhas=0, presente=0, presente_ok=0, alarme=0, ausente=0, ausente_pega=0, passou=0,
               ambigua=0, ambigua_pega=0, ambigua_aceita=0, revisao=0, custo=0.0)
    with ThreadPoolExecutor(2) as pool:
        for foto, g, r, seg in pool.map(rodar, casos):
            tot["custo"] += r["custo_usd"]
            print(f"\n== {foto.name} ({seg:.0f}s) fora da planilha: {r['fora_da_planilha']}")
            for e, l in zip(g["entregas"], r["linhas"]):
                cl = classe_assinatura(e.get("assinatura"))
                conf = l["confianca"].get("assinatura", 0)
                aceitou = l.get("assinatura") is True and conf >= LIMIAR
                tot["linhas"] += 1
                tot[cl] += 1
                tot["revisao"] += conf < LIMIAR
                if cl == "presente":
                    tot["presente_ok"] += aceitou
                    tot["alarme"] += l.get("assinatura") is False and conf >= LIMIAR
                    ok = aceitou
                elif cl == "ausente":
                    tot["ausente_pega"] += not aceitou
                    tot["passou"] += aceitou
                    ok = not aceitou
                else:
                    tot["ambigua_pega"] += not aceitou
                    tot["ambigua_aceita"] += aceitou
                    ok = not aceitou
                print(f"   {'✓' if ok else '✗'} linha {e['linha']:>2} esp {e.get('assinatura')!s:11} -> "
                      f"{l.get('assinatura')!s:5} conf {conf:.2f} [{l.get('assinatura_tipo')}: {l.get('assinatura_texto')!r}]"
                      f" B={l['leitura_assinatura']['b']!r}")
    n = tot["linhas"] or 1
    print(f"\n### {len(casos)} fichas, {tot['linhas']} entregas, ${tot['custo']:.4f}")
    print(f"    assinadas aceitas: {tot['presente_ok']}/{tot['presente']} (alarme falso {tot['alarme']})")
    print(f"    SEM assinatura pegas: {tot['ausente_pega']}/{tot['ausente']}  ⚠️ deixou passar: {tot['passou']}")
    print(f"    ambíguas pegas: {tot['ambigua_pega']}/{tot['ambigua']} (aceitas: {tot['ambigua_aceita']})")
    print(f"    entregas para conferência no papel: {tot['revisao']}/{tot['linhas']} ({100 * tot['revisao'] / n:.0f}%)")

    if "--cenarios" in sys.argv:
        print("\n### Cenários: entrega falsa na planilha / entrega tirada da planilha")
        for foto, g in casos[:3]:
            planilha = planilha_do_gabarito(g)
            falsa = dict(planilha[0], linha=99, data="2026-10-15", epi="cinto de segurança", ca="12345")
            tirada = planilha[-1]
            r = conferir_assinaturas(foto, planilha[:-1] + [falsa])
            l_falsa = r["linhas"][-1]
            achou_tirada = any(x.get("data") == tirada["data"] for x in r["fora_da_planilha"])
            print(f"   {foto.name}: falsa -> na_ficha={l_falsa['na_ficha']} conf {l_falsa['confianca']['assinatura']:.2f}"
                  f" {'✓' if l_falsa['na_ficha'] is False else '✗'} | tirada ({tirada['data']} {tirada['epi']})"
                  f" em fora_da_planilha: {'✓' if achou_tirada else '✗'} {r['fora_da_planilha']}")


if __name__ == "__main__":
    main()
