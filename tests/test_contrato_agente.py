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


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok ", nome)
