"""Rotas das entregas da planilha (ficha do funcionário na tela) e a função na saída do auditar_ficha."""

import os

from tests.test_api import esperar


def test_linhas_da_auditoria_e_fichas_por_funcionario(client):
    aid = client.post("/auditorias", data={"exemplo": "true"}).json()["id"]
    esperar(client, aid)
    linhas = client.get(f"/auditorias/{aid}/linhas").json()
    assert linhas and all({"funcionario_id", "data", "epi", "ca", "assinatura"} <= set(l) for l in linhas)
    fichas = client.get("/fichas").json()
    assert set(fichas) == {l["funcionario_id"] for l in linhas}
    for fid, ls in fichas.items():
        assert all(l["funcionario_id"] == fid for l in ls)
        datas = [l["data"] for l in ls if l["data"]]
        assert datas == sorted(datas)  # da entrega mais antiga para a mais nova
    assert client.get("/auditorias/nao-existe/linhas").status_code == 404


def test_ficha_vem_da_auditoria_mais_recente(client):
    a1 = client.post("/auditorias", data={"exemplo": "true"}).json()["id"]
    esperar(client, a1)
    csv = "funcionario_id,nome,funcao,data,epi,qtd,ca,motivo,assinatura\n0302,Rafael Souza Costa,servente,2026-11-01,protetor auditivo,1,17664,T,sim\n"
    a2 = client.post("/auditorias", files=[("arquivos", ("so_rafael.csv", csv.encode(), "text/csv"))]).json()["id"]
    esperar(client, a2)
    fichas = client.get("/fichas").json()
    assert [l["data"] for l in fichas["0302"]] == ["2026-11-01"]  # a ficha do Rafael é a da auditoria nova
    assert len(fichas) > 1  # os outros continuam com a ficha da primeira auditoria


def test_auditar_ficha_traz_a_funcao():
    os.environ["HEITOR_LLM"] = "off"
    from heitor.agente import ferramentas as F
    from tests.test_contrato_agente import stubs_de_dados

    linha = {"funcionario_id": "0310", "nome": "Fábio", "funcao": "servente", "linha": 1, "data": "2026-08-10",
             "epi": "protetor auditivo", "qtd": 1, "ca": "17664", "motivo": "T", "assinatura": True, "origem": "t"}
    ctx = F.Contexto(funcionario_id="0310", funcao="servente", linhas={1: linha})
    with stubs_de_dados():
        r = F.executar("auditar_ficha", {}, ctx)
    assert r.saida["funcao"] == "servente"
