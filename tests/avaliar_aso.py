"""Avalia a leitura de ASOs ESCANEADOS (papel assinado à caneta) contra gabaritos feitos à mão.

Pergunta para quem decide o roadmap: dá para prometer "o Elmo lê o ASO escaneado"? Com que números?

Como montar o teste (dados SEMPRE fictícios; cada pessoa assina com a própria assinatura):
  1. Imprimir heitor/exemplos/aso_modelo.pdf (tem a marca "DOCUMENTO DE TESTE · SEM VALOR").
  2. Preencher à mão e assinar. Deixar de propósito casos difíceis: sem assinatura do médico, sem CRM, carimbo
     sem assinatura por cima, trabalhador que não assinou, um escaneado torto.
  3. Escanear (foto do celular ou PDF) para fotos_teste/aso/ (fora do Git: tem assinaturas).
  4. Um gabarito por ASO em fotos_teste/aso/gabaritos/<nome>.json, no formato de
     heitor/exemplos/aso_gabarito_exemplo.json.

Uso:
    python -m tests.avaliar_aso fotos_teste/aso fotos_teste/aso/gabaritos [--saida resultado.json]

Para cada ASO, os dois modelos de visão (o principal e o do veto) leem campos e assinaturas. Uma assinatura só
conta como presente se OS DOIS a virem (a mesma regra do veto da ficha de EPI); os campos vêm do principal.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from heitor.agente.conferencia_assinaturas import MODELO_VETO
from heitor.agente.extracao import paginas_do_pdf
from heitor.agente.ferramentas import normalizar_data
from heitor.agente.foto import MODELO_VISAO, _imagem_b64, _perguntar
from heitor.agente.llm import ClienteLLM

PROMPT_ASO = """Esta é a foto de um Atestado de Saúde Ocupacional (ASO) preenchido à mão.
Leia os campos e diga se há assinatura em cada lugar indicado. Para um campo em branco, use "vazio";
para escrita que você não consegue ler, use "ilegivel". Assinatura: "presente" se há assinatura ou rubrica
À CANETA no espaço; "vazio" se não há (um carimbo impresso sozinho NÃO é assinatura).
Responda SOMENTE com JSON:
{"nome": "...", "crm": "...", "data_exame": "DD/MM/AAAA", "tipo_exame": "admissional|periodico|retorno|mudanca_de_funcao|demissional|vazio",
 "resultado": "apto|inapto|vazio", "carimbo_medico": true, "assinatura_medico": "presente|vazio",
 "assinatura_trabalhador": "presente|vazio"}"""

CAMPOS = ("nome", "crm", "data_exame", "tipo_exame", "resultado")


def _norm(t: Any) -> str:
    s = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _igual(campo: str, lido: Any, esperado: Any) -> bool:
    if campo == "data_exame":
        return normalizar_data(str(lido or "")) == (esperado or None)
    if campo == "crm":
        return re.sub(r"\D", "", str(lido or "")) == re.sub(r"\D", "", str(esperado or ""))
    return _norm(lido) == _norm(esperado)


def _imagem(arquivo: Path) -> Path:
    return paginas_do_pdf(arquivo, max_paginas=1)[0] if arquivo.suffix.lower() == ".pdf" else arquivo


def ler(arquivo: Path, modelo: str, tentativas: int = 3) -> tuple[dict[str, Any], float]:
    """O provedor às vezes responde 503 ("at capacity"): tenta de novo com espera; sem leitura, devolve {}."""
    cliente = ClienteLLM(modelo=modelo, reserva=modelo, timeout_s=90, extra=False)
    for i in range(tentativas):
        try:
            return _perguntar(cliente, _imagem_b64(_imagem(arquivo)), PROMPT_ASO, 500)
        except Exception as e:  # noqa: BLE001
            if i == tentativas - 1:
                print(f"   {arquivo.name}: {modelo} não respondeu ({type(e).__name__})")
                return {}, 0.0
            time.sleep(8 * (i + 1))
    return {}, 0.0


def _presente(v: Any) -> bool:
    return _norm(v) == "presente"


def avaliar(pasta: Path, gabaritos: Path) -> dict[str, Any]:
    casos = []
    for g in sorted(gabaritos.glob("*.json")):
        gab = json.loads(g.read_text())
        arq = pasta / gab["arquivo"]
        if arq.exists():
            casos.append((arq, gab))

    def um(caso):
        arq, gab = caso
        (a, c1), (b, c2) = ler(arq, MODELO_VISAO), ler(arq, MODELO_VETO)
        return arq.name, gab, a, b, c1 + c2

    with ThreadPoolExecutor(max_workers=2) as ex:  # o provedor recusa muitas chamadas ao mesmo tempo
        res = list(ex.map(um, casos))

    acertos = {c: 0 for c in CAMPOS}
    ass = {"medico": {"pres_ok": 0, "pres": 0, "aus_pega": 0, "aus": 0},
           "trabalhador": {"pres_ok": 0, "pres": 0, "aus_pega": 0, "aus": 0}}
    so_principal_errou = 0
    custo = 0.0
    linhas = []
    nao_lidos = [nome for nome, _, a, b, _ in res if not a or not b]
    res = [r for r in res if r[2] and r[3]]  # sem leitura dos dois modelos não dá para medir: fica de fora
    for nome, gab, a, b, c in res:
        custo += c
        campos = {k: _igual(k, a.get(k), gab.get(k)) for k in CAMPOS}
        for k, ok in campos.items():
            acertos[k] += ok
        det = {}
        for quem in ("medico", "trabalhador"):
            chave = f"assinatura_{quem}"
            aceita = _presente(a.get(chave)) and _presente(b.get(chave))  # os dois precisam ver
            esperado = gab.get(chave) == "presente"
            m = ass[quem]
            if esperado:
                m["pres"] += 1
                m["pres_ok"] += aceita
            else:
                m["aus"] += 1
                m["aus_pega"] += not aceita
                so_principal_errou += _presente(a.get(chave)) and not aceita  # o segundo modelo salvou
            det[quem] = (gab.get(chave), a.get(chave), b.get(chave), "ok" if aceita == esperado else "ERRO")
        linhas.append({"arquivo": nome, "campos": campos, "assinaturas": det})
        print(f"{nome}: campos {sum(campos.values())}/{len(CAMPOS)} "
              + " ".join(f"{k}{'' if v else '✗'}" for k, v in campos.items())
              + f" | médico {det['medico']} | trabalhador {det['trabalhador']}")

    n = len(res)
    print(f"\n### {n} ASOs, US$ {custo:.4f}" + (f" | NÃO LIDOS (provedor fora): {nao_lidos}" if nao_lidos else ""))
    for k in CAMPOS:
        print(f"    {k:22} {acertos[k]}/{n}")
    for quem, m in ass.items():
        print(f"    assinatura do {quem:11} presentes aceitas {m['pres_ok']}/{m['pres']} | "
              f"ausentes pegas {m['aus_pega']}/{m['aus']}  ⚠️ deixou passar: {m['aus'] - m['aus_pega']}")
    print(f"    ausências que só o segundo modelo pegou: {so_principal_errou}")
    return {"n": n, "nao_lidos": nao_lidos, "custo_usd": round(custo, 4), "campos": acertos, "assinaturas": ass,
            "salvas_pelo_segundo_modelo": so_principal_errou, "casos": linhas}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", type=Path)
    ap.add_argument("gabaritos", type=Path)
    ap.add_argument("--saida", type=Path)
    a = ap.parse_args()
    r = avaliar(a.pasta, a.gabaritos)
    if a.saida:
        a.saida.write_text(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
