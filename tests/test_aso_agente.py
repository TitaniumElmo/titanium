"""Ferramenta auditar_aso (exames médicos, regras do Gustavo em heitor/dados/aso.py), atrás de HEITOR_EXAMES=1.

Sem a flag, a ferramenta nem é registrada e o agente fica igual (o pedido ao LLM é o mesmo da main).
Com a flag, a política sem LLM e a rede de segurança também conferem o ASO: com ou sem LLM, os mesmos achados.
"""

import os

os.environ["HEITOR_LLM"] = "off"

import pytest  # noqa: E402

from heitor.agente import ferramentas as F  # noqa: E402
from heitor.agente import grafo  # noqa: E402
from tests.test_contrato_agente import stubs_de_dados  # noqa: E402


def _epi(fid, funcao):
    return {"funcionario_id": fid, "nome": f"Funcionário {fid}", "funcao": funcao, "linha": 1, "data": "2026-10-01",
            "epi": "protetor auditivo", "qtd": 1, "ca": "17664", "motivo": "E", "assinatura": True, "origem": "t.csv"}


@pytest.fixture
def exames(monkeypatch):
    monkeypatch.setenv("HEITOR_EXAMES", "1")
    monkeypatch.setitem(F.FERRAMENTAS, "auditar_aso", F.Ferramenta(
        "auditar_aso", "auditar_aso()", "Exames médicos (ASO).", F._t_auditar_aso))
    F._cache_aso.clear()


def test_sem_a_flag_nada_muda(monkeypatch):
    monkeypatch.delenv("HEITOR_EXAMES", raising=False)
    assert "auditar_aso" not in F.FERRAMENTAS
    assert not F.aso_ligado()
    with stubs_de_dados():
        r = grafo.rodar_auditoria("au-sem-aso", [_epi("0503", "carpinteiro")])
    assert not any(a["regra"].startswith("aso_") for a in r["achados"])


def test_com_a_flag_o_funcionario_recebe_os_achados_de_aso(exames):
    with stubs_de_dados():
        r = grafo.rodar_auditoria("au-aso", [_epi("0503", "carpinteiro"), _epi("0509", "carpinteiro")])
    regras = {(a["funcionario_id"], a["regra"]) for a in r["achados"] if a["regra"].startswith("aso_")}
    assert ("0503", "aso_ausente") in regras                 # ativo sem nenhum ASO
    assert ("0509", "aso_sem_assinatura_medico") in regras   # periódico sem assinatura do médico
    assert all(a["funcionario_id"] in ("0503", "0509") for a in r["achados"])  # só quem está na planilha de EPI
    aso = [a for a in r["achados"] if a["funcionario_id"] == "0503" and a["regra"] == "aso_ausente"][0]
    assert any(p["achado_id"] == aso["id"] for p in r["pendencias"])  # corrigível: vira pendência


def test_relatorio_explica_as_regras_de_aso(exames):
    with stubs_de_dados():
        r = grafo.rodar_auditoria("au-aso-rel", [_epi("0503", "carpinteiro")])
    itens = [i for i in r["relatorio"]["itens"] if i["titulo"] == "Funcionário ativo sem ASO"]
    assert itens and any("NR-7" in b for b in itens[0]["base_legal"])


def test_uma_pendencia_cobre_exame_e_epi(exames):
    """criar_pendencia com 'tambem': uma ida só do técnico para o exame e o EPI do mesmo funcionário."""
    ctx = F.Contexto(funcionario_id="0502", funcao="servente", linhas={}, auditoria_id="au-t")
    epi = {"id": "a-epi", "funcionario_id": "0502", "auditoria_id": "au-t", "linha": 1, "regra": "troca_atrasada",
           "gravidade": "irregular", "tipo": "corrigivel", "evidencia": "protetor vencido", "acao_sugerida": "trocar"}
    aso = {"id": "a-aso", "funcionario_id": "0502", "auditoria_id": "au-t", "linha": None,
           "regra": "aso_periodico_vencido", "gravidade": "irregular", "tipo": "corrigivel",
           "evidencia": "periódico vencido", "acao_sugerida": "agendar o exame periódico"}
    rh = {**aso, "id": "a-rh", "regra": "aso_sem_medico", "gravidade": "risco", "tipo": "prova"}
    ctx.achados.update({a["id"]: a for a in (epi, aso, rh)})
    r = F.executar("criar_pendencia", {"achado_id": "a-epi", "acao": "Trocar o protetor e agendar o periódico",
                                       "prazo_dias": 2, "tambem": ["a-aso", "a-rh", "nao-existe"]}, ctx)
    assert r.saida["tambem_cobre"] == ["a-aso"]
    assert set(r.saida["tambem_recusados"]) == {"a-rh", "nao-existe"}  # RH tem destino próprio
    assert ctx.pendencia_por_achado["a-aso"] == ctx.pendencia_por_achado["a-epi"]
    assert "a-rh" not in ctx.pendencia_por_achado


def test_auditar_ficha_traz_os_exames_e_nao_diz_sem_falhas(exames):
    """Com a flag, o LLM vê EPI e ASO juntos no primeiro passo (senão criava as de EPI antes de ver o exame)."""
    linha = _epi("0505", "pedreiro")
    ctx = F.Contexto(funcionario_id="0505", funcao="pedreiro", linhas={1: linha}, auditoria_id="au-t")
    with stubs_de_dados():
        r = F.executar("auditar_ficha", {}, ctx)
    regras = [a["regra"] for a in r.saida["exames_aso"]["achados_aso"]]
    assert regras == ["aso_inapto_em_atividade"] and r.saida["sem_falhas"] is False
    assert all(a.get("auditoria_id") == "au-t" for a in ctx.achados_do_funcionario())
