"""Fichas de exemplo com problemas plantados, para testar o agente.

Não é o dataset da demo (esse é do Gustavo). Rodar:
    python -m heitor.agente.exemplo          # com LLM
    HEITOR_LLM=off python -m heitor.agente.exemplo   # sem LLM
"""

from __future__ import annotations

import json
import sys

from heitor.contrato import Evento
from heitor.agente.tipos import LinhaDict as Linha


def _l(fid: str, nome: str, funcao: str, data: str, epi: str, ca: str | None, assinatura: bool) -> Linha:
    return {"funcionario_id": fid, "nome": nome, "funcao": funcao, "data": data, "epi": epi, "qtd": 1,
            "ca": ca, "motivo": "E", "assinatura": assinatura, "origem": "exemplo"}


LINHAS: list[Linha] = [
    # Rafael (servente): nunca recebeu protetor auditivo; linha sem CA; linha sem assinatura.
    _l("0302", "Rafael Souza Costa", "servente", "2025-08-01", "capacete", "29637", True),
    _l("0302", "Rafael Souza Costa", "servente", "2025-08-01", "botina", "9182", False),
    _l("0302", "Rafael Souza Costa", "servente", "2025-11-03", "luva de raspa", None, True),
    # Ana (armadora): luva entregue quando o CA estava vencido; protetor auditivo em dia.
    _l("0415", "Ana Lima", "armador", "2026-10-01", "protetor auditivo", "17664", True),
    _l("0415", "Ana Lima", "armador", "2024-05-10", "luva de raspa", "21245", True),
    _l("0415", "Ana Lima", "armador", "2026-10-20", "luva de raspa", "21245", True),
    # João (pedreiro): botina com CA vencido desde 2020.
    _l("0520", "João Pereira", "pedreiro", "2026-09-15", "protetor auditivo", "17664", True),
    _l("0520", "João Pereira", "pedreiro", "2026-09-15", "capacete", "29637", True),
    _l("0520", "João Pereira", "pedreiro", "2026-09-15", "botina", "28499", True),
]


def imprimir_evento(e: Evento) -> None:
    custo = f" ${e.custo_usd:.5f}" if e.custo_usd else ""
    quem = e.funcionario_id or "-"
    if e.tipo == "decisao":
        print(f"[{e.passo:>3}] {quem:>5} 💭 {e.saida.get('pensamento', '')}{custo}")
        return
    saida = json.dumps(e.saida, ensure_ascii=False, default=str)
    marca = "⚠️ " if e.tipo == "erro" else "🔧"
    print(f"[{e.passo:>3}] {quem:>5} {marca} {e.ferramenta:<20}{custo} -> {saida[:150]}")


if __name__ == "__main__":
    from heitor.agente.grafo import rodar_auditoria

    r = rodar_auditoria("au-exemplo", [dict(l) for l in LINHAS], imprimir_evento)
    print("\n=== RESULTADO ===")
    print(f"modo={r['modo']} passos={r['passos']} custo=${r['custo_usd']} duração={r['duracao_s']}s")
    print("contagem:", r["contagem"], "| exposição:", r["exposicao"].get("total_brl"))
    for p in r["pendencias"]:
        print(f"  {p['id']} [{p['destino']}] {p['acao']} (prazo {p['prazo']})")
    print("stubs em uso:", ", ".join(r["stubs"]))
    sys.exit(0)
