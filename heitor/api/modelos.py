"""Modelos que só a API usa. Os modelos compartilhados ficam em heitor/contrato.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from heitor.contrato import Achado, Pendencia

StatusAuditoria = Literal["processando", "concluida", "erro"]


class Auditoria(BaseModel):
    id: str
    status: StatusAuditoria = "processando"
    criada_em: datetime
    concluida_em: Optional[datetime] = None
    arquivos: list[str] = Field(default_factory=list)
    erro: Optional[str] = None
    disparado_por: Optional[str] = None  # alteracao_planilha | prazo_vencido | rotina | manual | upload
    descricao_disparo: Optional[str] = None  # ex.: "mudança na pasta: ficha_0302.csv"
    n_fichas: int = 0  # funcionários (fichas) distintos que entram na auditoria
    n_linhas: int = 0
    # Vindos do resultado de rodar_auditoria (agente), quando ele devolve.
    exposicao: Optional[dict[str, Any]] = None  # {"total_brl", "salario_minimo", ...}
    relatorio: Optional[dict[str, Any]] = None  # {"itens", "texto", ...}
    modo: Optional[str] = None  # "llm" | "misto" (algum funcionário sem LLM) | "deterministico"
    modo_por_funcionario: Optional[dict[str, str]] = None  # funcionário -> "llm" | "degradado" | "deterministico"
    custo_usd: Optional[float] = None  # custo do LLM informado pelo agente (a auditoria toda)


class ResumoAuditoria(Auditoria):
    """Resposta de GET /auditorias/{id}: o que o painel mostra."""

    contagem_gravidade: dict[str, int]
    contagem_tipo: dict[str, int]
    exposicao_total_rs: float
    pendencias_abertas: int
    passos: int
    custo_total_usd: float
    dias_sem_epi_valido_registrado: dict[str, int] = Field(default_factory=dict)  # funcionário -> dias; ausente = 0


class PendenciaDetalhe(Pendencia):
    """Pendência com o achado que a originou (tela do técnico)."""

    achado: Optional[Achado] = None
