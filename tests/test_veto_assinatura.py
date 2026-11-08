"""Veto de assinatura: um modelo diferente só pode TIRAR uma assinatura (vira conferência), nunca aceitar.

Motivo (08/11): na ficha do Fábio, a linha 2 em branco entre linhas assinadas foi aceita como assinada em 2 de 16
rodadas; as perguntas A e B usam o mesmo modelo e erravam juntas. Com o veto: 0 de 10.
"""

from heitor.agente.conferencia_assinaturas import CONF_DISCORDA, aplicar_veto


def _linha(n, assinatura, conf):
    return {"linha": n, "assinatura": assinatura, "confianca": {"assinatura": conf}, "leitura_assinatura": {}}


def test_veto_tira_assinatura_que_o_outro_modelo_le_em_branco():
    linhas = [_linha(1, True, 0.95), _linha(2, True, 0.95)]
    assert aplicar_veto(linhas, ["Fábio", "vazio"]) == [2]
    assert linhas[0]["assinatura"] is True
    assert linhas[1]["assinatura"] is False and linhas[1]["confianca"]["assinatura"] == CONF_DISCORDA
    assert linhas[1]["leitura_assinatura"]["veto"] == "vazio"


def test_veto_nunca_aceita_assinatura():
    linhas = [_linha(1, False, 0.95), _linha(2, None, 0.0), _linha(3, False, 0.4)]
    assert aplicar_veto(linhas, ["Fábio", "Fábio", "Fábio"]) == []
    assert [l["assinatura"] for l in linhas] == [False, None, False]


def test_veto_sem_leitura_nao_muda_nada():
    linhas = [_linha(1, True, 0.95)]
    assert aplicar_veto(linhas, [None]) == [] and linhas[0]["assinatura"] is True
