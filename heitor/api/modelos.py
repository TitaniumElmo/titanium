"""Modelos que só a API usa. Os modelos compartilhados ficam em heitor/contrato.py."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

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


class ResumoAuditoria(Auditoria):
    """Resposta de GET /auditorias/{id}: o que o painel mostra."""

    contagem_gravidade: dict[str, int]
    contagem_tipo: dict[str, int]
    exposicao_total_rs: float
    pendencias_abertas: int
    passos: int
    custo_total_usd: float


class PendenciaDetalhe(Pendencia):
    """Pendência com o achado que a originou (tela do técnico)."""

    achado: Optional[Achado] = None
