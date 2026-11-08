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


def kit_com(epi, d1, d2, fid="0301"):
    base = [l for l in completa(fid) if categoria_epi(l.epi) != epi]
    return base + [L(20, epi, d1, fid), L(21, epi, d2, fid)]


def test_capacete_com_intervalo_de_800_dias_vira_troca_passado_acidente_sem_reais(pgr):
    ls = kit_com("capacete", date(2023, 1, 1), date(2025, 3, 11))
    a = audita_funcionario(dicts(ls), "pedreiro", hoje=HOJE)
    assert regras(a) == ["troca_passado"]
    assert (a[0]["gravidade"], a[0]["tipo"], a[0]["agente_nocivo"], a[0]["linha"]) == ("irregular", "passivo", "acidente", None)
    assert a[0]["evidencia"] == "capacete: 800 dias entre 2023-01-01 e 2025-03-11; vida útil 730 dias"
    r = calcula_exposicao(a, funcoes={"0301": "pedreiro"}, hoje=HOJE)
    assert r["total_brl"] == 0 and r["funcionarios"] == []


@pytest.mark.parametrize("epi,funcao,d1,d2,vida", [
    ("calçado", "armador", date(2024, 1, 1), date(2025, 3, 1), 365),
    ("óculos", "carpinteiro", date(2024, 1, 1), date(2025, 3, 1), 365),
    ("luva", "servente", date(2026, 1, 1), date(2026, 6, 1), 90),
])
def test_calcado_oculos_e_luva_tambem_viram_troca_passado_acidente(pgr, epi, funcao, d1, d2, vida):
    kit = {"armador": ["protetor auditivo", "capacete", "calçado", "luva"],
           "carpinteiro": ["protetor auditivo", "capacete", "calçado", "óculos"],
           "servente": ["protetor auditivo", "capacete", "calçado", "luva"]}[funcao]
    base = completa()
    ls = [l for l in base if categoria_epi(l.epi) in kit and categoria_epi(l.epi) != epi]
    ls += [L(20, epi, d1), L(21, epi, d2)]
    ls = [Linha.model_validate(l.model_dump() | {"funcao": funcao}) for l in ls]
    a = audita_funcionario(dicts(ls), funcao, hoje=HOJE)
    passados = [x for x in a if x["regra"] == "troca_passado"]
    assert len(passados) == 1 and passados[0]["agente_nocivo"] == "acidente"
    assert (passados[0]["gravidade"], passados[0]["tipo"]) == ("irregular", "passivo")
    assert f"vida útil {vida} dias" in passados[0]["evidencia"]
    assert calcula_exposicao(a, funcoes={"0301": funcao}, hoje=HOJE)["total_brl"] == 0


def test_protetor_com_intervalo_estourado_continua_com_reais(pgr):
    ls = kit_com("protetor auditivo", date(2025, 1, 1), date(2025, 12, 1))
    ls = [l for l in ls if not (l.epi == "protetor auditivo" and l.data == date(2026, 10, 1))]
    a = audita_funcionario(dicts(ls), "pedreiro", hoje=HOJE)
    passados = [x for x in a if x["regra"] == "troca_passado"]
    assert len(passados) == 1 and passados[0]["agente_nocivo"] == "ruído"
    r = calcula_exposicao(a, funcoes={"0301": "pedreiro"}, hoje=HOJE)
    assert r["funcionarios"] == ["0301"] and r["total_brl"] == round(0.20 * 1621 * (334 - 180) / 30.4375, 2)


def test_capacete_e_protetor_juntos_somam_so_o_ruido(pgr):
    ls = kit_com("capacete", date(2023, 1, 1), date(2025, 3, 11))
    ls = [l for l in ls if l.epi != "protetor auditivo"] + [
        L(30, "protetor auditivo", date(2025, 1, 1)), L(31, "protetor auditivo", date(2025, 12, 1)),
        L(32, "protetor auditivo", date(2026, 10, 1))]
    a = audita_funcionario(dicts(ls), "pedreiro", hoje=HOJE)
    assert sorted(x["agente_nocivo"] for x in a if x["regra"] == "troca_passado") == ["acidente", "ruído", "ruído"]
    r = calcula_exposicao(a, funcoes={"0301": "pedreiro"}, hoje=HOJE)
    assert r["por_funcionario"]["0301"]["meses"] == round((334 - 180) / 30.4375, 2)


def test_chave_desligada_capacete_com_intervalo_estourado_nao_gera_achado(monkeypatch):
    monkeypatch.delenv("HEITOR_PGR", raising=False)
    ls = [L(1, "protetor auditivo", date(2026, 10, 1)), L(2, "capacete", date(2023, 1, 1)), L(3, "capacete", date(2025, 3, 11))]
    assert audita_funcionario(dicts(ls), "pedreiro", hoje=HOJE) == []
