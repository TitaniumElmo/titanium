"""Ferramentas do agente que pertencem à API (Pierre).

A Sofia importa daqui:

    from heitor.api.ferramentas import criar_pendencia, fechar_pendencia, obter_pendencia

Dentro do agente os objetos circulam como dicts (heitor/agente/tipos.py), então
estas três funções aceitam dict ou modelo Pydantic e DEVOLVEM DICTS. Por
dentro, a API guarda modelos validados pelo contrato.

Nenhuma delas altera ficha: só gravam pendências e mudam o status delas.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import date, datetime
from typing import Any, Optional, Union

from heitor.api.estado import estado
from heitor.api.notificacao import notificar
from heitor.contrato import Achado, Destino, HistoricoPendencia, Pendencia, StatusPendencia

# Auditoria em execução na thread atual. A API preenche antes de chamar o
# agente, para `criar_pendencia` funcionar mesmo se o Achado vier sem auditoria_id.
auditoria_atual: ContextVar[Optional[str]] = ContextVar("auditoria_atual", default=None)

# Valores de `resultado` aceitos por fechar_pendencia além de True/False.
_CONFERE = {"confirmada", "fechada", "ok", "sim"}
_NAO_CONFERE = {"nao_confirmada", "não_confirmada", "reaberta", "nao", "não"}


class TransicaoInvalida(Exception):
    """Mudança de status não permitida (ex.: responder pendência já fechada)."""


def _json(modelo: Any) -> dict[str, Any]:
    return modelo.model_dump(mode="json")


def criar_pendencia(
    achado: Union[Achado, dict], destino: Destino, acao: str, prazo: Union[date, str]
) -> dict[str, Any]:
    """Grava a pendência e avisa o técnico ou o RH. Devolve a Pendencia como dict.

    Idempotente: se já existe pendência não fechada para o mesmo achado,
    devolve a existente (o agente pode repetir a chamada numa retentativa).
    """
    achado = achado if isinstance(achado, Achado) else Achado.model_validate(achado)
    auditoria_id = achado.auditoria_id or auditoria_atual.get()
    achado = achado.model_copy(update={"auditoria_id": auditoria_id})

    existentes = [
        p
        for p in estado.listar_pendencias(auditoria_id=auditoria_id, achado_id=achado.id)
        if p.status != "fechada"
    ]
    if existentes:
        return _json(existentes[0])

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
        historico=[HistoricoPendencia(status="aberta", ts=datetime.now(), nota="criada pela auditoria")],
    )
    if auditoria_id:
        estado.salvar_achado(achado)
    estado.salvar_pendencia(pendencia)
    notificar(pendencia)
    return _json(pendencia)


def fechar_pendencia(
    pendencia: Union[Pendencia, dict, str], resultado: Union[bool, str], nota: Optional[str] = None
) -> dict[str, Any]:
    """Fecha se a reauditoria conferiu; se não, reabre. Devolve a Pendencia como dict.

    `resultado`: True/False ou "confirmada"/"nao_confirmada".
    """
    if isinstance(pendencia, str):
        pendencia_id = pendencia
    elif isinstance(pendencia, dict):
        pendencia_id = pendencia["id"]
    else:
        pendencia_id = pendencia.id

    if isinstance(resultado, str):
        r = resultado.strip().lower()
        if r not in _CONFERE | _NAO_CONFERE:
            raise ValueError(f"resultado desconhecido: {resultado!r}")
        resultado = r in _CONFERE

    if resultado:
        return _json(mudar_status(pendencia_id, "fechada", nota or "reauditoria conferiu a correção"))
    p = mudar_status(pendencia_id, "reaberta", nota or "reauditoria não conferiu a correção")
    notificar(p, assunto="Pendência reaberta pelo Heitor")
    return _json(p)


def obter_pendencia(pendencia_id: str) -> Optional[tuple[dict[str, Any], dict[str, Any]]]:
    """(Pendencia, Achado) como dicts, ou None se a pendência não existir.

    O reauditar precisa do achado que gerou a pendência.
    """
    p = estado.obter_pendencia(pendencia_id)
    if p is None:
        return None
    achado = estado.obter_achado(p.achado_id, p.auditoria_id)
    if achado is None:
        return None
    return _json(p), _json(achado)


# ---------------------------------------------------------------------------
# Uso interno da API (não são ferramentas do agente): devolvem modelos.
# ---------------------------------------------------------------------------


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
