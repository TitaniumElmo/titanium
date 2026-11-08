"""Configurações que a tela de Configurações mostra e o time pode ajustar.

Ficam em memória (reiniciar o servidor volta aos padrões). Hoje têm efeito real:
- `intervalo_leitura_s`: passa direto para o vigia da pasta;
- `antecedencia_troca_dias`: quanto antes o cronograma mostra uma troca de EPI.
`prazo_padrao_dias` e `canal_aviso` ficam guardados e aparecem na tela, mas o agente ainda
escolhe o prazo sozinho e o canal vem do .env (e-mail); ligá-los é um passo à parte.
"""

from __future__ import annotations

import threading

from pydantic import BaseModel, Field

from heitor.api import vigia as modulo_vigia


class Configuracao(BaseModel):
    canal_aviso: str = "E-mail"
    prazo_padrao_dias: int = Field(5, ge=1, le=30)
    antecedencia_troca_dias: int = Field(15, ge=1, le=60)
    intervalo_leitura_s: float = Field(10, ge=3, le=300)


class AjusteConfiguracao(BaseModel):
    """Só os campos enviados mudam."""

    canal_aviso: str | None = None
    prazo_padrao_dias: int | None = Field(None, ge=1, le=30)
    antecedencia_troca_dias: int | None = Field(None, ge=1, le=60)
    intervalo_leitura_s: float | None = Field(None, ge=3, le=300)


_trava = threading.Lock()
_atual = Configuracao()


def atual() -> Configuracao:
    with _trava:
        v = modulo_vigia.vigia
        copia = _atual.model_copy()
        if v is not None:
            copia.intervalo_leitura_s = v.intervalo_s
        return copia


def ajustar(ajuste: AjusteConfiguracao) -> Configuracao:
    global _atual
    campos = ajuste.model_dump(exclude_none=True)
    with _trava:
        _atual = Configuracao(**{**_atual.model_dump(), **campos})
        if "intervalo_leitura_s" in campos and modulo_vigia.vigia is not None:
            modulo_vigia.vigia.intervalo_s = float(campos["intervalo_leitura_s"])
    return atual()


def restaurar() -> None:
    global _atual
    with _trava:
        _atual = Configuracao()
