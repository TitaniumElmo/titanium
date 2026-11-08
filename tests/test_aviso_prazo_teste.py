import logging
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from heitor.api import cobranca
from heitor.api.estado import estado
from heitor.api.ferramentas import criar_pendencia
from heitor.api.main import app

AVISO = ("ATENÇÃO: HEITOR_PRAZO_TESTE={n} ligada, o relógio da cobrança está {sentido} {dias} dias; "
         "não usar na demo")


def aviso(n):
    return AVISO.format(n=n, sentido="adiantado" if n > 0 else "atrasado", dias=abs(n))


class Registros(logging.Handler):
    """Faz o papel do caplog (o antes_do_pr.sh roda o pytest com -p no:logging)."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.mensagens = []

    def emit(self, record):
        self.mensagens.append((record.levelno, record.getMessage()))


@pytest.fixture
def registros():
    h, logger = Registros(), logging.getLogger("heitor.cobranca")
    nivel = logger.level
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
    yield h
    logger.removeHandler(h)
    logger.setLevel(nivel)


def invalidos(registros):
    return [m for nivel, m in registros.mensagens if m.startswith("HEITOR_PRAZO_TESTE inválida")]


def avisos(registros):
    return [m for nivel, m in registros.mensagens if m.startswith("ATENÇÃO: HEITOR_PRAZO_TESTE")]


def pendencia_vencendo_em(dias):
    aud = estado.novo_id("au")
    estado.criar_auditoria(aud, [])
    achado = {"id": "a-1", "auditoria_id": aud, "funcionario_id": "0302", "linha": None, "regra": "epi_inadequado",
              "gravidade": "irregular", "tipo": "corrigivel", "evidencia": "x", "acao_sugerida": "y"}
    return criar_pendencia(achado, "tecnico", "y", (date.today() + timedelta(days=dias)).isoformat())


def test_aviso_na_subida_do_servidor(monkeypatch, registros):
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "7")
    with TestClient(app):
        pass
    assert avisos(registros) == [aviso(7)]
    assert all(nivel == logging.WARNING for nivel, m in registros.mensagens if m.startswith("ATENÇÃO"))


@pytest.mark.parametrize("valor", [None, "", "0", "abc", "1.5"])
def test_sem_aviso_quando_desligada(monkeypatch, registros, valor):
    if valor is None:
        monkeypatch.delenv("HEITOR_PRAZO_TESTE", raising=False)
    else:
        monkeypatch.setenv("HEITOR_PRAZO_TESTE", valor)
    with TestClient(app):
        pass
    cobranca.cobrar_atrasadas()
    assert avisos(registros) == []


def test_aviso_a_cada_ciclo_que_adianta_o_relogio(client, monkeypatch, registros):
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "10")
    cobranca.cobrar_atrasadas()
    cobranca.cobrar_atrasadas()
    assert avisos(registros) == [aviso(10)] * 2


def test_data_explicita_nao_adianta_o_relogio_e_nao_avisa(client, monkeypatch, registros):
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "10")
    cobranca.cobrar_atrasadas(date(2026, 11, 20))
    assert avisos(registros) == []


def test_o_aviso_nao_muda_o_comportamento(client, monkeypatch, registros):
    p = pendencia_vencendo_em(3)
    monkeypatch.delenv("HEITOR_PRAZO_TESTE", raising=False)
    assert cobranca.cobrar_atrasadas() == [] and avisos(registros) == []
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "5")
    assert [f["pendencia_id"] for f in cobranca.cobrar_atrasadas()] == [p["id"]]
    assert cobranca.hoje() == date.today() + timedelta(days=5)
    assert len(avisos(registros)) == 1


@pytest.mark.parametrize("valor,n,aviso_esperado", [
    ("0", 0, None),
    ("3", 3, aviso(3)),
    ("-2", -2, aviso(-2)),
    ("abc", 0, None),
    ("", 0, None),
    (None, 0, None),
])
def test_dias_adiantados_e_aviso_para_zero_positivo_negativo_e_invalido(monkeypatch, registros, valor, n, aviso_esperado):
    if valor is None:
        monkeypatch.delenv("HEITOR_PRAZO_TESTE", raising=False)
    else:
        monkeypatch.setenv("HEITOR_PRAZO_TESTE", valor)
    assert cobranca.dias_adiantados() == n
    assert cobranca.hoje() == date.today() + timedelta(days=n)
    assert cobranca.avisar_prazo_teste() == n
    assert avisos(registros) == ([aviso_esperado] if aviso_esperado else [])


def test_relogio_atrasado_cobra_menos_e_avisa(client, monkeypatch, registros):
    p = pendencia_vencendo_em(-3)
    monkeypatch.delenv("HEITOR_PRAZO_TESTE", raising=False)
    assert [f["pendencia_id"] for f in cobranca.cobrar_atrasadas()] == [p["id"]]
    estado.atualizar_pendencia(p["id"], lambda x: setattr(x, "cobrancas", 0) or x.historico.clear())
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "-5")
    assert cobranca.cobrar_atrasadas() == []
    assert avisos(registros) == [aviso(-5)]


@pytest.mark.parametrize("valor", ["--3", "---", "1.5"])
def test_valor_invalido_vira_zero_avisa_uma_vez_e_nao_quebra_a_cobranca(client, monkeypatch, registros, valor):
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", valor)
    assert cobranca.dias_adiantados() == 0
    assert cobranca.hoje() == date.today()
    assert invalidos(registros) == []  # hoje() e dias_adiantados() não registram: rodam a cada cobrança

    p = pendencia_vencendo_em(-3)
    assert [f["pendencia_id"] for f in cobranca.cobrar_atrasadas()] == [p["id"]]  # relógio normal
    assert invalidos(registros) == [f"HEITOR_PRAZO_TESTE inválida ({valor!r}), ignorada"]
    assert avisos(registros) == []

    assert cobranca.avisar_prazo_teste() == 0
    assert len(invalidos(registros)) == 2  # uma por chamada de avisar_prazo_teste


def test_valor_invalido_na_subida_do_servidor_nao_derruba(monkeypatch, registros):
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "--3")
    with TestClient(app):
        pass
    assert invalidos(registros) == ["HEITOR_PRAZO_TESTE inválida ('--3'), ignorada"]


@pytest.mark.parametrize("valor", [None, "", "  ", "0", "5", "-5"])
def test_valor_valido_ou_vazio_nao_gera_aviso_de_invalido(monkeypatch, registros, valor):
    if valor is None:
        monkeypatch.delenv("HEITOR_PRAZO_TESTE", raising=False)
    else:
        monkeypatch.setenv("HEITOR_PRAZO_TESTE", valor)
    cobranca.avisar_prazo_teste()
    assert invalidos(registros) == []
