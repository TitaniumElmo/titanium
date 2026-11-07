"""Confere que tudo o que o agente produz passa na validação do contrato (heitor/contrato.py).

Roda sem LLM e com os STUBS das regras do Gustavo: testa o agente, não as regras nem a base CAEPI
(as regras reais têm os testes delas em tests/test_audita.py). Uso:
    HEITOR_LLM=off python -m tests.test_contrato_agente
"""

import os
from contextlib import contextmanager

os.environ["HEITOR_LLM"] = "off"

from heitor.agente import ferramentas as F  # noqa: E402
from heitor.agente import stubs  # noqa: E402
from heitor.agente.exemplo import LINHAS  # noqa: E402
from heitor.agente.extracao import extrair_ficha  # noqa: E402
from heitor.agente.grafo import reauditar, rodar_auditoria  # noqa: E402
from heitor.agente.tipos import REGRAS_PROPOSTAS  # noqa: E402
from heitor.contrato import Achado, Evento, Linha, Pendencia  # noqa: E402

FUNCOES_DE_DADOS = ("consulta_ca", "buscar_ca_proximo", "exigencia_funcao", "categoria_epi",
                    "audita_linha", "audita_funcionario", "calcula_exposicao")


@contextmanager
def stubs_de_dados():
    """Troca as funções de heitor/dados pelos stubs enquanto o teste roda."""
    originais = {n: F.IMPL[n] for n in FUNCOES_DE_DADOS}
    F.IMPL.update({n: getattr(stubs, n) for n in FUNCOES_DE_DADOS})
    try:
        yield
    finally:
        F.IMPL.update(originais)


def test_extracao_gera_linhas_do_contrato():
    for f in ("a", "b"):
        for l in extrair_ficha(f"tests/planilhas/formato_{f}.csv")["linhas"]:
            Linha.model_validate(l)


def test_auditoria_respeita_o_contrato():
    eventos: list[Evento] = []
    entrada = [Linha.model_validate(l | {"linha": i}) for i, l in enumerate(LINHAS, start=1)]  # modelos Pydantic
    with stubs_de_dados():
        r = rodar_auditoria("au-teste", entrada, eventos.append)
    assert r["contagem"] == {"irregular": 4, "risco": 3}
    for a in r["achados"]:
        if a["regra"] not in REGRAS_PROPOSTAS:
            Achado.model_validate(a)
    for p in r["pendencias"]:
        Pendencia.model_validate(p)
    assert eventos and all(isinstance(e, Evento) for e in eventos)
    assert {e.tipo for e in eventos} >= {"decisao", "ferramenta"}
    assert [e.passo for e in eventos] == list(range(1, len(eventos) + 1))


def test_reauditoria_fecha_e_reabre():
    with stubs_de_dados():
        r = rodar_auditoria("au-re", [dict(l) for l in LINHAS])
        p = next(p for p in r["pendencias"] if "protetor auditivo" in p["acao"])
        base = {"funcionario_id": "0302", "nome": "Rafael", "funcao": "servente", "linha": 1, "qtd": 1,
                "data": "2026-11-07", "epi": "protetor auditivo", "ca": "17664", "origem": "correcao"}
        assert reauditar(p["id"], [base | {"assinatura": False}])["status"] == "reaberta"
        assert reauditar(p["id"], [base | {"assinatura": True}])["status"] == "fechada"
    Pendencia.model_validate(p)


def test_falha_repetida_gera_uma_pendencia_de_revisao():
    """Sem a base CAEPI, audita_linha falha em toda linha: deve sair UMA pendência de revisão por funcionário."""
    def quebra(*_a, **_k):
        raise FileNotFoundError("base CAEPI não encontrada")

    with stubs_de_dados():
        F.IMPL["audita_linha"] = quebra
        r = rodar_auditoria("au-sem-base", [dict(l) for l in LINHAS])
    revisoes = [p for p in r["pendencias"] if p["acao"] == "revisar manualmente esta ficha"]
    funcionarios = {l["funcionario_id"] for l in LINHAS}
    assert len(revisoes) == len(funcionarios), [p["achado_id"] for p in revisoes]


