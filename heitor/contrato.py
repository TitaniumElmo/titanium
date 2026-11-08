"""Contrato de dados do Heitor (CLAUDE.md, seção 7).

Todos os módulos importam daqui:

    from heitor.contrato import Linha, Achado, Pendencia, Evento

Campos marcados com `# PROPOSTA` ainda não estão no CLAUDE.md e precisam
da aprovação do time. Os valores fechados (Literal) não devem ser alterados
sem avisar todo mundo: a interface depende deles.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Valores fechados
# ---------------------------------------------------------------------------

Gravidade = Literal["irregular", "risco", "ok"]
TipoAchado = Literal["corrigivel", "prova", "passivo"]
Destino = Literal["tecnico", "rh"]
StatusPendencia = Literal["aberta", "aguardando", "fechada", "reaberta"]

# PROPOSTA: lista fechada de regras, para a interface mostrar rótulos amigáveis.
Regra = Literal[
    "assinatura_ausente",
    "ca_ausente",
    "ca_vencido",
    "ca_nao_encontrado",
    "ca_cancelado",  # CANCELADO ou SUSPENSO na base CAEPI
    "ca_conflitante",  # número repetido com dados que discordam
    "epi_inadequado",  # EPI exigido ausente ou de categoria errada
    "troca_atrasada",  # intervalo maior que a vida útil do fabricante
    "treinamento_ausente",
    # O agente usa quando não consegue decidir; viram pendência de revisão.
    "falha_de_ferramenta",  # ferramenta falhou duas vezes
    "funcao_desconhecida",  # função fora da tabela função -> EPI
    # Ficha de papel conferida contra a planilha (decisão do time: sempre risco, nunca irregular).
    "entrega_sem_ficha",  # está na planilha e não no papel
    "ficha_sem_planilha",  # está no papel e não na planilha
    "leitura_incerta",  # CA, data ou assinatura em dúvida na foto: conferir na ficha física
]

# PROPOSTA: separa chamada de ferramenta, decisão do LLM e falha no log.
TipoEvento = Literal["ferramenta", "decisao", "erro"]


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class Linha(BaseModel):
    """Uma linha da ficha de EPI depois de lida (CSV ou foto)."""

    funcionario_id: str  # texto, para manter zeros à esquerda ("0302")
    nome: str
    funcao: str
    linha: int  # número da linha no arquivo de origem
    data: Optional[date] = None  # data da entrega; None se não foi possível ler
    epi: str
    qtd: int = 1
    ca: Optional[str] = None  # número do CA como texto; None se vazio na ficha
    motivo: Optional[str] = None  # códigos a definir (ex.: T = troca)
    assinatura: Optional[bool] = None  # None se não foi possível ler
    confianca: dict[str, float] = Field(default_factory=dict)  # 0 a 1, por campo
    origem: str  # arquivo de onde a linha veio


class Achado(BaseModel):
    """Um problema encontrado. Só `audita_linha` produz achados."""

    id: str
    auditoria_id: Optional[str] = None  # PROPOSTA
    funcionario_id: str
    linha: Optional[int] = None  # PROPOSTA: None quando vale para o funcionário (ex.: treinamento)
    regra: Regra
    gravidade: Gravidade
    tipo: TipoAchado
    evidencia: str
    acao_sugerida: str
    norma: Optional[str] = None  # PROPOSTA: súmula/NR citada no relatório
    exposicao_rs: Optional[float] = None  # PROPOSTA: só para tipo "passivo"


class HistoricoPendencia(BaseModel):
    """Uma mudança de status da pendência."""  # PROPOSTA

    status: StatusPendencia
    ts: datetime
    nota: Optional[str] = None


class Pendencia(BaseModel):
    """Tarefa para o técnico (corrigir) ou para o RH (enviar documento)."""

    id: str
    achado_id: str
    auditoria_id: Optional[str] = None  # PROPOSTA: filtro de GET /pendencias
    funcionario_id: Optional[str] = None  # PROPOSTA: tela do técnico
    destino: Destino
    acao: str
    motivo: Optional[str] = None  # PROPOSTA: por que a pendência existe
    prazo: date
    status: StatusPendencia = "aberta"
    historico: list[HistoricoPendencia] = Field(default_factory=list)


class Evento(BaseModel):
    """Um passo do agente, para o log ao vivo e o rastro auditável."""

    auditoria_id: str
    funcionario_id: Optional[str] = None  # PROPOSTA: um episódio por funcionário
    passo: int
    tipo: TipoEvento = "ferramenta"  # PROPOSTA
    ferramenta: Optional[str] = None  # None quando tipo = "decisao"
    entrada: dict[str, Any] = Field(default_factory=dict)
    saida: Any = None
    custo_usd: float = 0.0
    ts: datetime
