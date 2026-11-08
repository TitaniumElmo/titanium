"""Precisão e recall do audita_linha nas fichas impressas. Uso: PYTHONPATH=. python scripts/avalia_gabaritos.py"""
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from heitor.dados.caepi import consulta_ca
from heitor.dados.funcoes import CATEGORIAS_CONHECIDAS, categoria_epi
from heitor.dados.regras import audita_linha

RAIZ = Path(__file__).resolve().parents[1] / "dados" / "gabaritos"
CATEGORIAS = set(CATEGORIAS_CONHECIDAS)
TIPO_POR_VALOR = {"iniciais": "iniciais", "x": "marca", "visto": "marca", "texto": "texto",
                  "falhada": "ilegivel", "outro_nome": "outro_nome"}
EQUIVALENTES = {"ca_nao_confere": "ca_nao_encontrado"}


def dados_da_assinatura(valor):
    if valor in TIPO_POR_VALOR:
        return {"assinatura": False, "assinatura_tipo": TIPO_POR_VALOR[valor],
                "assinatura_texto": None if valor == "outro_nome" else valor}
    if valor in (None, "ausente"):
        return {"assinatura": False, "assinatura_tipo": "vazio", "assinatura_texto": None}
    return {"assinatura": True, "assinatura_tipo": "nome_confere", "assinatura_texto": None}


def conferencia_ca(ca, epi, data):
    """Simula o campo do agente: só quando o CA existe na base e o equipamento não bate com o EPI."""
    if not ca or not data:
        return None
    r = consulta_ca(ca, data)
    if not r["encontrado"]:
        return None
    cat_base, cat_linha = categoria_epi(r["equipamento"].lower()), categoria_epi(epi)
    if cat_base != cat_linha and (cat_base in CATEGORIAS or cat_linha in CATEGORIAS):
        return {"confere": False, "motivo": f"CA {ca} é de {r['equipamento'].lower()[:30]}, ficha diz '{epi}'"}
    return None


def monta_linha(ficha_id, cab, e):
    ca = str(e["ca"]).strip() if e.get("ca") else None
    d = {
        "funcionario_id": str(cab.get("matricula") or ficha_id), "nome": cab.get("nome") or "-",
        "funcao": (cab.get("funcao") or "servente").strip().lower() or "servente",
        "linha": e["linha"], "data": e.get("data"), "epi": e["epi"], "qtd": e.get("qtd") or 1,
        "ca": ca, "motivo": e.get("motivo"), "origem": ficha_id,
        "confianca": {"assinatura": 1.0}, "na_ficha": True,
        **dados_da_assinatura(e.get("assinatura")),
    }
    conf = conferencia_ca(ca, e["epi"], e.get("data") or date.today().isoformat())
    if conf:
        d["conferencia_ca"] = conf
    return d


def main():
    esperados_json = json.loads((RAIZ / "esperados_audita_linha.json").read_text(encoding="utf-8"))
    esperado = {}
    for e in esperados_json["esperados"]:
        esperado[(e["ficha"], e["linha"], EQUIVALENTES.get(e["regra"], e["regra"]))] = e.get("gravidade")

    obtido, n_linhas = {}, 0
    for ficha_id in esperados_json["fichas"]:
        ficha = json.loads((RAIZ / "gabaritos" / f"{ficha_id}.json").read_text(encoding="utf-8"))
        cab = ficha.get("cabecalho", {})
        for e in ficha["entregas"]:
            n_linhas += 1
            linha = monta_linha(ficha_id, cab, e)
            for a in audita_linha(linha, linha["funcao"]):
                obtido[(ficha_id, e["linha"], EQUIVALENTES.get(a["regra"], a["regra"]))] = a["gravidade"]

    vp = set(esperado) & set(obtido)
    fp, fn = set(obtido) - set(esperado), set(esperado) - set(obtido)

    def pct(a, b):
        return f"{100 * a / b:5.1f}%" if b else "  n/a "

    por_regra = defaultdict(Counter)
    for k in vp: por_regra[k[2]]["vp"] += 1
    for k in fp: por_regra[k[2]]["fp"] += 1
    for k in fn: por_regra[k[2]]["fn"] += 1

    print(f"{len(esperados_json['fichas'])} fichas, {n_linhas} linhas, {len(esperado)} achados esperados, {len(obtido)} achados obtidos")
    print(f"\n{'regra':22} {'VP':>3} {'FP':>3} {'FN':>3}  precisão  recall")
    for regra in sorted(por_regra):
        c = por_regra[regra]
        print(f"{regra:22} {c['vp']:>3} {c['fp']:>3} {c['fn']:>3}  {pct(c['vp'], c['vp'] + c['fp'])}  {pct(c['vp'], c['vp'] + c['fn'])}")
    print(f"{'TOTAL':22} {len(vp):>3} {len(fp):>3} {len(fn):>3}  {pct(len(vp), len(vp) + len(fp))}  {pct(len(vp), len(vp) + len(fn))}")

    grav = [(k, esperado[k], obtido[k]) for k in sorted(vp) if esperado[k] and esperado[k] != obtido[k]]
    for titulo, conjunto in (("FALSOS POSITIVOS (código acusou, gabarito não)", fp),
                             ("FALSOS NEGATIVOS (gabarito esperava, código não achou)", fn)):
        print(f"\n{titulo}: {len(conjunto)}")
        for ficha, linha, regra in sorted(conjunto):
            print(f"  {ficha} linha {linha}: {regra}")
    print(f"\nGRAVIDADE DIFERENTE nos acertos: {len(grav)}")
    for (ficha, linha, regra), esp, obt in grav:
        print(f"  {ficha} linha {linha}: {regra} esperado {esp}, obtido {obt}")


if __name__ == "__main__":
    main()
