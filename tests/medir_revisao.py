"""Quantas tarefas de revisão humana chegam ao técnico, por ficha, no fluxo completo (foto -> auditoria).

Uso: python -m tests.medir_revisao <pasta_fotos> <foto1> <foto2> ... [--reler]
As leituras ficam em cache em fotos_teste/resultados/leituras/ (use --reler para ler de novo).
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ["HEITOR_LLM"] = "off"  # agente com a política determinística; a leitura de foto usa o modelo de visão

from heitor.agente.foto import ler_foto  # noqa: E402
from heitor.agente.grafo import rodar_auditoria  # noqa: E402
from tests.test_contrato_agente import stubs_de_dados  # noqa: E402

CACHE = Path("fotos_teste/resultados/leituras")


def ler(pasta: Path, nome: str, reler: bool) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    c = CACHE / f"{nome}.json"
    if c.exists() and not reler:
        return json.loads(c.read_text())
    linhas = ler_foto(pasta / nome)["linhas"]
    c.write_text(json.dumps(linhas, ensure_ascii=False, default=str))
    return linhas


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pasta, fotos, reler = Path(args[0]), args[1:], "--reler" in sys.argv
    with ThreadPoolExecutor(2) as p:
        leituras = dict(zip(fotos, p.map(lambda f: ler(pasta, f, reler), fotos)))
    todas, dono = [], {}
    for foto, linhas in leituras.items():
        for l in linhas:
            l["funcionario_id"] = f"{foto.split('.')[0]}"  # uma ficha por foto (matrícula lida pode vir errada)
            dono[l["funcionario_id"]] = foto
            todas.append(l)
    with stubs_de_dados():
        r = rodar_auditoria("au-medicao", todas)
    total_tarefas = total_linhas = 0
    print(f"{'ficha':24}{'linhas':>7}{'tarefas':>9}  revisões (o que o técnico confere no papel)")
    for foto, linhas in leituras.items():
        fid = foto.split(".")[0]
        ps = [p for p in r["pendencias"] if p["funcionario_id"] == fid
              and p["acao"].startswith(("conferir", "revisar manualmente"))]
        cobertas = {a["linha"] for a in r["achados"] if a["funcionario_id"] == fid
                    and r_pend(r, a) in {p["id"] for p in ps} and a.get("linha") is not None}
        total_tarefas += len(ps)
        total_linhas += len(cobertas)
        resumo = "; ".join(p["acao"][:70] for p in ps) or "-"
        print(f"{fid:24}{len(linhas):>7}{len(ps):>9}  {resumo}")
    n = len(leituras)
    print(f"\n{n} fichas | {total_tarefas} tarefas de revisão ({total_tarefas / n:.1f} por ficha) | "
          f"{sum(1 for f in leituras if any(p['funcionario_id'] == f.split('.')[0] and p['acao'].startswith(('conferir', 'revisar manualmente')) for p in r['pendencias']))} fichas com alguma revisão")


def r_pend(r: dict, a: dict) -> str | None:
    for p in r["pendencias"]:
        if p["achado_id"] == a["id"]:
            return p["id"]
    return None


if __name__ == "__main__":
    main()
