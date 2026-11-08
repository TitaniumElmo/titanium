"""Testes de ponta a ponta. Rodar antes de abrir PR em qualquer branch: scripts/antes_do_pr.sh

1) test_e2e_roteiro_da_demo (sempre roda, sem IA): API real + agente real, seguindo o roteiro da demo:
   ficha de exemplo -> log ao vivo (SSE) -> achados -> pendências -> correção -> pendência fechada -> relatório.
   Sem a base CAEPI em dados/, as regras do Gustavo viram stubs; com a base, roda com as regras reais.
2) test_e2e_ficha_de_papel_com_ia (só com HEITOR_E2E=1, custa centavos): foto real contra a planilha,
   com uma entrega isca; confere as propriedades de segurança, não números exatos (a IA varia).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from heitor.agente import ferramentas as F
from heitor.api import config
from tests.test_api import responder
from tests.test_contrato_agente import FUNCOES_DE_DADOS, stubs_de_dados
from tests.test_integracao import _pendencia_epi, real  # noqa: F401 (fixture)

CORRECAO_0302 = config.PASTA_EXEMPLOS / "correcao_0302.csv"
FOTOS = Path("fotos_teste/fotos")
GABARITOS = Path("fotos_teste/gabaritos_impressos")


def _base_caepi_presente() -> bool:
    return not any(F.ORIGEM[n].startswith("stub.") for n in ("consulta_ca", "audita_linha")) and \
        any(Path("dados").glob("RelatorioCA_*.csv"))


@pytest.fixture
def regras():
    """Regras reais se a base CAEPI está em dados/; senão, os stubs (o E2E roda em qualquer branch)."""
    if _base_caepi_presente():
        yield "reais"
    else:
        with stubs_de_dados():
            yield "stubs"


def _sse(client, aud_id):
    eventos, status, tipo = [], [], None
    with client.stream("GET", f"/auditorias/{aud_id}/eventos", params={"ate_concluir": "true"}) as resp:
        for linha in resp.iter_lines():
            if linha.startswith("event: "):
                tipo = linha[7:]
            elif linha.startswith("data: "):
                (eventos if tipo == "evento" else status).append(json.loads(linha[6:]))
    return eventos, status


def test_e2e_roteiro_da_demo(client, real, regras):  # noqa: F811
    # 1. Upload da ficha de exemplo; o agente roda em segundo plano.
    r = client.post("/auditorias", data={"exemplo": "true"})
    assert r.status_code == 202, r.text
    aud_id = r.json()["id"]

    # 2. Log ao vivo: o LLM (aqui, a política determinística) decide; as ferramentas executam.
    eventos, status = _sse(client, aud_id)
    assert status[-1] == {"status": "concluida"}, status
    assert {e["tipo"] for e in eventos} >= {"decisao", "ferramenta"}
    assert [e["passo"] for e in eventos] == list(range(1, len(eventos) + 1)), "passos fora de sequência no log"
    assert not [e for e in eventos if e["tipo"] == "erro"], [e for e in eventos if e["tipo"] == "erro"]

    # 3. Resumo, achados e pendências criados pelo agente real na API.
    resumo = client.get(f"/auditorias/{aud_id}").json()
    assert resumo["pendencias_abertas"] > 0
    achados = client.get(f"/auditorias/{aud_id}/achados").json()
    assert achados and all(a["gravidade"] in ("irregular", "risco", "ok") for a in achados)
    assert not [a for a in achados if a["regra"] == "falha_de_ferramenta"], "alguma ferramenta falhou"

    # 4. Ciclo de correção: resposta errada reabre, resposta certa fecha.
    p = _pendencia_epi(client, aud_id, "0302")
    assert responder(client, p["id"], config.FICHA_EXEMPLO).json()["status"] == "reaberta"
    fechada = responder(client, p["id"], CORRECAO_0302).json()
    assert fechada["status"] == "fechada"

    # 5. Relatório com o aviso jurídico e a exposição em "potencial máxima".
    rel = client.get(f"/auditorias/{aud_id}/relatorio").json()
    assert "não afirma se há insalubridade" in rel["texto"]
    assert rel["itens"]


@pytest.mark.e2e
@pytest.mark.skipif(os.getenv("HEITOR_E2E") != "1", reason="E2E com IA: rode com HEITOR_E2E=1 (custa centavos)")
@pytest.mark.skipif(not (FOTOS / "fabio-0310.jpg").exists(), reason="fotos de teste fora do Git (fotos_teste/)")
def test_e2e_ficha_de_papel_com_ia(monkeypatch):
    monkeypatch.setenv("HEITOR_LLM", "off")  # agente determinístico; a leitura da foto usa a IA de verdade
    from heitor.agente.grafo import conferir_e_auditar
    from tests.avaliar_assinaturas import planilha_do_gabarito
    from tests.avaliar_fotos import classe_assinatura

    g = json.loads((GABARITOS / "fabio-0310.json").read_text())
    planilha = planilha_do_gabarito(g)
    isca = dict(planilha[0], linha=99, data="2026-10-15", epi="cinto de segurança", ca="12345")
    eventos = []
    with stubs_de_dados():
        r = conferir_e_auditar("au-e2e-foto", planilha + [isca], {planilha[0]["funcionario_id"]: str(FOTOS / "fabio-0310.jpg")},
                               eventos.append)

    # Segurança 1: nenhuma entrega sem assinatura (ou isca) vira "assinada com confiança".
    # (as linhas não vêm no resultado; conferimos pelos achados de assinatura)
    com_achado = {a["linha"] for a in r["achados"] if a["regra"] == "assinatura_ausente"}
    no_grupo = {a["linha"] for a in r["achados"] if a.get("grupo")}
    for e in g["entregas"]:
        if classe_assinatura(e.get("assinatura")) != "presente":
            assert e["linha"] in com_achado | no_grupo, f"linha {e['linha']} sem assinatura passou como assinada"
    assert 99 in com_achado | no_grupo, "entrega isca passou como assinada"
    # Segurança 2: tudo o que é dúvida chega ao técnico numa conferência só.
    conferencias = [p for p in r["pendencias"] if p["acao"].startswith("conferir na ficha física:")]
    assert len(conferencias) <= 1
    # Log em sequência, começando pela conferência das assinaturas.
    assert [e.passo for e in eventos] == list(range(1, len(eventos) + 1))
    assert any(e.ferramenta == "conferir_ficha_de_papel" for e in eventos)
