"""Entregas da planilha (linhas) para a ficha do funcionário na tela.

O vigia audita só quem mudou: cada auditoria tem as linhas de parte dos funcionários.
A ficha de cada funcionário é a da auditoria MAIS RECENTE que o incluiu.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from heitor.api.estado import estado
from heitor.contrato import Linha

router = APIRouter(tags=["fichas"])


@router.get("/auditorias/{auditoria_id}/linhas", response_model=list[Linha])
def linhas_da_auditoria(auditoria_id: str) -> list[Linha]:
    """As entregas que entraram nesta auditoria."""
    if estado.obter_auditoria(auditoria_id) is None:
        raise HTTPException(404, f"auditoria {auditoria_id} não encontrada")
    return estado.obter_linhas(auditoria_id)


@router.get("/fichas", response_model=dict[str, list[Linha]])
def fichas() -> dict[str, list[Linha]]:
    """{funcionario_id: entregas}, cada funcionário com as linhas da auditoria mais recente que o incluiu."""
    atual: dict[str, list[Linha]] = {}
    for aud in estado.listar_auditorias():  # a mais recente primeiro
        por_func: dict[str, list[Linha]] = {}
        for l in estado.obter_linhas(aud.id):
            por_func.setdefault(l.funcionario_id, []).append(l)
        for fid, ls in por_func.items():
            atual.setdefault(fid, sorted(ls, key=lambda l: (l.data is None, l.data, l.linha)))
    return atual
