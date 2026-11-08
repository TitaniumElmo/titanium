from datetime import date

from heitor.contrato import Achado
from heitor.dados.exposicao import SALARIO_MINIMO, calcula_exposicao

HOJE = date(2026, 11, 7)


def A(fid, tipo="passivo", gravidade="irregular", **extra):
    return {"id": f"a-{fid}-{tipo}-{len(extra)}", "funcionario_id": fid, "linha": 1,
            "regra": "assinatura_ausente", "gravidade": gravidade, "tipo": tipo,
            "evidencia": "x", "acao_sugerida": "y", **extra}


def test_lista_vazia_da_zero():
    r = calcula_exposicao([], hoje=HOJE)
    assert r["total_brl"] == 0 and r["funcionarios"] == [] and r["por_funcionario"] == {}
    assert r["salario_minimo"] == SALARIO_MINIMO == 1621.00


def test_ignora_risco_e_ok():
    achados = [A("1", tipo="prova", gravidade="risco"), A("2", tipo="corrigivel"),
               A("3", gravidade="ok")]
    assert calcula_exposicao(achados, hoje=HOJE)["total_brl"] == 0


def test_teto_de_60_meses():
    r = calcula_exposicao([A("1", data="2010-01-01")], funcoes={"1": "armador"}, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert d["meses"] == 60 and d["valor_brl"] == round(0.20 * SALARIO_MINIMO * 60, 2)
    assert "meses_estimados" not in d


def test_dois_passivos_do_mesmo_funcionario_contam_uma_vez_pelo_maior_periodo():
    achados = [A("1", data="2026-05-07"), A("1", data="2026-01-07", linha=2)]
    r = calcula_exposicao(achados, funcoes={"1": "armador"}, hoje=HOJE)
    assert r["funcionarios"] == ["1"] and r["por_funcionario"]["1"]["meses"] == 10
    assert r["total_brl"] == round(0.20 * SALARIO_MINIMO * 10, 2)


def test_sem_data_usa_12_meses_estimados():
    r = calcula_exposicao([A("1")], funcoes={"1": "armador"}, hoje=HOJE)
    assert r["por_funcionario"]["1"]["meses"] == 12
    assert r["por_funcionario"]["1"]["meses_estimados"] is True and r["meses_estimados"] is True


def test_funcao_desconhecida_usa_020_e_avisa():
    r = calcula_exposicao([A("1")], funcoes={"1": "astronauta"}, hoje=HOJE)
    assert r["por_funcionario"]["1"]["grau"] == 0.20
    assert r["avisos"] and "astronauta" in r["avisos"][0]


def test_total_e_a_soma_dos_funcionarios():
    achados = [A("2", data="2026-05-07"), A("1", data="2025-11-07")]
    r = calcula_exposicao(achados, funcoes={"1": "armador", "2": "pedreiro"}, hoje=HOJE)
    assert r["funcionarios"] == ["1", "2"]
    assert r["total_brl"] == round(sum(d["valor_brl"] for d in r["por_funcionario"].values()), 2)
    assert r["por_funcionario"]["1"]["meses"] == 12 and r["por_funcionario"]["2"]["meses"] == 6


def test_aceita_achado_pydantic():
    a = Achado(id="a-1", funcionario_id="1", linha=1, regra="assinatura_ausente",
               gravidade="irregular", tipo="passivo", evidencia="x", acao_sugerida="y")
    assert calcula_exposicao([a], funcoes={"1": "armador"}, hoje=HOJE)["funcionarios"] == ["1"]


def TP(fid, dias=341, vida=180, evidencia=None, **extra):
    return A(fid, regra="troca_passado", linha=None, **extra,
             evidencia=evidencia or f"protetor auditivo: {dias} dias entre 2025-12-01 e 2026-11-07; vida útil {vida} dias")


def test_troca_passado_conta_so_o_tempo_alem_da_vida_util():
    r = calcula_exposicao([TP("1")], funcoes={"1": "armador"}, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    meses = 161 / 30.4375
    assert round(meses, 2) == 5.29 and d["meses"] == 5.29
    assert d["valor_brl"] == round(0.20 * SALARIO_MINIMO * meses, 2)
    assert d["criterio"] == "tempo além da vida útil" and "meses_estimados" not in d
    assert r["total_brl"] == d["valor_brl"]


def test_troca_passado_com_evidencia_ilegivel_usa_12_meses_estimados():
    r = calcula_exposicao([TP("1", evidencia="troca fora do prazo")], funcoes={"1": "armador"}, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert d["meses"] == 12 and d["meses_estimados"] is True and "criterio" not in d
    assert r["meses_estimados"] is True


def test_troca_passado_respeita_o_teto_de_60_meses():
    r = calcula_exposicao([TP("1", dias=3000, vida=180)], funcoes={"1": "armador"}, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert d["meses"] == 60 and d["valor_brl"] == round(0.20 * SALARIO_MINIMO * 60, 2)


def test_troca_passado_dentro_da_vida_util_nao_soma_meses():
    r = calcula_exposicao([TP("1", dias=100, vida=180)], funcoes={"1": "armador"}, hoje=HOJE)
    assert r["por_funcionario"]["1"]["meses"] == 0 and r["total_brl"] == 0


def test_troca_passado_e_assinatura_passiva_contam_uma_vez_pelo_maior_periodo_medido():
    funcoes = {"1": "armador"}
    # (d) assinatura com data conhecida (8 meses) vence os 5,29 meses da troca
    r = calcula_exposicao([TP("1"), A("1", data="2026-03-07")], funcoes=funcoes, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert r["funcionarios"] == ["1"] and d["meses"] == 8 and "criterio" not in d and "meses_estimados" not in d
    assert r["total_brl"] == round(0.20 * SALARIO_MINIMO * 8, 2)
    # a troca vence quando e maior
    r = calcula_exposicao([TP("1", dias=180 + 305), A("1", data="2026-09-07")], funcoes=funcoes, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert d["meses"] == round(305 / 30.4375, 2) and d["criterio"] == "tempo além da vida útil"


def test_medido_vence_estimado_mesmo_sendo_menor():
    # (a) passivo sem data (12 meses estimados) + troca de 161 dias além da vida útil
    for ordem in (lambda x: x, lambda x: x[::-1]):
        r = calcula_exposicao(ordem([A("1"), TP("1")]), funcoes={"1": "armador"}, hoje=HOJE)
        d = r["por_funcionario"]["1"]
        assert d["meses"] == 5.29 and d["criterio"] == "tempo além da vida útil"
        assert "meses_estimados" not in d and "meses_estimados" not in r
        assert d["valor_brl"] == round(0.20 * SALARIO_MINIMO * 161 / 30.4375, 2)


def test_so_estimado_usa_12_meses_e_marca():
    # (b)
    r = calcula_exposicao([A("1"), A("1", linha=2)], funcoes={"1": "armador"}, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert d["meses"] == 12 and d["meses_estimados"] is True and r["meses_estimados"] is True


def test_troca_passado_ignora_o_campo_data_e_usa_a_evidencia():
    # (c) data do achado diferente da evidência
    r = calcula_exposicao([TP("1", data="2020-01-01")], funcoes={"1": "armador"}, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert d["meses"] == 5.29 and d["criterio"] == "tempo além da vida útil"
    # evidencia ilegivel: tambem ignora a data e fica estimado
    r = calcula_exposicao([TP("1", data="2020-01-01", evidencia="ilegível")], funcoes={"1": "armador"}, hoje=HOJE)
    d = r["por_funcionario"]["1"]
    assert d["meses"] == 12 and d["meses_estimados"] is True
