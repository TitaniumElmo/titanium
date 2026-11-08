from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from heitor.api import config, execucao, integracao
from heitor.api.estado import estado
from heitor.api.modelos import Auditoria, ResumoAuditoria
from heitor.api.uploads import salvar_upload
from heitor.contrato import Achado, Gravidade, TipoAchado
from heitor.dados.dias_sem_epi import dias_sem_epi_valido

router = APIRouter(prefix="/auditorias", tags=["auditorias"])


def _auditoria_ou_404(auditoria_id: str) -> Auditoria:
    aud = estado.obter_auditoria(auditoria_id)
    if aud is None:
        raise HTTPException(404, f"auditoria {auditoria_id} não encontrada")
    return aud


def criar_e_iniciar(
    caminhos: list[str],
    auditoria_id: Optional[str] = None,
    fotos: Optional[list[tuple[str, Optional[str]]]] = None,
    disparado_por: str = "upload",
) -> Auditoria:
    auditoria_id = auditoria_id or estado.novo_id("au")
    fotos = fotos or []
    aud = estado.criar_auditoria(
        auditoria_id, [Path(c).name for c in caminhos] + [Path(f).name for f, _ in fotos], disparado_por=disparado_por
    )
    execucao.iniciar_auditoria(aud.id, caminhos, fotos)
    return aud


@router.post("", status_code=202, response_model=Auditoria)
async def criar_auditoria(
    arquivos: list[UploadFile] = File(default=[], description="planilhas (CSV) com as entregas: a fonte dos dados"),
    fotos: list[UploadFile] = File(default=[], description="fotos das fichas de papel: só conferem as assinaturas"),
    funcionarios_das_fotos: list[str] = Form(
        default=[],
        description="funcionario_id de cada foto, na mesma ordem de `fotos`. "
        "Se faltar, vale a matrícula no nome do arquivo (ex.: 0302.jpg)",
    ),
    exemplo: bool = Form(False, description="true = usar as fichas de exemplo"),
) -> Auditoria:
    """Recebe as planilhas e, opcionalmente, as fotos das fichas de papel, e roda o agente em segundo plano.

    Com foto, o agente decide, por funcionário, se vale conferir as assinaturas no papel
    (`conferir_e_auditar`). Os dados (data, EPI, CA) vêm sempre da planilha.
    """
    auditoria_id = estado.novo_id("au")
    caminhos = [str(await salvar_upload(a, auditoria_id)) for a in arquivos if a.filename]
    if exemplo:
        caminhos.append(str(config.FICHA_EXEMPLO))
    pares = []
    for i, foto in enumerate(f for f in fotos if f.filename):
        informado = funcionarios_das_fotos[i] if i < len(funcionarios_das_fotos) else None
        pares.append((str(await salvar_upload(foto, auditoria_id, "fotos")), informado or None))
    if not caminhos:
        raise HTTPException(400, "envie ao menos uma planilha em 'arquivos' ou use exemplo=true")
    return criar_e_iniciar(caminhos, auditoria_id, pares)


@router.get("", response_model=list[Auditoria])
def listar() -> list[Auditoria]:
    """Todas as auditorias, a mais recente primeiro (inclui as disparadas pelo vigia)."""
    return [a.model_copy(update={"relatorio": None}) for a in estado.listar_auditorias()]


@router.get("/{auditoria_id}", response_model=ResumoAuditoria)
def resumo(auditoria_id: str) -> ResumoAuditoria:
    aud = _auditoria_ou_404(auditoria_id)
    achados = estado.listar_achados(auditoria_id)
    eventos = estado.eventos_desde(auditoria_id)
    pendencias = estado.listar_pendencias(auditoria_id=auditoria_id)
    return ResumoAuditoria(
        **aud.model_dump(),
        contagem_gravidade=dict(Counter(a.gravidade for a in achados)),
        contagem_tipo=dict(Counter(a.tipo for a in achados)),
        exposicao_total_rs=_exposicao_total(aud, achados),
        pendencias_abertas=sum(p.status != "fechada" for p in pendencias),
        passos=sum(e.tipo != "erro" for e in eventos),
        custo_total_usd=round(sum(e.custo_usd for e in eventos), 6),
        dias_sem_epi_valido_registrado=dias_sem_epi_valido(achados),
    )


