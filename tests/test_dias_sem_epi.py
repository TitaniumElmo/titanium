from datetime import date

import pytest

from heitor.agente.relatorio import gerar_relatorio
from heitor.api.estado import estado
from heitor.contrato import Achado, Linha
from heitor.dados.dias_sem_epi import dias_sem_epi_valido
from heitor.dados.exposicao import calcula_exposicao
from heitor.dados.regras import audita_funcionario

HOJE = date(2026, 11, 8)


def L(n, epi, d, fid="0301", funcao="pedreiro"):
    return Linha(funcionario_id=fid, nome="X", funcao=funcao, linha=n, data=d, epi=epi, ca="17664",
                 origem="t", assinatura=True).model_dump(mode="json")


def achados_de(linhas, funcao="pedreiro"):
    return audita_funcionario(linhas, funcao, hoje=HOJE)


def protetor(*datas, fid="0301"):
    return [L(i, "protetor auditivo", d, fid) for i, d in enumerate(datas, 1)]


@pytest.fixture
def pgr(monkeypatch):
    monkeypatch.setenv("HEITOR_PGR", "completo")


@pytest.fixture
def sem_pgr(monkeypatch):
    monkeypatch.delenv("HEITOR_PGR", raising=False)


def test_um_intervalo_soma_os_dias_alem_da_vida_util(sem_pgr):
    a = achados_de(protetor(date(2025, 1, 1), date(2025, 12, 1), date(2026, 11, 1)))
    assert [x["regra"] for x in a] == ["troca_passado", "troca_passado"]
    assert dias_sem_epi_valido(a) == {"0301": (334 - 180) + (335 - 180)}
    um = achados_de(protetor(date(2025, 1, 1), date(2025, 12, 1), date(2026, 10, 30)))
    assert dias_sem_epi_valido([x for x in um if "334 dias" in x["evidencia"]]) == {"0301": 154}


def test_varios_intervalos_somam_e_o_trecho_ate_hoje_fica_de_fora(sem_pgr):
    a = achados_de(protetor(date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1)))
    assert sorted(x["regra"] for x in a) == ["troca_atrasada", "troca_passado", "troca_passado"]
    assert dias_sem_epi_valido(a) == {"0301": (366 - 180) + (365 - 180)}


def test_funcionario_sem_troca_passado_fica_ausente_e_so_troca_atrasada_nao_conta(sem_pgr):
    ok = achados_de(protetor(date(2026, 9, 1)))
    assert ok == [] and dias_sem_epi_valido(ok) == {}
    atrasada = achados_de(protetor(date(2025, 12, 1)))
    assert [x["regra"] for x in atrasada] == ["troca_atrasada"] and dias_sem_epi_valido(atrasada) == {}
    assert dias_sem_epi_valido([]) == {}


def test_varios_funcionarios_ficam_separados(sem_pgr):
    a = achados_de(protetor(date(2025, 1, 1), date(2025, 12, 1), date(2026, 10, 1), fid="1"))
    b = achados_de(protetor(date(2025, 1, 1), date(2026, 1, 1), date(2026, 10, 1), fid="2"))
    assert dias_sem_epi_valido(a + b) == {"1": 154 + (304 - 180), "2": (365 - 180) + (273 - 180)}


def kit_com_capacete_atrasado():
    base = [L(1, "protetor auditivo", date(2025, 1, 1)), L(2, "protetor auditivo", date(2025, 12, 1)),
            L(3, "protetor auditivo", date(2026, 10, 1)),
            L(4, "capacete", date(2023, 1, 1)), L(5, "capacete", date(2025, 3, 11)),
            L(6, "botina", date(2026, 6, 1)), L(7, "óculos de proteção", date(2026, 6, 1)),
            L(8, "luva de raspa", date(2026, 10, 1))]
    return base


def test_pgr_desligado_vale_so_para_protetor(sem_pgr):
    a = achados_de(kit_com_capacete_atrasado())
    assert dias_sem_epi_valido(a) == {"0301": 154 + (304 - 180)}
    capacete = [{"funcionario_id": "0301", "regra": "troca_passado", "gravidade": "irregular",
                 "evidencia": "capacete: 800 dias entre 2023-01-01 e 2025-03-11; vida útil 730 dias"}]
    assert dias_sem_epi_valido(capacete) == {}


