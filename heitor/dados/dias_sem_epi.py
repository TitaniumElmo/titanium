"""Dias sem EPI válido registrado, por funcionário. Só para exibição: não é regra, não gera achado, não tem R$.

Soma, sobre os achados troca_passado, os dias de cada intervalo entre entregas consecutivas
acima da vida útil. O trecho da última entrega até hoje é troca_atrasada e não entra.
A ficha não prova que a pessoa estava sem proteção: por isso "registrado" e "pelo menos".
"""

from heitor.dados.exposicao import _como_dict, dias_alem_da_vida_util
from heitor.dados.funcoes import CATEGORIAS_CONHECIDAS, pgr_completo

NOME = "dias sem EPI válido registrado"


def _categoria(achado):
    return str(achado.get("evidencia") or "").split(":", 1)[0].strip()


def dias_sem_epi_valido(achados):
    """{funcionario_id: dias}. Funcionário sem troca_passado fica de fora (vale 0)."""
    categorias = set(CATEGORIAS_CONHECIDAS) if pgr_completo() else {"protetor auditivo"}
    total = {}
    for a in (_como_dict(x) for x in achados):
        if a.get("regra") != "troca_passado" or a.get("gravidade") == "ok" or _categoria(a) not in categorias:
            continue
        dias = dias_alem_da_vida_util(a)
        if dias:
            total[a["funcionario_id"]] = total.get(a["funcionario_id"], 0) + dias
    return total


def texto(dias):
    return f"pelo menos {dias} dias sem EPI válido registrado"
