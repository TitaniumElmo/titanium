"""Tipos internos do agente.

Dentro do agente os objetos circulam como dicts com os MESMOS campos do
contrato (heitor/contrato.py, do Pierre). A conversão para os modelos
Pydantic acontece só na fronteira: grafo.rodar_auditoria e grafo.reauditar.
"""

from __future__ import annotations

from typing import Any, Callable, get_args

from heitor.contrato import Evento, Regra

LinhaDict = dict[str, Any]
AchadoDict = dict[str, Any]
PendenciaDict = dict[str, Any]

EmitirEvento = Callable[[Evento], None]

REGRAS_DO_CONTRATO: frozenset[str] = frozenset(get_args(Regra))

# PROPOSTA ao Pierre: incluir no Literal Regra. O agente usa quando não consegue decidir.
REGRAS_PROPOSTAS: frozenset[str] = frozenset({"falha_de_ferramenta", "funcao_desconhecida"})