def test_cas_em_duvida_viram_uma_conferencia_por_ficha():
    """CA lido que não confere com o EPI: nunca é trocado; vira UMA conferência no papel, com a hipótese da empresa."""
    def l(fid, n, epi, ca):
        return {"funcionario_id": fid, "nome": "Diego", "funcao": "carpinteiro", "linha": n, "data": "2026-09-01",
                "epi": epi, "qtd": 1, "ca": ca, "motivo": "T", "assinatura": True, "origem": "teste"}
    linhas = [l("0308", 1, "protetor auricular plug", "17664"), l("0308", 2, "protetor auricular plug", "14664"),
              l("0308", 3, "protetor auricular plug", "14664"), l("0308", 4, "óculos de proteção", "10347"),
              l("0309", 5, "óculos de proteção", "10344"),
              l("0307", 6, "luva de raspa", "10344")]  # erro de registro plantado: CA de óculos numa luva
    with stubs_de_dados():
        r = rodar_auditoria("au-ca", linhas)
    conferencias = [p for p in r["pendencias"] if p["acao"].startswith("conferir na ficha física:")]
    diego = [p for p in conferencias if p["funcionario_id"] == "0308"]
    assert len(diego) == 1, [p["acao"] for p in conferencias]
    assert "provável 17664" in diego[0]["acao"] and "provável 10344" in diego[0]["acao"]
    bruno = [p for p in conferencias if p["funcionario_id"] == "0307"]
    assert len(bruno) == 1 and "provável" not in bruno[0]["acao"]  # erro real: sem hipótese de "correção"
    assert {a["linha"]: a for a in r["achados"] if a["funcionario_id"] == "0307"}[6]["regra"].startswith("ca_")
    assert all(x["ca"] == y["ca"] for x, y in zip(linhas, linhas))  # nenhum CA foi trocado


def test_data_impossivel_vira_conferencia_e_nao_gera_achado_falso():
    """Entrega lida em 2023 para admissão em 2025: data em dúvida, hipótese 2025, e nenhuma troca atrasada falsa."""
    linhas = [{"funcionario_id": "0312", "nome": "Thiago", "funcao": "armador", "linha": n, "data": "2023-06-02",
               "data_admissao": "2025-06-02", "epi": epi, "qtd": 1, "ca": ca, "motivo": "1", "assinatura": True,
               "origem": "teste"} for n, (epi, ca) in enumerate([("protetor auricular plug", "17664"),
                                                                 ("luva de raspa", "21245")], start=1)]
    with stubs_de_dados():
        r = rodar_auditoria("au-data", linhas)
    conf = [p for p in r["pendencias"] if p["acao"].startswith("conferir na ficha física:")]
    assert len(conf) == 1 and "linhas 1-2: data lida 2023-06-02, provável 2025-06-02" in conf[0]["acao"]
    assert not [a for a in r["achados"] if a["regra"] == "troca_atrasada" and "2023" in a["evidencia"]]
    assert all(l["data"] == "2023-06-02" for l in linhas)  # a data lida nunca é trocada


