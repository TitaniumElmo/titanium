from datetime import date

from heitor.contrato import Linha
from heitor.dados.regras import audita_funcionario, audita_linha

HOJE = date(2026, 11, 7)


def L(n, epi, d, ca=None, fid="0302"):
    return Linha(funcionario_id=fid, nome="X", funcao="armador", linha=n, data=d, epi=epi, ca=ca, origem="t")


def regras(achados):
    return sorted(a.regra for a in achados)


def test_ficha_ok():
    ls = [L(1, "protetor auditivo", date(2026, 10, 1), "17664"), L(2, "luva", date(2026, 11, 1), "21245")]
    assert audita_funcionario(ls, "armador", hoje=HOJE) == []


def test_funcionario_nao_repete_achados_de_ca():
    ls = [L(1, "luva", date(2026, 11, 1), "25"), L(2, "protetor auditivo", date(2026, 10, 1))]
    assert audita_funcionario(ls, "armador", hoje=HOJE) == []


def test_linha_ca_vencido_na_entrega():
    a = audita_linha(L(1, "botina", date(2026, 10, 1), "25"), "armador")
    assert regras(a) == ["ca_vencido"] and a[0].gravidade == "risco" and a[0].tipo == "prova"


def test_linha_ca_cancelado_e_nao_encontrado():
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "33295"), "armador")) == ["ca_cancelado"]
    assert regras(audita_linha(L(2, "luva", date(2026, 11, 1), "99999999"), "armador")) == ["ca_nao_encontrado"]


def test_linha_ca_conflitante():
    assert regras(audita_linha(L(1, "luva", date(2026, 11, 1), "7536"), "armador")) == ["ca_conflitante"]


def test_linha_ok():
    assert audita_linha(L(1, "luva", date(2026, 11, 1), "21245", ), "armador") == []


def test_linha_assinatura_ausente():
    l = L(1, "luva", date(2026, 11, 1), "21245")
    l.assinatura = False
    a = audita_linha(l, "armador")
    assert regras(a) == ["assinatura_ausente"] and a[0].gravidade == "irregular" and a[0].tipo == "passivo"


def test_linha_assinatura_ilegivel_nao_acusa():
    l = L(1, "luva", date(2026, 11, 1), "21245")
    assert l.assinatura is None and audita_linha(l, "armador") == []


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
