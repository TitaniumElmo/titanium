"""Planilha corrigida subida de novo pela tela também fecha as pendências (antes só o vigia conciliava).

Caso do jurado: ele não tem a pasta do Drive; edita a planilha dele e sobe de novo.
"""

from heitor.api.estado import estado
from tests.test_api import esperar
from tests.test_vigia import FICHAS, PROTETOR_0302, ate, pendencias_abertas


def _subir(client, csv: str) -> str:
    r = client.post("/auditorias", files=[("arquivos", ("fichas.csv", csv.encode(), "text/csv"))])
    aid = r.json()["id"]
    esperar(client, aid)
    return aid


def test_subir_a_planilha_corrigida_fecha_a_pendencia(client):
    _subir(client, FICHAS)
    [p] = pendencias_abertas("0302", "epi_inadequado")
    outras = {x.id for x in estado.listar_pendencias(funcionario_id="0302") if x.id != p.id and x.status != "fechada"}

    _subir(client, FICHAS + PROTETOR_0302)  # o jurado registrou a entrega do protetor e subiu de novo
    ate(lambda: estado.obter_pendencia(p.id).status == "fechada")  # a conciliação roda logo depois da auditoria
    # as outras pendências do Rafael continuam abertas (o problema delas não foi corrigido)
    assert all(estado.obter_pendencia(i).status != "fechada" for i in outras)


def test_subir_a_mesma_planilha_nao_fecha_nada(client):
    _subir(client, FICHAS)
    [p] = pendencias_abertas("0302", "epi_inadequado")
    _subir(client, FICHAS)
    assert estado.obter_pendencia(p.id).status != "fechada"