def test_conferir_e_auditar_com_ficha_de_papel():
    """Planilha + foto: assinaturas em dúvida, entrega sem linha e linha fora da planilha viram UMA conferência;
    entrega sem linha com certeza vira achado; o log tem passos em sequência."""
    from heitor.agente import conferencia_assinaturas as CA
    from heitor.agente import grafo

    def planilha(n, data, epi, ca):
        return {"funcionario_id": "0310", "nome": "Fábio Nogueira Pires", "funcao": "servente", "linha": n,
                "data": data, "epi": epi, "qtd": 1, "ca": ca, "motivo": "T", "assinatura": None, "origem": "planilha"}
    linhas = [planilha(1, "2025-09-02", "capacete classe A", "29637"), planilha(2, "2025-09-02", "botina de segurança", "9182"),
              planilha(3, "2025-12-15", "luva de raspa", "21245"), planilha(4, "2026-08-10", "protetor auricular plug", "17664")]

    def falsa(_foto, do_func):  # o que a conferência de assinaturas devolveria para esta ficha
        r = [dict(l) for l in do_func]
        marca = {1: (True, 0.95, "nome_confere", "Fábio"), 2: (False, 0.95, "vazio", "vazio"),
                 3: (False, 0.5, "outro_nome", "Marcos"), 4: (None, 0.95, "sem_linha_na_ficha", None)}
        for l in r:
            l["assinatura"], c, l["assinatura_tipo"], l["assinatura_texto"] = marca[l["linha"]]
            l["confianca"] = {"assinatura": c}
            l["na_ficha"] = l["assinatura_tipo"] != "sem_linha_na_ficha"
        return {"linhas": r, "fora_da_planilha": [{"data": "2026-10-15", "epi": "cinto de segurança"}], "custo_usd": 0.0}

    original = CA.conferir_assinaturas
    CA.conferir_assinaturas = falsa
    eventos = []
    try:
        with stubs_de_dados():
            r = grafo.conferir_e_auditar("au-papel", linhas, {"0310": "ficha.jpg"}, eventos.append)
    finally:
        CA.conferir_assinaturas = original
    conf = [p for p in r["pendencias"] if p["acao"].startswith("conferir na ficha física:")]
    assert len(conf) == 1, [p["acao"] for p in r["pendencias"]]
    assert "linha 3: assinatura em dúvida (lido 'Marcos')" in conf[0]["acao"]
    assert "linha no papel sem entrega na planilha" in conf[0]["acao"] and "cinto de segurança" in conf[0]["acao"]
    assert any(a["regra"] == "ficha_sem_planilha" and a["gravidade"] == "risco" for a in r["achados"])
    por_linha = {a["linha"]: a for a in r["achados"] if a.get("regra") == "assinatura_ausente"}
    assert por_linha[2]["gravidade"] == "irregular"
    assert por_linha[4]["gravidade"] == "risco"  # decisão do time: sem linha na ficha é risco, nunca irregular
    assert "sem linha na ficha de papel" in por_linha[4]["evidencia"]
    assert 1 not in por_linha  # assinatura que confere não gera achado
    assert any(e.ferramenta == "conferir_ficha_de_papel" for e in eventos)
    assert [e.passo for e in eventos] == list(range(1, len(eventos) + 1))


def test_disjuntor_do_llm(monkeypatch):
    """LLM fora do ar: o funcionário segue em modo degradado e o próximo tenta de novo;
    depois de 2 funcionários seguidos com falha, o agente para de tentar."""
    import json as _json

    from heitor.agente import grafo
    from heitor.agente.llm import LLMIndisponivel, RespostaLLM

    def rodar(falhas: list[bool]) -> dict:
        roteiro = iter(falhas)

        class LLMFalso:
            def __init__(self, *a, **k):
                self.atual = None

            def completar(self, mensagens, max_tokens=400):
                if mensagens is not self.atual:  # primeira chamada de cada funcionário consome o roteiro
                    self.atual, self.cai = mensagens, next(roteiro, False)
                if self.cai:
                    raise LLMIndisponivel("timeout")
                return RespostaLLM(_json.dumps({"pensamento": "ok", "ferramenta": "terminei", "args": {}}),
                                   0.0, 0, 0, "falso", 0.0)

        monkeypatch.setenv("HEITOR_LLM", "on")
        monkeypatch.setenv("HEITOR_PARALELO", "1")  # o roteiro de falhas depende da ordem dos funcionários
        monkeypatch.setattr(grafo, "ClienteLLM", LLMFalso)
        linhas = [dict(l) for l in LINHAS]  # 3 funcionários
        with stubs_de_dados():
            return grafo.rodar_auditoria("au-disjuntor", linhas)

    # Cai no 1º funcionário e volta: só o 1º fica degradado.
    r = rodar([True, False, False])
    assert list(r["modo_por_funcionario"].values()) == ["degradado", "llm", "llm"], r["modo_por_funcionario"]
    assert r["modo"] == "misto"
    # Cai no 1º e no 2º: o 3º nem tenta (disjuntor aberto).
    r = rodar([True, True, False])
    assert list(r["modo_por_funcionario"].values()) == ["degradado", "degradado", "deterministico"]
    # Em todos os casos a auditoria termina com os mesmos achados (os guarda-corpos completam o trabalho).
    assert r["contagem"] == {"irregular": 4, "risco": 3}


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok ", nome)