def test_pgr_ligado_vale_para_todas_as_categorias_da_tabela(pgr):
    a = achados_de(kit_com_capacete_atrasado())
    assert dias_sem_epi_valido(a) == {"0301": 154 + (304 - 180) + (800 - 730)}
    assert dias_sem_epi_valido([{"funcionario_id": "9", "regra": "troca_passado", "gravidade": "irregular",
                                 "evidencia": "luva: 200 dias entre 2026-01-01 e 2026-07-20; vida útil 90 dias"}]) == {"9": 110}


def test_nao_gera_achado_nem_reais_nem_mexe_na_exposicao(sem_pgr):
    ls = protetor(date(2025, 1, 1), date(2025, 12, 1), date(2026, 10, 1))
    antes = achados_de(ls)
    exposicao = calcula_exposicao(antes, funcoes={"0301": "pedreiro"}, hoje=HOJE)
    dias_sem_epi_valido(antes)
    assert achados_de(ls) == antes or [x["regra"] for x in achados_de(ls)] == [x["regra"] for x in antes]
    assert calcula_exposicao(antes, funcoes={"0301": "pedreiro"}, hoje=HOJE) == exposicao
    assert all(isinstance(v, int) for v in dias_sem_epi_valido(antes).values())


def test_aceita_achado_pydantic_e_evidencia_ilegivel_nao_conta(sem_pgr):
    a = Achado.model_construct(id="a-1", funcionario_id="1", linha=None, regra="troca_passado", gravidade="irregular",
                               tipo="passivo", evidencia="protetor auditivo: 334 dias entre 2025-01-01 e 2025-12-01; vida útil 180 dias",
                               acao_sugerida="x")
    ilegivel = {**a.model_dump(), "funcionario_id": "2", "evidencia": "protetor auditivo: sem números"}
    assert dias_sem_epi_valido([a, ilegivel]) == {"1": 154}


# -- relatório ---------------------------------------------------------------------------------


def test_relatorio_mostra_pelo_menos_n_dias_por_funcionario(sem_pgr):
    a = achados_de(protetor(date(2025, 1, 1), date(2025, 12, 1), date(2026, 10, 1)))
    r = gerar_relatorio(a)
    assert r["resumo"]["por_funcionario"] == {
        "0301": {"dias_sem_epi_valido_registrado": 278, "texto": "pelo menos 278 dias sem EPI válido registrado"}}
    assert "Pelo menos 278 dias sem EPI válido registrado" in r["texto"]
    assert r["resumo"]["funcionarios"] == 1 and "por_gravidade" in r["resumo"] and r["itens"]


def test_relatorio_sem_troca_passado_nao_cita_dias(sem_pgr):
    r = gerar_relatorio(achados_de([L(1, "capacete", date(2026, 1, 1))]))
    assert r["resumo"]["por_funcionario"] == {} and "dias sem EPI válido" not in r["texto"]


# -- API ---------------------------------------------------------------------------------------


def salvar_achado(aud, fid, evidencia):
    estado.salvar_achado(Achado.model_construct(
        id=estado.novo_id("a"), auditoria_id=aud, funcionario_id=fid, linha=None, regra="troca_passado",
        gravidade="irregular", tipo="passivo", evidencia=evidencia, acao_sugerida="registrar no relatório (não tem conserto)"))


def test_api_expoe_o_campo_opcional_sem_quebrar_o_resumo_antigo(client, sem_pgr):
    aud = estado.novo_id("au")
    estado.criar_auditoria(aud, [])
    salvar_achado(aud, "0301", "protetor auditivo: 334 dias entre 2025-01-01 e 2025-12-01; vida útil 180 dias")
    salvar_achado(aud, "0301", "protetor auditivo: 304 dias entre 2025-12-01 e 2026-10-01; vida útil 180 dias")
    r = client.get(f"/auditorias/{aud}").json()
    assert r["dias_sem_epi_valido_registrado"] == {"0301": 278}
    for chave in ("id", "status", "contagem_gravidade", "contagem_tipo", "exposicao_total_rs", "pendencias_abertas",
                  "passos", "custo_total_usd", "disparado_por", "n_fichas"):
        assert chave in r


def test_api_sem_troca_passado_devolve_mapa_vazio(client, sem_pgr):
    aud = estado.novo_id("au")
    estado.criar_auditoria(aud, [])
    assert client.get(f"/auditorias/{aud}").json()["dias_sem_epi_valido_registrado"] == {}
    assert all("dias_sem_epi_valido_registrado" not in a for a in client.get("/auditorias").json())
