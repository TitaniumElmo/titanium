from datetime import date

import pytest

from heitor.contrato import Linha
from heitor.dados.exposicao import calcula_exposicao
from heitor.dados.funcoes import categoria_epi, exigencia_funcao
from heitor.dados.regras import audita_funcionario, audita_linha

HOJE = date(2026, 11, 7)


def L(n, epi, d, fid="0301", **extra):
    return Linha(funcionario_id=fid, nome="X", funcao="pedreiro", linha=n, data=d, epi=epi, ca="17664",
                 origem="t", assinatura=True, **extra)


def dicts(linhas):
    return [l.model_dump(mode="json") for l in linhas]


def regras(achados):
    return sorted(a["regra"] if isinstance(a, dict) else a.regra for a in achados)


def completa(fid="0301", **atrasos):
    base = {"protetor auditivo": date(2026, 10, 1), "capacete": date(2026, 6, 1), "calçado": date(2026, 6, 1),
            "óculos": date(2026, 6, 1), "luva": date(2026, 10, 1)} | atrasos
    return [L(i, epi, d, fid) for i, (epi, d) in enumerate(base.items(), 1) if d]


@pytest.fixture
def pgr(monkeypatch):
    monkeypatch.setenv("HEITOR_PGR", "completo")


@pytest.mark.parametrize("valor", [None, "", "parcial", "COMPLETO", "1", "true"])
def test_chave_desligada_mantem_so_protetor_auditivo(monkeypatch, valor):
    if valor is None:
        monkeypatch.delenv("HEITOR_PGR", raising=False)
    else:
        monkeypatch.setenv("HEITOR_PGR", valor)
    for f in ("pedreiro", "servente", "carpinteiro", "armador"):
        e = exigencia_funcao(f)
        assert e["epis"] == [{"epi": "protetor auditivo", "vida_util_dias": 180}]
        assert (e["agente_nocivo"], e["grau"]) == ("ruído", 0.20)
    ls = [L(1, "protetor auditivo", date(2026, 10, 1)), L(2, "capacete", date(2020, 1, 1))]
    assert audita_funcionario(ls, "pedreiro", hoje=HOJE) == []
    assert "agente_nocivo" not in audita_linha(dicts([L(1, "botina", date(2026, 1, 1))])[0] | {"assinatura": False}, "pedreiro")[0]


def test_chave_ligada_tabela_por_funcao(pgr):
    def tabela(f):
        return {e["epi"]: e["vida_util_dias"] for e in exigencia_funcao(f)["epis"]}
    assert tabela("pedreiro") == {"protetor auditivo": 180, "capacete": 730, "calçado": 365, "óculos": 365, "luva": 90}
    assert tabela("servente") == {"protetor auditivo": 180, "capacete": 730, "calçado": 365, "luva": 90}
    assert tabela("carpinteiro") == {"protetor auditivo": 180, "capacete": 730, "calçado": 365, "óculos": 365}
    assert tabela("armador") == {"protetor auditivo": 180, "capacete": 730, "calçado": 365, "luva": 90}
    e = exigencia_funcao("armador")
    assert e["grau"] == 0.20 and {x["epi"]: x["agente_nocivo"] for x in e["epis"]} == {
        "protetor auditivo": "ruído", "capacete": "acidente", "calçado": "acidente", "luva": "acidente"}
    for nome, cat in {"capacete classe C": "capacete", "botina": "calçado", "calçado de segurança": "calçado",
                      "óculos de proteção": "óculos", "luva de raspa": "luva"}.items():
        assert categoria_epi(nome) == cat


def test_ficha_completa_nao_gera_achado(pgr):
    assert audita_funcionario(completa(), "pedreiro", hoje=HOJE) == []


def test_pedreiro_sem_capacete_vira_epi_exigido_ausente_acidente(pgr):
    a = audita_funcionario(dicts(completa(capacete=None)), "pedreiro", hoje=HOJE)
    assert regras(a) == ["epi_inadequado"]
    assert (a[0]["gravidade"], a[0]["agente_nocivo"]) == ("irregular", "acidente") and "capacete" in a[0]["evidencia"]


def test_armador_com_botina_vencida_vira_troca_atrasada_acidente(pgr):
    ls = [l for l in completa("0310", calçado=date(2025, 1, 10), óculos=None) if l.epi != "óculos"]
    a = audita_funcionario(dicts(ls), "armador", hoje=HOJE)
    assert regras(a) == ["troca_atrasada"]
    assert (a[0]["gravidade"], a[0]["tipo"], a[0]["agente_nocivo"]) == ("irregular", "corrigivel", "acidente")
    assert a[0]["evidencia"].startswith("calçado:")


