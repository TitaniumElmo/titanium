"""Ferramentas do agente que pertencem à API (Pierre).

A Sofia importa daqui:

    from heitor.api.ferramentas import criar_pendencia, fechar_pendencia

Nenhuma delas altera ficha: só gravam pendências e mudam o status delas.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import date, datetime
from typing import Optional, Union

from heitor.api.estado import estado
from heitor.api.notificacao import notificar
from heitor.contrato import Achado, Destino, HistoricoPendencia, Pendencia, StatusPendencia

# Auditoria em execução na thread atual. A API preenche antes de chamar o
# agente, para `criar_pendencia` funcionar mesmo se o Achado vier sem auditoria_id.
auditoria_atual: ContextVar[Optional[str]] = ContextVar("auditoria_atual", default=None)


class TransicaoInvalida(Exception):
    """Mudança de status não permitida (ex.: responder pendência já fechada)."""


def criar_pendencia(achado: Achado, destino: Destino, acao: str, prazo: Union[date, str]) -> Pendencia:
    """Grava a pendência e avisa o técnico ou o RH.

    Idempotente: se já existe pendência não fechada para o mesmo achado,
    devolve a existente (o agente pode repetir a chamada numa retentativa).
    """
    auditoria_id = achado.auditoria_id or auditoria_atual.get()
    achado = achado.model_copy(update={"auditoria_id": auditoria_id})

    existentes = [
        p
        for p in estado.listar_pendencias(auditoria_id=auditoria_id, achado_id=achado.id)
        if p.status != "fechada"
    ]
    if existentes:
        return existentes[0]

    agora = datetime.now()
    pendencia = Pendencia(
        id=estado.novo_id("p"),
        achado_id=achado.id,
        auditoria_id=auditoria_id,
        funcionario_id=achado.funcionario_id,
        destino=destino,
        acao=acao,
        motivo=achado.evidencia,
        prazo=prazo,
        status="aberta",
        historico=[HistoricoPendencia(status="aberta", ts=agora, nota="criada pela auditoria")],
    )
    if auditoria_id:
        estado.salvar_achado(achado)
    estado.salvar_pendencia(pendencia)
    notificar(pendencia)
    return pendencia


def fechar_pendencia(pendencia: Union[Pendencia, str], resultado: bool, nota: Optional[str] = None) -> Pendencia:
    """Fecha a pendência se a reauditoria conferiu (`resultado=True`); se não, reabre."""
    pendencia_id = pendencia if isinstance(pendencia, str) else pendencia.id
    if resultado:
        return mudar_status(pendencia_id, "fechada", nota or "reauditoria conferiu a correção")
    p = mudar_status(pendencia_id, "reaberta", nota or "reauditoria não conferiu a correção")
    notificar(p, assunto="Pendência reaberta pelo Heitor")
    return p


def marcar_aguardando(pendencia_id: str, nota: Optional[str] = None) -> Pendencia:
    """Resposta chegou: a pendência aguarda a reauditoria."""
    return mudar_status(
        pendencia_id, "aguardando", nota or "resposta recebida", exigir=("aberta", "reaberta")
    )


def mudar_status(
    pendencia_id: str,
    novo: StatusPendencia,
    nota: Optional[str] = None,
    exigir: Optional[tuple[StatusPendencia, ...]] = None,
) -> Pendencia:
    def aplicar(p: Pendencia) -> None:
        if exigir and p.status not in exigir:
            raise TransicaoInvalida(f"pendência {p.id} está '{p.status}'; esperado {', '.join(exigir)}")
        p.status = novo
        p.historico.append(HistoricoPendencia(status=novo, ts=datetime.now(), nota=nota))

    return estado.atualizar_pendencia(pendencia_id, aplicar)
