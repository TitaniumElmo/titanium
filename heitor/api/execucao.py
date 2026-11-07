"""Execução do agente fora do ciclo da requisição.

Hoje: um pool de threads no próprio processo. Para escalar, `iniciar_auditoria`
passa a enfileirar um job (Celery/arq) e o resto não muda.

Guarda-corpo do CLAUDE.md: se uma etapa falhar, tenta mais uma vez; se falhar
de novo, registra o erro no log de eventos e o fluxo segue.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union

from heitor.api import ferramentas, integracao
from heitor.api.estado import estado
from heitor.contrato import Evento, Pendencia

log = logging.getLogger("heitor.execucao")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="auditoria")


class FalhaReauditoria(Exception):
    pass


def com_retentativa(fn: Callable[..., Any], *args: Any) -> Any:
    try:
        return fn(*args)
    except Exception as exc:
        log.warning("%s falhou (%s); tentando de novo", getattr(fn, "__name__", fn), exc)
        return fn(*args)


def emitir_evento(auditoria_id: str, evento: Union[Evento, dict]) -> None:
    """Callback passado ao agente. Aceita Evento ou dict; nunca lança exceção."""
    try:
        if isinstance(evento, dict):
            evento = Evento(**{"auditoria_id": auditoria_id, "ts": datetime.now(), **evento})
        estado.registrar_evento(evento)
    except Exception:
        log.exception("evento inválido descartado: %r", evento)


def _erro(auditoria_id: Optional[str], funcionario_id: Optional[str], etapa: str, exc: Exception) -> None:
    if auditoria_id:
        emitir_evento(auditoria_id, {
            "funcionario_id": funcionario_id, "passo": 0, "tipo": "erro",
            "ferramenta": etapa, "saida": f"{type(exc).__name__}: {exc}",
        })


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------


def iniciar_auditoria(auditoria_id: str, arquivos: list[str]) -> None:
    _executor.submit(rodar_auditoria, auditoria_id, arquivos)


def rodar_auditoria(auditoria_id: str, arquivos: list[str]) -> None:
    token = ferramentas.auditoria_atual.set(auditoria_id)
    try:
        linhas = []
        for arquivo in arquivos:
            try:
                linhas += com_retentativa(integracao.extrair_ficha, arquivo)
            except Exception as exc:
                log.exception("falha ao ler %s", arquivo)
                _erro(auditoria_id, None, f"extrair_ficha({Path(arquivo).name})", exc)
        estado.salvar_linhas(auditoria_id, linhas)

        # Sem retentativa aqui: repetir o agente inteiro duplicaria eventos.
        # A retentativa por ferramenta é responsabilidade do laço do agente.
        achados = integracao.rodar_auditoria(
            auditoria_id, linhas, lambda e: emitir_evento(auditoria_id, e)
        ) or []
        for a in achados:
            estado.salvar_achado(a.model_copy(update={"auditoria_id": a.auditoria_id or auditoria_id}))
        estado.atualizar_auditoria(auditoria_id, status="concluida", concluida_em=datetime.now())
    except Exception as exc:
        log.exception("auditoria %s falhou", auditoria_id)
        _erro(auditoria_id, None, "rodar_auditoria", exc)
        estado.atualizar_auditoria(auditoria_id, status="erro", erro=str(exc), concluida_em=datetime.now())
    finally:
        ferramentas.auditoria_atual.reset(token)


# ---------------------------------------------------------------------------
# Reauditoria (resposta do técnico ou do RH)
# ---------------------------------------------------------------------------


def executar_reauditoria(pendencia_id: str, arquivo: str, nota: Optional[str] = None) -> Pendencia:
    """aberta/reaberta -> aguardando -> (reauditar) -> fechada/reaberta.

    Lança KeyError (não existe), TransicaoInvalida (status errado) ou
    FalhaReauditoria (falhou duas vezes; a pendência volta ao status anterior).
    """
    anterior = estado.obter_pendencia(pendencia_id)
    if anterior is None:
        raise KeyError(pendencia_id)
    p = ferramentas.marcar_aguardando(pendencia_id, nota)
    aud_id, func_id = p.auditoria_id, p.funcionario_id

    token = ferramentas.auditoria_atual.set(aud_id)
    try:
        if aud_id:
            emitir_evento(aud_id, {
                "funcionario_id": func_id, "passo": 1, "tipo": "decisao",
                "entrada": {"pendencia_id": pendencia_id, "arquivo": Path(arquivo).name},
                "saida": "resposta recebida; reauditar com as mesmas regras",
            })
        linhas = com_retentativa(integracao.extrair_ficha, arquivo)
        com_retentativa(integracao.reauditar, pendencia_id, linhas)
    except Exception as exc:
        log.exception("reauditoria da pendência %s falhou", pendencia_id)
        _erro(aud_id, func_id, "reauditar", exc)
        ferramentas.mudar_status(pendencia_id, anterior.status, f"falha na reauditoria: {exc}")
        raise FalhaReauditoria(str(exc)) from exc
    finally:
        ferramentas.auditoria_atual.reset(token)

    p = estado.obter_pendencia(pendencia_id)
    if aud_id:
        emitir_evento(aud_id, {
            "funcionario_id": func_id, "passo": 2, "tipo": "ferramenta", "ferramenta": "reauditar",
            "entrada": {"pendencia_id": pendencia_id, "linhas": len(linhas)},
            "saida": {"status": p.status},
        })
    return p
