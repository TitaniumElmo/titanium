"""Guarda-corpo de fraude: o texto do LLM vai para a tela e para o técnico.

Nunca pedir para assinar, preencher ou alterar um registro antigo (CLAUDE.md, seção 2). Quando o filtro
barra, a ação vira a da regra, que é segura; por isso barrar a mais é aceitável e deixar passar não é.
"""

from datetime import date

import pytest

from heitor.agente.ferramentas import _sugere_fraude

HOJE = date(2026, 11, 8)

FRAUDE = [
    "Colher a assinatura do Rafael na ficha antiga",  # revisão do Pierre
    "Preencher o CA que falta na entrega de setembro/2023",  # revisão do Pierre
    "Pedir ao funcionário que assine as entregas de 2023",
    "Regularizar as entregas anteriores com a assinatura do funcionário",
    "Completar a data que falta na linha 4 da ficha",
    "Alterar a data da entrega de 02/06/2023 para 02/06/2025 na ficha",
    "Assinar retroativamente a ficha de EPI",
    "Obter a assinatura do Wagner na entrega de 12/03/2024",
    "Na ficha antiga, colher a assinatura do Fábio",
    "Preencher a ficha com data anterior",
    "Colher assinatura das entregas passadas do Elias",
    "Incluir o número do CA na linha 7 da ficha de papel",
]

LEGITIMO = [
    "colher a assinatura nas próximas entregas",  # revisão do Pierre
    "entregar hoje e colher a assinatura",  # revisão do Pierre
    # escritas pelo LLM em rodadas reais (fotos_teste/resultados/agente_preventivo_v3.log)
    "Entregar protetor auditivo ao Wellington e colher a assinatura: a última troca foi em 01/12/2025 e a "
    "vida útil é de 90 dias, então ele está sem proteção",
    "Entregar bota de cano longo ao Wellington e colher a assinatura: o CA 40754 está suspenso.",
    "Entregar protetor auditivo ao Elias e colher a assinatura, pois a última troca foi em 20/08/2026",
    "Entregar a luva hoje e colher a assinatura até 10/11/2026",
    "Pedir ao RH a nota fiscal da compra da luva entregue em 12/03/2023",
    "Conferir na ficha de papel se a linha 3 está assinada",
    "Atualizar a planilha com a entrega de 05/03/2024 que está no papel",
    "Colher a assinatura nas próximas entregas; não preencher a ficha antiga",
    # ações das regras (a troca vira uma delas, então não podem ser barradas)
    "colher assinatura nas próximas entregas",
    "conferir a assinatura na ficha física",
    "entregar protetor auditivo, registrar com o CA e colher a assinatura",
    "pedir nota fiscal ao RH",
    "trocar protetor auditivo agora",
    "registrar no relatório (não tem conserto)",
    # conferência montada pelo código (ferramentas.criar_conferencia)
    "conferir na ficha física: linha 3: assinatura em dúvida (lido 'entregue'); linhas 1-2: data lida "
    "2023-06-02, provável 2025-06-02 (entrega em 02/06/2023 é anterior à admissão (02/06/2025))",
]


@pytest.mark.parametrize("texto", FRAUDE)
def test_barra_fraude(texto):
    assert _sugere_fraude(texto, HOJE)


@pytest.mark.parametrize("texto", LEGITIMO)
def test_deixa_passar_acao_legitima(texto):
    assert not _sugere_fraude(texto, HOJE)
