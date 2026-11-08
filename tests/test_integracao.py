"""API + agente real da Sofia (sem LLM). Os dados do Gustavo ainda são stubs dela.

O conftest força os stubs da API; aqui cada teste troca as funções da
integração pelas reais do agente.
"""

import pytest

from heitor.agente import extracao, grafo, relatorio
from heitor.agente import ferramentas as ferramentas_agente
from heitor.api import config, integracao
from heitor.api.estado import estado
from heitor.dados.caepi import CAMINHO
from tests.test_api import esperar, responder

# O agente real chama as regras reais do Gustavo, que precisam da base CAEPI em dados/.
precisa_base = pytest.mark.skipif(not CAMINHO.exists(), reason="base CAEPI não está em dados/ (RelatorioCA_*.csv)")

CORRECAO_0302 = config.PASTA_EXEMPLOS / "correcao_0302.csv"


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("HEITOR_LLM", "off")
    monkeypatch.setattr(integracao, "extrair_ficha", extracao.extrair_ficha)
    monkeypatch.setattr(integracao, "rodar_auditoria", grafo.rodar_auditoria)
    monkeypatch.setattr(integracao, "reauditar", grafo.reauditar)
    monkeypatch.setattr(integracao, "gerar_relatorio", relatorio.gerar_relatorio)


def test_agente_usa_as_ferramentas_da_api():
    for nome in ("criar_pendencia", "fechar_pendencia", "obter_pendencia"):
        assert ferramentas_agente.ORIGEM[nome] == f"heitor.api.ferramentas.{nome}"


def _auditar(client):
    r = client.post("/auditorias", data={"exemplo": "true"})
    return esperar(client, r.json()["id"], limite_s=30)


def _pendencia_epi(client, aud_id, funcionario_id):
    for p in client.get("/pendencias", params={"auditoria_id": aud_id, "funcionario_id": funcionario_id}).json():
        d = client.get(f"/pendencias/{p['id']}").json()
        if d["achado"]["regra"] == "epi_inadequado" and "protetor auditivo" in d["achado"]["evidencia"]:
            return d
    raise AssertionError("sem pendência de protetor auditivo")


@precisa_base
def test_auditoria_com_agente_real(client, real):
    resumo = _auditar(client)
    assert resumo["status"] == "concluida", resumo["erro"]
    assert resumo["modo"] == "deterministico"
    assert resumo["pendencias_abertas"] > 0  # criadas pelo agente na API, não no stub dele
    assert resumo["exposicao_total_rs"] > 0  # veio de calcula_exposicao
    assert resumo["passos"] > 0

    rel = client.get(f"/auditorias/{resumo['id']}/relatorio").json()
    assert rel["texto"] and rel["itens"]


@precisa_base
def test_reauditoria_com_agente_real(client, real):
    aud = _auditar(client)
    p = _pendencia_epi(client, aud["id"], "0302")

    r = responder(client, p["id"], config.FICHA_EXEMPLO)  # nada mudou
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "reaberta"

    r = responder(client, p["id"], CORRECAO_0302)  # protetor auditivo entregue hoje
    assert r.json()["status"] == "fechada"

    # Os eventos do reauditar entram no log da própria auditoria.
    eventos = estado.eventos_desde(aud["id"])
    assert any(e.ferramenta == "fechar_pendencia" for e in eventos)

