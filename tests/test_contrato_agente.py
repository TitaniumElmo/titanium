"""Confere que tudo o que o agente produz passa na validação do contrato (heitor/contrato.py).

Roda sem LLM. Uso:  HEITOR_LLM=off python -m tests.test_contrato_agente
"""

import os

os.environ["HEITOR_LLM"] = "off"

from heitor.agente.exemplo import LINHAS  # noqa: E402
from heitor.agente.extracao import extrair_ficha  # noqa: E402
from heitor.agente.grafo import reauditar, rodar_auditoria  # noqa: E402
from heitor.agente.tipos import REGRAS_PROPOSTAS  # noqa: E402
from heitor.contrato import Achado, Evento, Linha, Pendencia  # noqa: E402


def test_extracao_gera_linhas_do_contrato():
    for f in ("a", "b"):
        for l in extrair_ficha(f"tests/planilhas/formato_{f}.csv")["linhas"]:
            Linha.model_validate(l)


def test_auditoria_respeita_o_contrato():
    eventos: list[Evento] = []
    entrada = [Linha.model_validate(l | {"linha": i}) for i, l in enumerate(LINHAS, start=1)]  # modelos Pydantic
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
    r = rodar_auditoria("au-re", [dict(l) for l in LINHAS])
    p = next(p for p in r["pendencias"] if "protetor auditivo" in p["acao"])
    base = {"funcionario_id": "0302", "nome": "Rafael", "funcao": "servente", "linha": 1, "qtd": 1,
            "data": "2026-11-07", "epi": "protetor auditivo", "ca": "17664", "origem": "correcao"}
    assert reauditar(p["id"], [base | {"assinatura": False}])["status"] == "reaberta"
    assert reauditar(p["id"], [base | {"assinatura": True}])["status"] == "fechada"
    Pendencia.model_validate(p)


if __name__ == "__main__":
    for nome, fn in list(globals().items()):
        if nome.startswith("test_"):
            fn()
            print("ok ", nome)
