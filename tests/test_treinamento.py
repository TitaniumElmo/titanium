"""Campo de treinamento da ficha de papel: só o campo que existe e está em branco vira achado.

Medido em 14 fotos (08/11): 3 de 5 campos vazios pegos, nenhum campo preenchido lido como vazio.
"""

import os

os.environ["HEITOR_LLM"] = "off"

import pytest  # noqa: E402

from heitor.agente import conferencia_assinaturas as CA  # noqa: E402
from heitor.agente import grafo  # noqa: E402
from heitor.agente.foto import interpretar_treinamento  # noqa: E402
from tests.test_contrato_agente import stubs_de_dados  # noqa: E402

LINHAS = [{"funcionario_id": "0310", "nome": "Fábio Nogueira Pires", "funcao": "servente", "linha": 1,
           "data": "2026-08-10", "epi": "protetor auricular plug", "qtd": 1, "ca": "17664", "motivo": "T",
           "assinatura": None, "origem": "planilha"}]


def _assinaturas_ok(_foto, do_func):
    r = [dict(l, assinatura=True, assinatura_tipo="nome_confere", assinatura_texto="Fábio", na_ficha=True,
              confianca={"assinatura": 0.95}) for l in do_func]
    return {"linhas": r, "fora_da_planilha": [], "custo_usd": 0.0}


def _auditar(monkeypatch, treinamento):
    monkeypatch.setattr(CA, "conferir_assinaturas", _assinaturas_ok)
    if isinstance(treinamento, Exception):
        def falha(_foto):
            raise treinamento
        monkeypatch.setattr(CA, "ler_treinamento", falha)
    else:
        monkeypatch.setattr(CA, "ler_treinamento", lambda _foto: {**treinamento, "custo_usd": 0.001})
    with stubs_de_dados():
        return grafo.conferir_e_auditar("au-trein", [dict(l) for l in LINHAS], {"0310": "ficha.jpg"})


def test_campo_vazio_vira_risco_e_pede_lista_de_presenca_ao_rh(monkeypatch):
    r = _auditar(monkeypatch, {"estado": "vazio", "data": None})
    trein = [a for a in r["achados"] if a["regra"] == "treinamento_ausente"]
    assert len(trein) == 1 and trein[0]["gravidade"] == "risco" and trein[0]["tipo"] == "prova"
    pend = [p for p in r["pendencias"] if p["achado_id"] == trein[0]["id"]]
    assert pend and pend[0]["destino"] == "rh"


@pytest.mark.parametrize("estado", [{"estado": "ok", "data": "2025-09-02"}, {"estado": "sem_campo", "data": None},
                                    {"estado": "ilegivel", "data": None}])
def test_campo_preenchido_sem_campo_ou_ilegivel_nao_acusa(monkeypatch, estado):
    r = _auditar(monkeypatch, estado)
    assert not any(a["regra"] == "treinamento_ausente" for a in r["achados"])


def test_falha_na_leitura_do_treinamento_nao_derruba_a_conferencia(monkeypatch):
    r = _auditar(monkeypatch, TimeoutError("visão fora do ar"))
    assert not any(a["regra"] == "treinamento_ausente" for a in r["achados"])
    assert not any(a["regra"] == "falha_de_ferramenta" for a in r["achados"])


@pytest.mark.parametrize("resposta, estado", [
    ({"tem_rotulo": False, "tem_escrita_a_mao": False, "data": None}, "sem_campo"),
    ({"tem_rotulo": True, "tem_escrita_a_mao": False, "data": "03/04/2023"}, "vazio"),  # o Rafael: data inventada
    ({"tem_rotulo": True, "tem_escrita_a_mao": True, "data": "02/09/2025"}, "ok"),
    ({"tem_rotulo": True, "tem_escrita_a_mao": True, "data": "ilegivel"}, "ilegivel"),
])
def test_interpretar_resposta_do_modelo(resposta, estado):
    assert interpretar_treinamento(resposta)["estado"] == estado
