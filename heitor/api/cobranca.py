"""Gatilho 2: pendência com prazo vencido é cobrada pelo Heitor.

A cada ciclo do vigia, para cada pendência aberta ou reaberta cujo prazo já
passou: soma uma cobrança, registra no histórico (etapa cobrar_atraso), emite o
evento "cobrar_atraso" e reenvia o aviso ao destino. Na 2ª cobrança a pendência
é escalada (prioridade alta) e o aviso vai também ao coordenador
(HEITOR_EMAIL_COORDENADOR; sem ele, só registra). No máximo uma cobrança por dia.

HEITOR_PRAZO_TESTE=N adianta o relógio da cobrança em N dias (ensaio e testes):
com N=10, pendência com prazo em até 10 dias já conta como vencida; para ensaiar
a 2ª cobrança, aumente N (cada valor novo é "outro dia").
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta
from typing import Optional

from heitor.api import execucao
from heitor.api.estado import estado
from heitor.api.notificacao import notificar
from heitor.contrato import HistoricoPendencia, Pendencia

log = logging.getLogger("heitor.cobranca")

COBRANCAS_PARA_ESCALAR = 2
_DIA_DA_COBRANCA = re.compile(r"hoje=(\d{4}-\d{2}-\d{2})")


class _JaCobrada(Exception):
    pass


def hoje() -> date:
    adiantar = os.getenv("HEITOR_PRAZO_TESTE", "").strip()
    return date.today() + timedelta(days=int(adiantar)) if adiantar.lstrip("-").isdigit() else date.today()


def _cobrada_em(p: Pendencia) -> Optional[date]:
    for h in reversed(p.historico):
        if h.etapa == "cobrar_atraso":
            achou = _DIA_DA_COBRANCA.search(h.nota or "")
            return date.fromisoformat(achou.group(1)) if achou else h.ts.date()
    return None


def _vencida(p: Pendencia, dia: date) -> bool:
    return p.status in ("aberta", "reaberta") and p.prazo < dia and _cobrada_em(p) != dia


def cobrar_atrasadas(dia: Optional[date] = None) -> list[dict]:
    dia = dia or hoje()
    feitas = []
    for p in estado.listar_pendencias():
        if not _vencida(p, dia):
            continue

        def cobrar(atual: Pendencia) -> None:
            if not _vencida(atual, dia):
                raise _JaCobrada()
            atual.cobrancas += 1
            if atual.cobrancas >= COBRANCAS_PARA_ESCALAR:
                atual.escalada, atual.prioridade = True, "alta"
            atual.historico.append(HistoricoPendencia(
                status=atual.status, ts=datetime.now(), nota=f"cobrança {atual.cobrancas} (hoje={dia.isoformat()})",
                etapa="cobrar_atraso", ator="agente",
            ))

        try:
            nova = estado.atualizar_pendencia(p.id, cobrar)
        except _JaCobrada:
            continue
        dados = {"pendencia_id": nova.id, "cobrancas": nova.cobrancas, "escalada": nova.escalada}
        if nova.auditoria_id:
            execucao.emitir_evento(nova.auditoria_id, {
                "funcionario_id": nova.funcionario_id, "passo": 0, "tipo": "ferramenta",
                "ferramenta": "cobrar_atraso", "entrada": dict(dados), "saida": dict(dados),
            })
        achado = estado.obter_achado(nova.achado_id, nova.auditoria_id)
        notificar(nova, acao_da_regra=achado.acao_sugerida if achado else None,
                  cobranca=nova.cobrancas, coordenador=nova.escalada)
        feitas.append(dados)
    return feitas
