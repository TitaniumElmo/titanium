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
