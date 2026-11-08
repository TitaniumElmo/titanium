"""Correção registrada (pela tela ou na planilha) só fecha a pendência se a ENTREGA NOVA vier limpa.

Antes (visto em 08/11 testando o botão "Registrar correção"): uma pendência de CA suspenso fechava quando o técnico
registrava uma bota com CA VENCIDO, porque a reauditoria só olhava se a regra antiga (ca_cancelado) tinha sumido.
"""

import os
from datetime import date

import pytest

os.environ["HEITOR_LLM"] = "off"

from heitor.agente import ferramentas as F  # noqa: E402
from heitor.agente.grafo import reauditar  # noqa: E402
from heitor.dados.caepi import CAMINHO  # noqa: E402

precisa_base = pytest.mark.skipif(not CAMINHO.exists(), reason="CSV do CAEPI não está em dados/")
HOJE = date.today().isoformat()


def _pendencia_de_ca_suspenso():
    achado = {"id": "a-bota", "auditoria_id": "au-corr", "funcionario_id": "0406", "linha": 3, "regra": "ca_cancelado",
              "gravidade": "risco", "tipo": "corrigivel", "evidencia": "linha 3, CA 40754 suspenso na base",
              "acao_sugerida": "revisar o CA e trocar o EPI se preciso"}
    return F.IMPL["criar_pendencia"](achado, "tecnico", "Entregar bota válida ao Wellington", HOJE)


def _bota(ca):
    return [{"funcionario_id": "0406", "nome": "Wellington Prado Silva", "funcao": "servente", "linha": 1, "data": HOJE,
             "epi": "bota de cano longo", "qtd": 1, "ca": ca, "motivo": "T", "assinatura": True, "origem": "correcao.csv"}]


@precisa_base
def test_bota_com_ca_vencido_nao_corrige_ca_suspenso():
    p = _pendencia_de_ca_suspenso()
    r = reauditar(p["id"], _bota("28499"))  # CA vencido desde 02/10/2020
    assert r["status"] == "reaberta"
    assert "outro problema" in r["motivo"]


@precisa_base
def test_bota_com_ca_valido_corrige():
    p = _pendencia_de_ca_suspenso()
    r = reauditar(p["id"], _bota("12844"))
    assert r["status"] == "fechada"
