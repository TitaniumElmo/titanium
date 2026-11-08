import pytest

from heitor.dados.caepi import base_mais_recente, consulta_ca, validade_do_ca

pytestmark = pytest.mark.skipif(not base_mais_recente().exists(), reason="CSV do CAEPI não está em dados/")


def test_ca_existente_devolve_validade_sem_precisar_de_data():
    r = validade_do_ca("17664")
    assert r["encontrado"] and r["validade"] == "2031-06-16"
    assert r["situacao"] == "VÁLIDO" and r["situacao_invalida"] is False
    assert "PROTETOR AUDITIVO" in r["equipamento"].upper()


def test_mesma_validade_que_consulta_ca():
    assert validade_do_ca("29637")["validade"] == consulta_ca("29637", "2026-02-10")["validade"]


def test_ca_inexistente():
    r = validade_do_ca("99999999")
    assert r["encontrado"] is False


def test_ca_cancelado_marca_situacao_invalida():
    r = validade_do_ca("28499")
    assert r["encontrado"]
    ca = consulta_ca("28499", "2020-01-01")
    assert r["situacao_invalida"] == (ca["situacao"].upper() in ("CANCELADO", "SUSPENSO"))
