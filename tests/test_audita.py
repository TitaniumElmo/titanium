from datetime import date

import pytest

from heitor.contrato import Linha
from heitor.dados.caepi import CAMINHO
from heitor.dados.regras import audita_funcionario, audita_linha

HOJE = date(2026, 11, 7)

precisa_base = pytest.mark.skipif(not CAMINHO.exists(), reason="CSV do CAEPI não está em dados/")


def L(n, epi, d, ca=None, fid="0302"):
    return Linha(funcionario_id=fid, nome="X", funcao="armador", linha=n, data=d, epi=epi, ca=ca, origem="t", assinatura=True)


def regras(achados):
    return sorted(a.regra for a in achados)


@precisa_base
def test_ficha_ok():
    ls = [L(1, "protetor auditivo", date(2026, 10, 1), "17664"), L(2, "luva", date(2026, 11, 1), "21245")]
    assert audita_funcionario(ls, "armador", hoje=HOJE) == []


@precisa_base
def test_funcionario_nao_repete_achados_de_ca():
    ls = [L(1, "luva", date(2026, 11, 1), "25"), L(2, "protetor auditivo", date(2026, 10, 1))]
    assert audita_funcionario(ls, "armador", hoje=HOJE) == []


@precisa_base
def test_linha_ca_vencido_na_entrega():
    a = audita_linha(L(1, "botina", date(2026, 10, 1), "25"), "armador")
    assert regras(a) == ["ca_vencido"] and a[0].gravidade == "risco" and a[0].tipo == "prova"


@precisa_base
def test_linha_ca_cancelado_e_nao_encontrado():
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "33295"), "armador")) == ["ca_cancelado"]
    assert regras(audita_linha(L(2, "luva", date(2026, 11, 1), "99999999"), "armador")) == ["ca_nao_encontrado"]


@precisa_base
def test_linha_ca_conflitante():
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "7536"), "armador")) == ["ca_conflitante"]


@precisa_base
def test_linha_ok():
    assert audita_linha(L(1, "luva", date(2026, 11, 1), "21245", ), "armador") == []


@precisa_base
def test_linha_assinatura_ausente():
    l = L(1, "luva", date(2026, 11, 1), "21245")
    l.assinatura = False
    a = audita_linha(l, "armador")
    assert regras(a) == ["assinatura_ausente"] and a[0].gravidade == "irregular" and a[0].tipo == "passivo"


def _assina(assinatura, confianca=None):
    l = L(1, "luva", date(2026, 11, 1), "21245")
    l.assinatura = assinatura
    if confianca is not None:
        l.confianca = {"assinatura": confianca}
    return l


@precisa_base
def test_assinatura_none_vira_risco_prova():
    a = audita_linha(_assina(None), "armador")
    assert regras(a) == ["assinatura_ausente"]
    assert (a[0].gravidade, a[0].tipo) == ("risco", "prova")
    assert a[0].evidencia == "linha 1, assinatura não identificada na leitura"
    assert a[0].acao_sugerida == "conferir a assinatura na ficha física"


@precisa_base
def test_assinatura_none_mostra_a_confianca():
    a = audita_linha(_assina(None, 0.4), "armador")
    assert a[0].evidencia == "linha 1, assinatura incerta na leitura (confiança 0.40)"


@precisa_base
def test_assinatura_false_com_confianca_baixa_vira_risco_prova():
    a = audita_linha(_assina(False, 0.69), "armador")
    assert (a[0].gravidade, a[0].tipo) == ("risco", "prova") and "confiança 0.69" in a[0].evidencia


@precisa_base
def test_assinatura_false_com_confianca_no_limite_ou_sem_confianca_e_passivo():
    for conf in (0.7, 0.95, None):
        a = audita_linha(_assina(False, conf), "armador")
        assert regras(a) == ["assinatura_ausente"] and (a[0].gravidade, a[0].tipo) == ("irregular", "passivo")


@precisa_base
def test_assinatura_true_nao_acusa():
    assert audita_linha(_assina(True, 0.1), "armador") == []


def test_linha_ca_ausente():
    for vazio in (None, "", "  "):
        a = audita_linha(L(1, "luva", date(2026, 11, 1), vazio), "armador")
        assert regras(a) == ["ca_ausente"] and a[0].tipo == "prova"


def test_epi_ausente_e_inadequado():
    ls = [L(1, "protetor auditivo", date(2026, 10, 1)), L(2, "capacete", date(2026, 10, 1))]
    a = audita_funcionario(ls, "armador", hoje=HOJE)
    assert regras(a) == ["epi_inadequado", "epi_inadequado"]
    assert {x.gravidade for x in a} == {"irregular", "risco"}


def test_troca_atrasada():
    ls = [L(1, "protetor auditivo", date(2026, 1, 1)), L(2, "luva", date(2026, 11, 1))]
    a = audita_funcionario(ls, "armador", hoje=HOJE)
    assert regras(a) == ["troca_atrasada"]


def test_funcao_desconhecida():
    a = audita_funcionario([L(1, "luva", date(2026, 11, 1))], "astronauta", hoje=HOJE)
    assert regras(a) == ["funcao_desconhecida"]


@precisa_base
def test_ca_com_texto_e_normalizado():
    assert audita_linha(L(1, "luva", date(2026, 11, 1), " C.A. 21245 "), "armador") == []
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "C.A. 25"), "armador")) == ["ca_vencido"]


def test_ca_sem_digitos_vira_ausente():
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "s/ CA"), "armador")) == ["ca_ausente"]


@precisa_base
def test_sem_data_ainda_acusa_nao_encontrado_e_cancelado_mas_nao_vencido():
    assert regras(audita_linha(L(1, "luva", None, "99999999"), "armador")) == ["ca_nao_encontrado"]
    assert regras(audita_linha(L(1, "luva", None, "33295"), "armador")) == ["ca_cancelado"]
    assert audita_linha(L(1, "botina", None, "25"), "armador") == []


def _fake_ca(situacao, validade, conflito=False):
    return lambda numero, data: {"numero": numero, "encontrado": True, "valido_na_data": False,
                                 "validade": validade, "situacao": situacao, "equipamento": "X",
                                 "conflito": conflito, "motivo": ""}


def test_conflitante_com_linha_cancelada_e_vencida_gera_so_conflitante(monkeypatch):
    monkeypatch.setattr("heitor.dados.regras.consulta_ca", _fake_ca("CANCELADO", "2020-01-01", conflito=True))
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "1"), "armador")) == ["ca_conflitante"]


def test_cancelado_com_validade_passada_gera_vencido_e_cancelado(monkeypatch):
    monkeypatch.setattr("heitor.dados.regras.consulta_ca", _fake_ca("CANCELADO", "2020-01-01"))
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "1"), "armador")) == ["ca_cancelado", "ca_vencido"]


def test_cancelado_com_validade_futura_gera_so_cancelado(monkeypatch):
    monkeypatch.setattr("heitor.dados.regras.consulta_ca", _fake_ca("CANCELADO", "2030-01-01"))
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "1"), "armador")) == ["ca_cancelado"]


def test_validade_no_proprio_dia_nao_vence(monkeypatch):
    monkeypatch.setattr("heitor.dados.regras.consulta_ca", _fake_ca("VÁLIDO", "2026-11-01"))
    assert audita_linha(L(1, "luva", date(2026, 11, 1), "1"), "armador") == []
