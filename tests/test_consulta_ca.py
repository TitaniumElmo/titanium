from datetime import date

import pytest

from heitor.dados.caepi import CAMINHO, consulta_ca, resolver_ca

precisa_base = pytest.mark.skipif(not CAMINHO.exists(), reason="CSV do CAEPI não está em dados/")


@precisa_base
def test_ca_valido():
    r = consulta_ca("448", date(2026, 11, 7))
    assert r["encontrado"] and r["valido_na_data"] and not r["conflito"]


@precisa_base
def test_valido_no_proprio_dia_da_validade():
    r = consulta_ca("448", "17/11/2029")
    assert r["valido_na_data"]


@precisa_base
def test_vencido_na_entrega():
    r = consulta_ca("25", date(2026, 11, 7))
    assert r["encontrado"] and not r["valido_na_data"]


@precisa_base
def test_vencido_so_depois_da_entrega_ainda_vale():
    assert consulta_ca("448", "01/01/2029")["valido_na_data"]
    assert not consulta_ca("448", "18/11/2029")["valido_na_data"]


@precisa_base
def test_nao_existe():
    r = consulta_ca("99999999", date(2026, 11, 7))
    assert r["encontrado"] is False and "valido_na_data" not in r and r["numero"] == "99999999"


@precisa_base
def test_conflitante_7536():
    r = consulta_ca("7536", date(2026, 11, 7))
    assert r["conflito"] and r["validade"] == "2027-10-08"
    assert r["valido_na_data"]


@precisa_base
def test_cancelado_com_validade_futura_e_invalido():
    r = consulta_ca("33295", date(2026, 11, 7))
    assert r["situacao"] == "CANCELADO"
    assert r["validade"] >= "2026-11-07"
    assert not r["valido_na_data"]


@precisa_base
def test_suspenso_e_invalido():
    assert not consulta_ca("40754", date(2026, 11, 7))["valido_na_data"]


def _l(validade, situacao):
    return {"NR Registro CA": "1", "DATA DE VALIDADE": validade, "SITUACAO": situacao, "EQUIPAMENTO": "X"}


def test_empate_de_validade_escolhe_pior_situacao():
    ordem = ["VÁLIDO", "VENCIDO", "SUSPENSO", "CANCELADO"]
    for i in range(1, len(ordem)):
        linhas = [_l("01/01/2030", ordem[i]), _l("01/01/2030", ordem[0])]
        assert resolver_ca(linhas)["registro"]["SITUACAO"] == ordem[i]
        assert resolver_ca(linhas[::-1])["registro"]["SITUACAO"] == ordem[i]
    r = resolver_ca([_l("01/01/2030", "SUSPENSO"), _l("01/01/2030", "CANCELADO"), _l("01/01/2030", "VENCIDO")])
    assert r["registro"]["SITUACAO"] == "CANCELADO" and r["conflito"]


def test_validade_maior_ainda_vence_o_desempate():
    r = resolver_ca([_l("01/01/2031", "VÁLIDO"), _l("01/01/2030", "CANCELADO")])
    assert r["registro"]["SITUACAO"] == "VÁLIDO"


CHAVES_STUB_ENCONTRADO = {"numero", "encontrado", "valido_na_data", "validade", "situacao", "equipamento", "conflito"}


@precisa_base
def test_formato_igual_ao_stub():
    r = consulta_ca("448", "2026-11-07")
    assert set(r) - {"motivo"} == CHAVES_STUB_ENCONTRADO
    assert r["numero"] == "448" and r["validade"] == "2029-11-17"
    assert isinstance(r["validade"], str) and isinstance(r["valido_na_data"], bool)
    assert set(consulta_ca("99999999", "2026-11-07")) - {"motivo"} == {"numero", "encontrado"}
