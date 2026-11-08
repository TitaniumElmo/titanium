"""Rotas de leitura da interface: funcionários, cronograma, relatório por período e configurações."""

from datetime import date, timedelta

import pytest

from heitor.api import configuracoes, visoes
from tests.test_api import esperar

CSV = (
    "funcionario_id,nome,funcao,data,epi,qtd,ca,motivo,assinatura\n"
    "0302,Rafael Souza Costa,servente,2026-06-01,protetor auditivo,1,17664,T,sim\n"
    "0302,Rafael Souza Costa,servente,2026-06-01,capacete,1,29637,T,sim\n"
)


@pytest.fixture(autouse=True)
def _config_padrao():
    configuracoes.restaurar()
    yield
    configuracoes.restaurar()


def _auditar_csv(client, csv=CSV):
    aid = client.post("/auditorias", files=[("arquivos", ("ficha.csv", csv.encode(), "text/csv"))]).json()["id"]
    esperar(client, aid)
    return aid


def test_funcionarios_lista_e_ficha(client):
    aid = client.post("/auditorias", data={"exemplo": "true"}).json()["id"]
    esperar(client, aid)
    lista = client.get("/funcionarios").json()
    assert lista and {"funcionario_id", "nome", "funcao", "status", "achados_abertos", "pendencias_abertas", "ultima_entrega", "proxima_troca"} <= set(lista[0])
    assert all(f["status"] in ("irregular", "risco", "ok") for f in lista)
    um = client.get(f"/funcionarios/{lista[0]['funcionario_id']}").json()
    assert um["linhas"] and um["auditoria_id"] == aid
    assert {"achados", "pendencias", "trocas"} <= set(um)
    assert client.get("/funcionarios/9999").status_code == 404


def test_troca_vence_pela_vida_util_da_funcao(client):
    _auditar_csv(client)
    # protetor auditivo: 180 dias de vida útil; capacete não é exigido na tabela padrão
    hoje = date(2026, 6, 1) + timedelta(days=170)
    trocas = visoes.funcionario("0302", hoje)["trocas"]
    assert [t["epi"] for t in trocas] == ["protetor auditivo"]
    assert trocas[0]["vence"] == (date(2026, 6, 1) + timedelta(days=180)).isoformat()


def test_cronograma_traz_trocas_e_prazos_das_pendencias(client):
    _auditar_csv(client)
    hoje = date(2026, 6, 1) + timedelta(days=170)
    itens = visoes.cronograma(hoje - timedelta(days=7), hoje + timedelta(days=30), hoje, antecedencia_dias=15)
    troca = [i for i in itens if i["tipo"] == "troca_epi"]
    assert len(troca) == 1 and troca[0]["status"] == "previsto" and troca[0]["titulo"] == "Trocar protetor auditivo"
    assert itens == sorted(itens, key=lambda i: (i["data"], i["tipo"]))
    # mais longe que a antecedência (15 + 15 de folga): não entra
    cedo = date(2026, 6, 1) + timedelta(days=100)
    assert not [i for i in visoes.cronograma(cedo, cedo + timedelta(days=120), cedo, antecedencia_dias=15) if i["tipo"] == "troca_epi"]


def test_cronograma_pela_rota_valida_o_intervalo(client):
    assert client.get("/cronograma").status_code == 200
    assert client.get("/cronograma?de=2026-12-31&ate=2026-01-01").status_code == 422


def test_relatorio_por_periodo(client):
    aid = client.post("/auditorias", data={"exemplo": "true"}).json()["id"]
    esperar(client, aid)
    r = client.get("/relatorio?dias=7").json()
    assert r["dias"] == 7 and len(r["serie"]) == 7
    assert {"irregular", "risco", "ok", "data"} <= set(r["serie"][-1])
    assert sum(d["irregular"] + d["risco"] + d["ok"] for d in r["serie"]) > 0  # a auditoria é de hoje
    assert set(r["por_tipo"]) == {"corrigivel", "prova", "passivo"}
    assert {"abertas", "fechadas", "reabertas", "tempo_medio_dias"} <= set(r["pendencias"])
    assert r["exposicao_total"] == pytest.approx(sum(f["valor"] for f in r["exposicao_por_funcao"]), abs=0.01)
    assert client.get("/relatorio?dias=0").status_code == 422


def test_relatorio_sem_auditorias_vem_zerado(client):
    r = client.get("/relatorio?dias=30").json()
    assert len(r["serie"]) == 30 and r["pendencias"]["abertas"] == 0
    assert r["exposicao_total"] == 0 and r["custo_medio_ficha_usd"] == 0


def test_configuracoes_ler_e_ajustar(client):
    base = client.get("/configuracoes").json()
    assert base["prazo_padrao_dias"] == 5 and base["antecedencia_troca_dias"] == 15
    novo = client.put("/configuracoes", json={"prazo_padrao_dias": 3}).json()
    assert novo["prazo_padrao_dias"] == 3 and novo["antecedencia_troca_dias"] == 15  # só o enviado muda
    assert client.get("/configuracoes").json()["prazo_padrao_dias"] == 3
    assert client.put("/configuracoes", json={"prazo_padrao_dias": 0}).status_code == 422
    assert client.put("/configuracoes", json={"intervalo_leitura_s": 1}).status_code == 422


def test_antecedencia_configurada_vale_no_cronograma(client):
    _auditar_csv(client)
    hoje = date(2026, 6, 1) + timedelta(days=130)  # a troca vence em 50 dias
    de, ate = hoje, hoje + timedelta(days=60)
    assert not [i for i in visoes.cronograma(de, ate, hoje) if i["tipo"] == "troca_epi"]  # 50 > 15 + 15
    client.put("/configuracoes", json={"antecedencia_troca_dias": 40})
    assert [i for i in visoes.cronograma(de, ate, hoje) if i["tipo"] == "troca_epi"]  # 50 <= 40 + 15


def test_restaurar_devolve_o_intervalo_ao_vigia(monkeypatch):
    from types import SimpleNamespace

    from heitor.api import config, vigia as modulo_vigia

    falso = SimpleNamespace(intervalo_s=config.VIGIA_INTERVALO_S)
    monkeypatch.setattr(modulo_vigia, "vigia", falso)
    configuracoes.ajustar(configuracoes.AjusteConfiguracao(intervalo_leitura_s=300))
    assert falso.intervalo_s == 300 and configuracoes.atual().intervalo_leitura_s == 300
    configuracoes.restaurar()
    assert falso.intervalo_s == config.VIGIA_INTERVALO_S
    assert configuracoes.atual().intervalo_leitura_s == config.VIGIA_INTERVALO_S
