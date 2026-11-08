"""Rotas de leitura que a interface usa para as telas de Funcionários, Cronograma e Relatório."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from heitor.api import configuracoes, seguranca, visoes

router = APIRouter(tags=["visões"])


@router.get("/funcionarios")
def listar_funcionarios() -> list[dict[str, Any]]:
    """Cada funcionário com o status geral (o pior achado em aberto), contagens, última entrega e próxima troca."""
    return visoes.funcionarios()


@router.get("/funcionarios/{funcionario_id}")
def obter_funcionario(funcionario_id: str) -> dict[str, Any]:
    """A ficha de um funcionário: linhas, achados, pendências e trocas previstas."""
    achado = visoes.funcionario(funcionario_id)
    if achado is None:
        raise HTTPException(404, f"funcionário {funcionario_id} não encontrado")
    return achado


@router.get("/cronograma")
def obter_cronograma(
    de: Optional[date] = Query(None, description="padrão: 7 dias atrás"),
    ate: Optional[date] = Query(None, description="padrão: 30 dias à frente"),
) -> list[dict[str, Any]]:
    """Trocas de EPI (vida útil do fabricante), CAs vencendo e prazos de pendência. Treinamento e DDS ainda não."""
    hoje = date.today()
    inicio, fim = de or hoje - timedelta(days=7), ate or hoje + timedelta(days=30)
    if fim < inicio:
        raise HTTPException(422, "`ate` vem antes de `de`")
    return visoes.cronograma(inicio, fim, hoje)


@router.get("/relatorio")
def relatorio_por_periodo(dias: int = Query(30, ge=1, le=365)) -> dict[str, Any]:
    """Resumo dos últimos `dias` dias (7, 30 e 90 são os da tela): série por dia, tipos, pendências, exposição e custo."""
    return visoes.relatorio(dias)


@router.get("/configuracoes", response_model=configuracoes.Configuracao)
def ler_configuracoes() -> configuracoes.Configuracao:
    return configuracoes.atual()


@router.put("/configuracoes", response_model=configuracoes.Configuracao, dependencies=[Depends(seguranca.exigir_admin)])
def ajustar_configuracoes(ajuste: configuracoes.AjusteConfiguracao) -> configuracoes.Configuracao:
    """Muda só os campos enviados. Com HEITOR_TOKEN_ADMIN configurado, exige o token."""
    return configuracoes.ajustar(ajuste)
