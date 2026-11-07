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
from heitor.contrato import Achado, Evento, Linha, Pendencia

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
# Adaptadores: o agente pode devolver dicts com mais chaves que o contrato
# ---------------------------------------------------------------------------


def _ler(arquivo: str, auditoria_id: Optional[str], funcionario_id: Optional[str] = None) -> list[Linha]:
    """extrair_ficha devolve list[Linha] ou {"linhas": [...], "mapeamento": ...}."""
    bruto = com_retentativa(integracao.extrair_ficha, arquivo)
    if isinstance(bruto, dict):
        bruto = bruto.get("linhas", [])
    linhas = []
    for item in bruto or []:
        try:
            linhas.append(item if isinstance(item, Linha) else Linha.model_validate(item))
        except Exception as exc:  # linha fora do contrato: avisa no log, não some calada
            _erro(auditoria_id, funcionario_id, f"extrair_ficha({Path(arquivo).name})", exc)
    return linhas


def ler_linhas(arquivo: str) -> list[Linha]:
    """Lê um arquivo de ficha fora de uma auditoria (o vigia). Lança exceção se falhar."""
    return _ler(arquivo, None)


def _achados(resultado: Any, auditoria_id: str) -> list[Achado]:
    """rodar_auditoria devolve list[Achado] ou {"achados": [...], "exposicao": ..., ...}."""
    brutos = resultado.get("achados", []) if isinstance(resultado, dict) else (resultado or [])
    achados = []
    for item in brutos:
        try:
            a = item if isinstance(item, Achado) else Achado.model_validate(item)
        except Exception as exc:
            _erro(auditoria_id, None, "rodar_auditoria (achado fora do contrato)", exc)
            continue
        achados.append(a.model_copy(update={"auditoria_id": a.auditoria_id or auditoria_id}))
    return achados


def _emissor(auditoria_id: str) -> Callable[[Union[Evento, dict]], None]:
    """Callback para o agente. Força o auditoria_id certo (o reauditar da Sofia
    usa um id próprio, "re-p-X", e o evento sumiria do log da auditoria)."""

    def emitir(evento: Union[Evento, dict]) -> None:
        if isinstance(evento, Evento):
            evento = evento.model_copy(update={"auditoria_id": auditoria_id})
        elif isinstance(evento, dict):
            evento = {**evento, "auditoria_id": auditoria_id}
        emitir_evento(auditoria_id, evento)

    return emitir


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------


def em_segundo_plano(fn: Callable[..., Any], *args: Any) -> None:
    _executor.submit(fn, *args)


def iniciar_auditoria(auditoria_id: str, arquivos: list[str]) -> None:
    _executor.submit(rodar_auditoria, auditoria_id, arquivos)


def iniciar_auditoria_linhas(auditoria_id: str, linhas: list[Linha], disparado_por: Optional[str] = None) -> None:
    """Para quem já leu as linhas (o vigia da pasta)."""
    _executor.submit(auditar_linhas, auditoria_id, linhas, disparado_por)


def rodar_auditoria(auditoria_id: str, arquivos: list[str]) -> None:
    linhas = []
    for arquivo in arquivos:
        try:
            linhas += _ler(arquivo, auditoria_id)
        except Exception as exc:
            log.exception("falha ao ler %s", arquivo)
            _erro(auditoria_id, None, f"extrair_ficha({Path(arquivo).name})", exc)
    auditar_linhas(auditoria_id, linhas)


def auditar_linhas(auditoria_id: str, linhas: list[Linha], disparado_por: Optional[str] = None) -> None:
    token = ferramentas.auditoria_atual.set(auditoria_id)
    try:
        if disparado_por:
            emitir_evento(auditoria_id, {
                "passo": 0, "tipo": "decisao",
                "entrada": {"linhas": len(linhas), "funcionarios": sorted({l.funcionario_id for l in linhas})},
                "saida": f"disparado por: {disparado_por}",
            })
        estado.salvar_linhas(auditoria_id, linhas)

        # Sem retentativa aqui: repetir o agente inteiro duplicaria eventos.
        # A retentativa por ferramenta é responsabilidade do laço do agente.
        resultado = integracao.rodar_auditoria(auditoria_id, linhas, _emissor(auditoria_id))
        for a in _achados(resultado, auditoria_id):
            estado.salvar_achado(a)
        extras = {}
        if isinstance(resultado, dict):
            extras = {k: resultado.get(k) for k in ("exposicao", "relatorio", "modo") if resultado.get(k) is not None}
        estado.atualizar_auditoria(auditoria_id, status="concluida", concluida_em=datetime.now(), **extras)
    except Exception as exc:
        log.exception("auditoria %s falhou", auditoria_id)
        _erro(auditoria_id, None, "rodar_auditoria", exc)
        estado.atualizar_auditoria(auditoria_id, status="erro", erro=str(exc), concluida_em=datetime.now())
    finally:
        ferramentas.auditoria_atual.reset(token)


# ---------------------------------------------------------------------------
# Reauditoria (resposta do técnico/RH, ou mudança detectada na pasta)
# ---------------------------------------------------------------------------


def executar_reauditoria(pendencia_id: str, arquivo: str, nota: Optional[str] = None) -> Pendencia:
    """Resposta enviada pela API: lê o arquivo e reaudita."""
    p = estado.obter_pendencia(pendencia_id)
    if p is None:
        raise KeyError(pendencia_id)

    def ler() -> list[Linha]:
        return _ler(arquivo, p.auditoria_id, p.funcionario_id)

    return reauditar_linhas(pendencia_id, ler, nota, origem=Path(arquivo).name)


def reauditar_linhas(
    pendencia_id: str,
    linhas: Union[list[Linha], Callable[[], list[Linha]]],
    nota: Optional[str] = None,
    origem: Optional[str] = None,
) -> Pendencia:
    """aberta/reaberta -> aguardando -> (reauditar) -> fechada/reaberta.

    `linhas` pode ser a lista ou uma função que a lê (a leitura entra na
    retentativa). Lança KeyError (não existe), TransicaoInvalida (status
    errado) ou FalhaReauditoria (falhou duas vezes; a pendência volta ao
    status anterior).
    """
    anterior = estado.obter_pendencia(pendencia_id)
    if anterior is None:
        raise KeyError(pendencia_id)
    p = ferramentas.marcar_aguardando(pendencia_id, nota)
    aud_id, func_id = p.auditoria_id, p.funcionario_id

    token = ferramentas.auditoria_atual.set(aud_id)
    lidas: list[Linha] = []
    try:
        if aud_id:
            emitir_evento(aud_id, {
                "funcionario_id": func_id, "passo": 1, "tipo": "decisao",
                "entrada": {"pendencia_id": pendencia_id, "origem": origem},
                "saida": nota or "resposta recebida; reauditar com as mesmas regras",
            })
        lidas = com_retentativa(linhas) if callable(linhas) else linhas
        emitir = _emissor(aud_id) if aud_id else None
        com_retentativa(integracao.reauditar, pendencia_id, lidas, emitir)
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
            "entrada": {"pendencia_id": pendencia_id, "linhas": len(lidas)},
            "saida": {"status": p.status},
        })
    return p
