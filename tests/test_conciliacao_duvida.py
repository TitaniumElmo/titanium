"""Ausência de prova não é prova (pedido da Luciana, 08/11).

Antes: quando uma regra falhava (ex.: base CAEPI ausente), o agente registrava o auditar_ficha como ferramenta
que RODOU; a conciliação via "rodou e o problema sumiu" e fechava como corrigida uma pendência que ninguém
conferiu. Agora: falha vira ERRO no log, e a conciliação não fecha nada de quem ficou em dúvida.
"""

from datetime import datetime

from heitor.agente import ferramentas as F
from heitor.agente.grafo import rodar_auditoria
from heitor.api import vigia as modulo_vigia
from heitor.api.estado import estado
from heitor.contrato import Achado, Evento
from tests.test_vigia import disparar, esperar_auditoria, pasta, pendencias_abertas, vigia, FICHAS  # noqa: F401


def test_regra_que_falha_vira_erro_no_log_e_nao_repete(monkeypatch):
    monkeypatch.setenv("HEITOR_LLM", "off")

    def quebra(*a, **k):
        raise FileNotFoundError("base CAEPI não encontrada")

    monkeypatch.setitem(F.IMPL, "audita_linha", quebra)
    monkeypatch.setitem(F.IMPL, "audita_funcionario", quebra)
    eventos = []
    linha = {"funcionario_id": "0402", "nome": "X", "funcao": "servente", "linha": 1, "data": "2024-02-05",
             "epi": "botina", "qtd": 1, "ca": "28499", "motivo": "T", "assinatura": True, "origem": "t"}
    r = rodar_auditoria("au-falha", [linha], eventos.append)
    regras = [e for e in eventos if e.ferramenta in ("auditar_ficha", "audita_linha", "audita_funcionario")]
    assert regras and all(e.tipo == "erro" for e in regras)  # nada disso conta como "rodou"
    assert sum(e.ferramenta == "auditar_ficha" for e in regras) == 1  # não tenta 11 vezes
    assert [a["regra"] for a in r["achados"]] == ["falha_de_ferramenta"]


def _auditoria_com_duvida(aid: str, fid: str, regra: str) -> str:
    """Uma auditoria nova, concluída, em que o agente rodou para o funcionário mas deixou dúvida sobre ele."""
    estado.criar_auditoria(aid, ["fichas.csv"], disparado_por="alteracao_planilha")
    estado.registrar_evento(Evento(auditoria_id=aid, funcionario_id=fid, passo=1, tipo="ferramenta",
                                   ferramenta="auditar_ficha", entrada={}, saida={}, custo_usd=0.0, ts=datetime.now()))
    estado.salvar_achado(Achado(id="a-duvida", auditoria_id=aid, funcionario_id=fid, linha=None, regra=regra,
                                gravidade="risco", tipo="corrigivel", evidencia="dúvida", acao_sugerida="conferir"))
    estado.atualizar_auditoria(aid, status="concluida")
    return aid


def test_conciliacao_nao_fecha_pendencia_de_quem_ficou_em_duvida(vigia, pasta):  # noqa: F811
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    esperar_auditoria(disparar(vigia)["auditoria_id"])
    [p] = pendencias_abertas("0302", "epi_inadequado")

    for regra in ("falha_de_ferramenta", "leitura_incerta"):
        aid = _auditoria_com_duvida(f"au-duvida-{regra}", "0302", regra)
        linhas = [l for l in estado.obter_linhas(p.auditoria_id) if l.funcionario_id == "0302"]
        r = modulo_vigia.conciliar(aid, linhas)
        assert estado.obter_pendencia(p.id).status == "aberta", regra
        assert any(x["pendencia_id"] == p.id and "dúvida" in x["motivo"] for x in r), r
