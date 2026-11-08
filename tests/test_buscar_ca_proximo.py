from datetime import date

import pytest

from heitor.dados.caepi import CAMINHO, buscar_ca_proximo, consulta_ca, distancia_edicao

pytestmark = pytest.mark.skipif(not CAMINHO.exists(), reason="CSV do CAEPI não está em dados/")

CERTO = "17664"  # protetor auditivo, válido até 2031
HOJE = date(2026, 11, 7)


def inexistente(numero):
    assert not consulta_ca(numero, HOJE)["encontrado"], f"{numero} existe na base; troque o caso do teste"
    return numero


def numeros(sugestoes):
    return [s["numero"] for s in sugestoes]


def test_distancia_de_edicao():
    assert distancia_edicao("17664", "17664", 2) == 0
    assert distancia_edicao("17664", "17669", 2) == 1
    assert distancia_edicao("17664", "1764", 2) == 1
    assert distancia_edicao("17664", "176640", 2) == 1
    assert distancia_edicao("17664", "99999", 2) == 3


def test_digito_trocado_acha_o_ca_certo():
    r = buscar_ca_proximo(inexistente("27664"))
    assert CERTO in numeros(r) and r[0]["distancia"] == 1


def test_digito_a_mais_acha_o_ca_certo():
    assert CERTO in numeros(buscar_ca_proximo(inexistente("117664")))


def test_digito_a_menos_acha_o_ca_certo():
    assert CERTO in numeros(buscar_ca_proximo(inexistente("7664")))


def test_formato_e_ordem_das_sugestoes():
    r = buscar_ca_proximo(inexistente("27664"))
    assert set(r[0]) == {"numero", "equipamento", "validade", "situacao", "distancia", "confianca"}
    assert r[0]["numero"] == CERTO and r[0]["equipamento"] == "PROTETOR AUDITIVO" and r[0]["validade"] == "2031-06-16"
    chaves = [(s["distancia"], [-int(x) for x in s["validade"].split("-")]) for s in r]
    assert chaves == sorted(chaves)


def test_ca_que_existe_devolve_vazio():
    assert consulta_ca(CERTO, HOJE)["encontrado"]
    assert buscar_ca_proximo(CERTO) == []
    assert buscar_ca_proximo(" 0" + CERTO + " ") == []


def test_entrada_invalida_devolve_vazio():
    for ruim in (None, "", "   ", "abc", "17x64", "0", "00"):
        assert buscar_ca_proximo(ruim) == [], ruim


def test_confianca_sempre_baixa():
    for digitado in ("27664", "117664", "7664", "1764"):
        r = buscar_ca_proximo(inexistente(digitado))
        assert r and all(s["confianca"] == "baixa" for s in r)


def test_maximo_de_5_resultados():
    r = buscar_ca_proximo(inexistente("1764"))
    assert len(r) == 5


def test_sem_vizinho_a_distancia_1_tenta_distancia_2():
    r = buscar_ca_proximo(inexistente("9917664"))
    assert numeros(r) == [CERTO] and r[0]["distancia"] == 2


def test_sem_nada_ate_distancia_2_devolve_vazio():
    assert buscar_ca_proximo(inexistente("99999999")) == []