def _exposicao_total(aud: Auditoria, achados: list[Achado]) -> float:
    """Usa o total calculado pelo agente (calcula_exposicao); senão, soma os achados."""
    if aud.exposicao and aud.exposicao.get("total_brl") is not None:
        return round(float(aud.exposicao["total_brl"]), 2)
    return round(sum(a.exposicao_rs or 0 for a in achados if a.tipo == "passivo"), 2)


@router.get("/{auditoria_id}/achados", response_model=list[Achado])
def achados(
    auditoria_id: str,
    tipo: Optional[TipoAchado] = None,
    gravidade: Optional[Gravidade] = None,
    funcionario_id: Optional[str] = None,
) -> list[Achado]:
    _auditoria_ou_404(auditoria_id)
    return [
        a
        for a in estado.listar_achados(auditoria_id)
        if (tipo is None or a.tipo == tipo)
        and (gravidade is None or a.gravidade == gravidade)
        and (funcionario_id is None or a.funcionario_id == funcionario_id)
    ]


@router.get("/{auditoria_id}/relatorio")
async def relatorio(auditoria_id: str) -> dict:
    """Relatório com base legal. Sempre traz `texto`; o agente real traz também
    `itens` (um por achado), `resumo`, `exposicao` e `aviso`."""
    aud = _auditoria_ou_404(auditoria_id)
    if aud.status == "processando":
        raise HTTPException(409, "auditoria ainda em andamento")
    rel = aud.relatorio
    if rel is None:  # o agente não devolveu relatório: gera agora
        achados = [a.model_dump(mode="json") for a in estado.listar_achados(auditoria_id)]
        rel = await run_in_threadpool(integracao.gerar_relatorio, achados, aud.exposicao)
    if isinstance(rel, str):
        rel = {"texto": rel}
    return {"auditoria_id": auditoria_id, **rel}


@router.get("/{auditoria_id}/eventos")
async def eventos(
    auditoria_id: str,
    request: Request,
    ate_concluir: bool = False,
    last_event_id: Optional[str] = Header(None),
) -> StreamingResponse:
    """SSE do log do agente.

    Mensagens:
      event: evento  -> data: Evento (JSON); `id` = posição no log
      event: status  -> data: {"status": ...} quando o status da auditoria muda
    A conexão fica aberta para mostrar também as reauditorias. Com
    `ate_concluir=true`, fecha quando a auditoria termina. Ao reconectar, o
    navegador manda Last-Event-ID e o envio continua de onde parou.
    """
    _auditoria_ou_404(auditoria_id)
    inicio = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0

    async def gerar():
        idx, status_enviado, ultimo_envio = inicio, None, time.monotonic()
        while not await request.is_disconnected():
            aud = estado.obter_auditoria(auditoria_id)
            for ev in estado.eventos_desde(auditoria_id, idx):
                yield f"id: {idx}\nevent: evento\ndata: {ev.model_dump_json()}\n\n"
                idx += 1
                ultimo_envio = time.monotonic()
            if aud is None:  # reset da demo
                yield 'event: status\ndata: {"status": "removida"}\n\n'
                return
            if aud.status != status_enviado:
                status_enviado = aud.status
                yield f"event: status\ndata: {json.dumps({'status': aud.status})}\n\n"
            # Só encerra depois de esvaziar o log lido junto com o status final.
            if ate_concluir and aud.status != "processando":
                return
            if time.monotonic() - ultimo_envio > 15:
                yield ": ping\n\n"
                ultimo_envio = time.monotonic()
            await asyncio.sleep(0.25)

    return StreamingResponse(
        gerar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
