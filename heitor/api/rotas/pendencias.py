from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from heitor.api import execucao
from heitor.api.estado import estado
from heitor.api.ferramentas import TransicaoInvalida
from heitor.api.modelos import PendenciaDetalhe
from heitor.api.uploads import salvar_upload
from heitor.contrato import Destino, Pendencia, StatusPendencia

router = APIRouter(prefix="/pendencias", tags=["pendencias"])


def _detalhe(p: Pendencia) -> PendenciaDetalhe:
    return PendenciaDetalhe(**p.model_dump(), achado=estado.obter_achado(p.achado_id, p.auditoria_id))


@router.get("", response_model=list[Pendencia])
def listar(
    auditoria_id: Optional[str] = None,
    destino: Optional[Destino] = None,
    status: Optional[StatusPendencia] = None,
    funcionario_id: Optional[str] = None,
) -> list[Pendencia]:
    return estado.listar_pendencias(
        auditoria_id=auditoria_id, destino=destino, status=status, funcionario_id=funcionario_id
    )


@router.get("/{pendencia_id}", response_model=PendenciaDetalhe)
def detalhe(pendencia_id: str) -> PendenciaDetalhe:
    p = estado.obter_pendencia(pendencia_id)
    if p is None:
        raise HTTPException(404, f"pendência {pendencia_id} não encontrada")
    return _detalhe(p)


@router.post("/{pendencia_id}/resposta", response_model=PendenciaDetalhe)
async def responder(
    pendencia_id: str,
    arquivo: UploadFile = File(..., description="ficha corrigida (CSV/foto) ou documento (nota fiscal, lista de presença)"),
    nota: Optional[str] = Form(None),
) -> PendenciaDetalhe:
    """Técnico/RH responde; a reauditoria roda e a resposta já traz o novo status."""
    p = estado.obter_pendencia(pendencia_id)
    if p is None:
        raise HTTPException(404, f"pendência {pendencia_id} não encontrada")
    if p.status not in ("aberta", "reaberta"):
        raise HTTPException(409, f"pendência está '{p.status}'; só aceita resposta quando aberta ou reaberta")

    caminho = await salvar_upload(arquivo, p.auditoria_id or "sem-auditoria", "respostas", pendencia_id)
    try:
        p = await run_in_threadpool(execucao.executar_reauditoria, pendencia_id, str(caminho), nota)
    except TransicaoInvalida as exc:  # outra resposta chegou ao mesmo tempo
        raise HTTPException(409, str(exc))
    except execucao.FalhaReauditoria as exc:
        raise HTTPException(502, f"reauditoria falhou duas vezes; pendência mantida: {exc}")
    return _detalhe(p)
