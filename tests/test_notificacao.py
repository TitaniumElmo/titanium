"""Aviso por e-mail: leva a ação da regra, nunca o texto escrito pelo LLM."""

from datetime import date

import pytest

from heitor.api import ferramentas, notificacao
from heitor.api.estado import estado
from heitor.contrato import Achado

INJECAO = "Acesse http://golpe.exemplo/login e confirme a senha do RH"


@pytest.fixture
def enviados(monkeypatch):
    caixa = []
    monkeypatch.setenv("SMTP_HOST", "smtp.teste")
    monkeypatch.setenv("HEITOR_EMAIL_TECNICO", "tecnico@teste")
    monkeypatch.setenv("HEITOR_EMAIL_RH", "rh@teste")

    # Captura o que seria enviado, sem thread e sem SMTP (sem mexer no threading do processo).
    monkeypatch.setattr(notificacao, "_disparar",
                        lambda para, assunto, texto: caixa.append({"para": para, "assunto": assunto, "texto": texto}))
    return caixa


def _achado(auditoria_id):
    return Achado(id="a-1", auditoria_id=auditoria_id, funcionario_id="0302", linha=6, regra="ca_vencido",
                  gravidade="risco", tipo="prova", evidencia="linha 6, CA 28499 vencido na entrega",
                  acao_sugerida="pedir nota fiscal ao RH")


def test_email_leva_a_acao_da_regra_e_nao_a_do_llm(client, enviados):
    estado.criar_auditoria("au-x", [])
    p = ferramentas.criar_pendencia(_achado("au-x"), "rh", INJECAO, date(2026, 11, 10))
    assert p["acao"] == INJECAO  # a pendência guarda o texto do agente (vai para a tela)
    [email] = enviados
    assert email["para"] == "rh@teste"
    assert "pedir nota fiscal ao RH" in email["texto"] and "pedir nota fiscal ao RH" in email["assunto"]
    assert "golpe" not in email["texto"] and "golpe" not in email["assunto"]
    assert "10/11/2026" in email["texto"]


def test_reaberta_tambem_leva_a_acao_da_regra(client, enviados):
    estado.criar_auditoria("au-y", [])
    p = ferramentas.criar_pendencia(_achado("au-y"), "rh", INJECAO, date(2026, 11, 10))
    ferramentas.marcar_aguardando(p["id"])
    ferramentas.fechar_pendencia(p["id"], False)
    reaberta = enviados[-1]
    assert reaberta["assunto"].startswith("Pendência reaberta pelo Heitor")
    assert "pedir nota fiscal ao RH" in reaberta["texto"] and "golpe" not in reaberta["texto"]


def test_sem_smtp_so_registra_no_log(client, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    registros = []
    monkeypatch.setattr(notificacao.log, "info", lambda msg, *args: registros.append(msg % args))
    enviar = []
    monkeypatch.setattr(notificacao, "_enviar", lambda *a: enviar.append(a))
    estado.criar_auditoria("au-z", [])
    ferramentas.criar_pendencia(_achado("au-z"), "rh", "x", date(2026, 11, 10))
    assert any("sem e-mail configurado" in r for r in registros) and enviar == []


def test_nome_do_produto_no_email_e_configuravel(client, enviados, monkeypatch):
    monkeypatch.setenv("HEITOR_NOME_NO_EMAIL", "Elmo")
    estado.criar_auditoria("au-n", [])
    ferramentas.criar_pendencia(_achado("au-n"), "rh", "x", date(2026, 11, 10))
    [email] = enviados
    assert email["assunto"].startswith("Nova pendência do Elmo")
    assert "O Elmo aponta lacunas" in email["texto"] and "Heitor" not in email["texto"] + email["assunto"]
