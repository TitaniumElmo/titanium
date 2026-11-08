import re
from datetime import date
from pathlib import Path

import pytest

from heitor.dados.aso import (ExameASO, audita_aso, audita_aso_csv, exames_ligado, ler_aso_csv,
                              soma_meses)

HOJE = date(2026, 11, 8)
CSV = Path(__file__).resolve().parents[1] / "heitor" / "exemplos" / "aso_exemplo.csv"

ESPERADO = {
    "0501": [],
    "0502": [("aso_periodico_vencido", "irregular", "corrigivel")],
    "0503": [("aso_ausente", "irregular", "corrigivel")],
    "0504": [("aso_admissional_tardio", "irregular", "passivo")],
    "0505": [("aso_inapto_em_atividade", "irregular", "corrigivel")],
    "0506": [],
    "0507": [("aso_periodico_vencido", "irregular", "corrigivel")],
    "0508": [("aso_sem_medico", "risco", "prova")],
    "0509": [("aso_sem_assinatura_medico", "irregular", "prova")],
    "0510": [("aso_sem_assinatura_medico", "risco", "prova")],
    "0511": [],
    "0512": [("aso_inapto_em_atividade", "irregular", "corrigivel"),
             ("aso_sem_assinatura_medico", "irregular", "prova")],
}


@pytest.fixture(scope="module")
def achados():
    return audita_aso_csv(CSV, HOJE)


@pytest.mark.parametrize("fid", sorted(ESPERADO))
def test_gabarito_por_funcionario(achados, fid):
    obtido = sorted((a["regra"], a["gravidade"], a["tipo"]) for a in achados if a["funcionario_id"] == fid)
    assert obtido == sorted(ESPERADO[fid])


def test_total_de_achados(achados):
    assert len(achados) == sum(len(v) for v in ESPERADO.values())


def test_borda_vence_hoje_nao_e_vencido():
    exames = [e for e in ler_aso_csv(CSV) if e.funcionario_id == "0506"]
    assert audita_aso(exames, date(2026, 11, 8)) == []
    assert [a.regra for a in audita_aso(exames, date(2026, 11, 9))] == ["aso_periodico_vencido"]


def test_periodicidade_configuravel():
    exames = [e for e in ler_aso_csv(CSV) if e.funcionario_id == "0502"]
    assert audita_aso(exames, HOJE, meses=24) == []
    assert [a.regra for a in audita_aso(exames, HOJE, meses=12)] == ["aso_periodico_vencido"]


def test_desligado_nao_gera_ausente_nem_vencido():
    e = ExameASO(funcionario_id="9", nome="X", funcao="servente", linha=2, ativo=False)
    assert audita_aso([e], HOJE) == []


def test_soma_meses_fim_de_mes():
    assert soma_meses(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert soma_meses(date(2025, 11, 30), 3) == date(2026, 2, 28)


def test_acoes_nunca_mandam_alterar_registro_antigo(achados):
    proibido = re.compile(r"\b(assinar|preencher|alterar|completar|regularizar|retroativ\w*)\b", re.I)
    assert not [a for a in achados if proibido.search(a["acao_sugerida"])]


def test_so_regras_fora_do_contrato_existente(achados):
    assert all(a["regra"].startswith("aso_") for a in achados)


def test_flag_desligada_por_padrao(monkeypatch):
    monkeypatch.delenv("HEITOR_EXAMES", raising=False)
    assert exames_ligado() is False
    monkeypatch.setenv("HEITOR_EXAMES", "1")
    assert exames_ligado() is True
