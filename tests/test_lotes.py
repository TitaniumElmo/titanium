"""E-mail agrupado (um por destinatário), aviso de edição pela versão e relógio da cobrança."""

import threading
import time
from datetime import date

from heitor.api import cobranca, ferramentas, notificacao
from heitor.api.estado import estado
from heitor.api.vigia import Vigia
from heitor.contrato import Achado
from tests.test_api import esperar
from tests.test_notificacao import enviados  # noqa: F401 (fixture)
from tests.test_vigia import FICHAS, PROTETOR_0302, _DriveFalso, disparar, esperar_auditoria


def _achado(i, auditoria_id, tipo="prova"):
    return Achado(id=f"a-{i}", auditoria_id=auditoria_id, funcionario_id=f"03{i:02d}", linha=1, regra="ca_vencido",
                  gravidade="risco", tipo=tipo, evidencia=f"linha 1, CA vencido ({i})",
                  acao_sugerida=f"ação da regra {i}")


def test_lote_manda_um_email_por_destinatario(client, enviados):  # noqa: F811
    estado.criar_auditoria("au-l", [])
    with notificacao.agrupar("au-l"):
        for i in range(3):
            ferramentas.criar_pendencia(_achado(i, "au-l"), "rh", "texto do LLM", date(2026, 11, 10 + i))
        ferramentas.criar_pendencia(_achado(9, "au-l", "corrigivel"), "tecnico", "x", date(2026, 11, 12))
        assert enviados == []  # nada sai antes do fim do lote

    por_destino = {e["para"]: e for e in enviados}
    assert len(enviados) == 2 and set(por_destino) == {"rh@teste", "tecnico@teste"}
    rh = por_destino["rh@teste"]
    assert rh["assunto"] == "Elmo: 3 pendências novas"
    assert [l for l in rh["texto"].splitlines() if "O que fazer" in l] == [
        "   O que fazer: ação da regra 0", "   O que fazer: ação da regra 1", "   O que fazer: ação da regra 2"]
    assert "texto do LLM" not in rh["texto"]
    assert por_destino["tecnico@teste"]["assunto"].startswith("Nova pendência do Elmo: ação da regra 9")


def test_lote_junta_pendencias_criadas_em_varias_threads(client, enviados):  # noqa: F811
    """O agente cria as pendências de cada funcionário numa thread: o lote é pela chave, não pela thread."""
    estado.criar_auditoria("au-t", [])
    with notificacao.agrupar("au-t"):
        ts = [threading.Thread(target=ferramentas.criar_pendencia,
                               args=(_achado(i, "au-t"), "rh", "x", date(2026, 11, 10))) for i in range(6)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    assert len(enviados) == 1 and enviados[0]["assunto"] == "Elmo: 6 pendências novas"


def test_auditoria_pela_api_manda_um_email_por_destinatario(client, enviados):  # noqa: F811
    r = client.post("/auditorias", data={"exemplo": "true"})
    esperar(client, r.json()["id"])
    pendencias = client.get("/pendencias", params={"auditoria_id": r.json()["id"]}).json()
    assert len(pendencias) >= 4
    assert len(enviados) == len({p["destino"] for p in pendencias})  # 1 e-mail por destino, não 1 por pendência


def test_cobranca_agrupada(client, enviados):  # noqa: F811
    estado.criar_auditoria("au-c", [])
    for i in range(3):
        ferramentas.criar_pendencia(_achado(i, "au-c"), "rh", "x", date(2026, 11, 1))
    enviados.clear()
    feitas = cobranca.cobrar_atrasadas(date(2026, 11, 20))
    assert len(feitas) == 3
    assert len(enviados) == 1 and enviados[0]["assunto"] == "Elmo: 3 pendências em atraso"


def test_edicao_detectada_assim_que_a_versao_muda(client, tmp_path):
    drive = _DriveFalso(versao=10, exportacoes=[FICHAS])
    v = Vigia(drive, 0.1, tmp_path / "trabalho")
    esperar_auditoria(disparar(v)["auditoria_id"])

    drive.versao = 11  # o Google anuncia a versão nova; o CSV exportado segue velho por 3 consultas
    drive.exportacoes = [FICHAS, FICHAS, FICHAS, FICHAS + PROTETOR_0302]
    avisos = []
    for _ in range(5):
        antes = len(estado.eventos_desde("vigia"))
        r = v.verificar()
        avisos.append((len(estado.eventos_desde("vigia")) - antes, r.get("mudou")))
    # consulta 1: aviso na hora (versão); o conteúdo que chega na 4ª é a mesma edição: não repete
    assert avisos == [(1, False), (0, False), (0, False), (0, False), (0, True)]


def test_relogio_da_cobranca_sem_vigia(monkeypatch):
    chamadas = []
    monkeypatch.setattr(cobranca, "cobrar_atrasadas", lambda: chamadas.append(time.monotonic()))
    parar = cobranca.iniciar_relogio(0.02)
    time.sleep(0.15)
    parar.set()
    vistas = len(chamadas)
    time.sleep(0.06)
    assert vistas >= 2 and len(chamadas) <= vistas + 1  # rodou várias vezes e parou
