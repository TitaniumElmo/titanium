"""Ponto único onde a API pega as funções dos outros módulos.

Tenta importar o código real da Sofia (heitor.agente) e do Gustavo
(heitor.dados). O que não existir ainda vem de `stubs.py`. Quando o código
real chegar, basta reiniciar o servidor: a API não muda.

GET /health mostra o que está real e o que ainda é stub.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from heitor.api import config, stubs

log = logging.getLogger("heitor.integracao")

origem: dict[str, str] = {}  # nome da função -> "modulo.real" ou "stub"


def _resolver(nome: str, modulos: tuple[str, ...]) -> Callable[..., Any]:
    if not config.FORCAR_STUBS:
        for modulo in modulos:
            try:
                fn = getattr(importlib.import_module(modulo), nome)
            except ModuleNotFoundError as exc:
                if exc.name and modulo.startswith(exc.name):
                    continue  # o módulo ainda não existe: normal
                log.exception("erro ao importar %s; usando stub de %s", modulo, nome)
                break
            except AttributeError:
                continue
            except Exception:
                log.exception("erro ao importar %s; usando stub de %s", modulo, nome)
                break
            origem[nome] = f"{modulo}.{nome}"
            return fn
    origem[nome] = "stub"
    return getattr(stubs, nome)


extrair_ficha = _resolver("extrair_ficha", ("heitor.agente.extracao", "heitor.agente"))
rodar_auditoria = _resolver("rodar_auditoria", ("heitor.agente.grafo", "heitor.agente"))
reauditar = _resolver("reauditar", ("heitor.agente.grafo", "heitor.agente"))
gerar_relatorio = _resolver("gerar_relatorio", ("heitor.agente.relatorio", "heitor.agente"))
consulta_ca = _resolver("consulta_ca", ("heitor.dados.caepi", "heitor.dados"))

log.info("integração: %s", origem)
