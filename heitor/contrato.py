"""Contrato JSON entre os módulos (seção 7 do CLAUDE.md).

Os objetos circulam como dicts simples; os TypedDicts abaixo só documentam
os campos e ajudam o editor. Mudou algo aqui? Avise o time antes.
"""

from __future__ import annotations

from typing import Any, Callable, Literal, Optional, TypedDict

Gravidade = Literal["irregular", "risco", "ok"]
Tipo = Literal["corrigivel", "prova", "passivo"]
Destino = Literal["tecnico", "rh"]
Status = Literal["aberta", "aguardando", "fechada", "reaberta"]

GRAVIDADES: tuple[str, ...] = ("irregular", "risco", "ok")
TIPOS: tuple[str, ...] = ("corrigivel", "prova", "passivo")
DESTINOS: tuple[str, ...] = ("tecnico", "rh")
STATUS: tuple[str, ...] = ("aberta", "aguardando", "fechada", "reaberta")


class Linha(TypedDict, total=False):
    funcionario_id: str
    nome: str
    funcao: str
    linha: int
    data: Optional[str]  # AAAA-MM-DD
    epi: Optional[str]
    qtd: Optional[int]
    ca: Optional[str]
    motivo: Optional[str]
    assinatura: Optional[bool]
    confianca: dict[str, float]
    origem: str


class Achado(TypedDict, total=False):
    id: str
    funcionario_id: str
    linha: Optional[int]
    regra: str
    gravidade: Gravidade
    tipo: Tipo
    evidencia: str
    acao_sugerida: str


class Pendencia(TypedDict, total=False):
    id: str
    achado_id: str
    destino: Destino
    acao: str
    prazo: str  # AAAA-MM-DD
    status: Status
    historico: list[dict[str, Any]]


class Evento(TypedDict, total=False):
    auditoria_id: str
    passo: int
    ferramenta: str
    entrada: dict[str, Any]
    saida: Any
    custo_usd: float
    ts: str
    # Campos extras do agente (opcionais para a interface):
    funcionario_id: Optional[str]
    pensamento: Optional[str]


EmitirEvento = Callable[[Evento], None]