def test_protetor_auditivo_continua_ruido(pgr):
    a = audita_funcionario(dicts(completa(**{"protetor auditivo": date(2025, 1, 10)})), "pedreiro", hoje=HOJE)
    assert regras(a) == ["troca_atrasada"] and a[0]["agente_nocivo"] == "ruído"
    a = audita_funcionario(dicts(completa(**{"protetor auditivo": None})), "pedreiro", hoje=HOJE)
    assert regras(a) == ["epi_inadequado"] and a[0]["agente_nocivo"] == "ruído"


def test_agente_na_assinatura_passiva_segue_o_epi_da_linha(pgr):
    sem = {"assinatura": False}
    assert audita_linha(dicts([L(1, "protetor auditivo", date(2026, 10, 1))])[0] | sem, "pedreiro")[0]["agente_nocivo"] == "ruído"
    assert audita_linha(dicts([L(1, "botina", date(2026, 10, 1))])[0] | sem, "pedreiro")[0]["agente_nocivo"] == "acidente"
    obj = audita_linha(L(1, "luva", date(2026, 10, 1)).model_copy(update={"assinatura": False}), "pedreiro")
    assert obj[0].agente_nocivo == "acidente"


def passivo(fid, agente=None, **extra):
    a = {"id": f"a-{fid}", "funcionario_id": fid, "linha": 1, "regra": "assinatura_ausente", "gravidade": "irregular",
         "tipo": "passivo", "evidencia": "x", "acao_sugerida": "y"} | extra
    if agente:
        a["agente_nocivo"] = agente
    return a


def test_exposicao_mista_soma_so_o_ruido(pgr):
    achados = [passivo("1", "ruído"), passivo("2", "acidente"), passivo("3")]
    r = calcula_exposicao(achados, funcoes={"1": "pedreiro", "2": "pedreiro", "3": "pedreiro"}, hoje=HOJE)
    assert r["funcionarios"] == ["1"] and r["total_brl"] == round(0.20 * 1621 * 12, 2)
    so_acidente = calcula_exposicao([passivo("2", "acidente")], funcoes={"2": "pedreiro"}, hoje=HOJE)
    assert so_acidente["total_brl"] == 0 and so_acidente["funcionarios"] == []


def test_exposicao_com_chave_desligada_conta_tudo(monkeypatch):
    monkeypatch.delenv("HEITOR_PGR", raising=False)
    achados = [passivo("1", "ruído"), passivo("2", "acidente"), passivo("3")]
    r = calcula_exposicao(achados, funcoes={}, hoje=HOJE)
    assert r["funcionarios"] == ["1", "2", "3"] and r["total_brl"] == round(3 * 0.20 * 1621 * 12, 2)


def test_reserva_categoria_fora_da_tabela_com_mais_de_365_dias_vira_risco(pgr):
    ls = [l for l in completa("0304", óculos=date(2025, 6, 1)) if l.epi != "luva"] + [L(9, "luva", date(2026, 10, 1), "0304")]
    a = audita_funcionario(dicts(ls), "servente", hoje=HOJE)
    assert regras(a) == ["troca_atrasada"]
    assert (a[0]["gravidade"], a[0]["tipo"], a[0]["agente_nocivo"]) == ("risco", "corrigivel", "acidente")
    assert "sem prazo na tabela da empresa; conferir a durabilidade do EPI" in a[0]["evidencia"]
    assert "fabricante" not in (a[0]["evidencia"] + a[0]["acao_sugerida"]).lower()


def test_reserva_nao_dispara_dentro_de_365_dias_nem_para_categoria_desconhecida(pgr):
    base = completa("0304", óculos=None)
    dentro = base + [L(9, "óculos", date(2026, 1, 1), "0304")]
    assert audita_funcionario(dicts(dentro), "servente", hoje=HOJE) == []
    desconhecida = base + [L(9, "cinto de segurança", date(2020, 1, 1), "0304")]
    assert audita_funcionario(dicts(desconhecida), "servente", hoje=HOJE) == []


def test_reserva_nunca_irregular_e_nao_existe_com_a_chave_desligada(pgr, monkeypatch):
    ls = [l for l in completa("0304", óculos=date(2015, 1, 1)) if l.epi != "luva"] + [L(9, "luva", date(2026, 10, 1), "0304")]
    assert {x["gravidade"] for x in audita_funcionario(dicts(ls), "servente", hoje=HOJE)} == {"risco"}
    monkeypatch.delenv("HEITOR_PGR")
    assert audita_funcionario(dicts(ls), "servente", hoje=HOJE) == []
