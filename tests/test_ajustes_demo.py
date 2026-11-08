"""Ajustes antes do Demo Day: feed SSE depois do reset, token obrigatório no deploy e vigia antigo
que não grava no estado da pasta nova."""

import threading
import time

from heitor.api import config
from heitor.api import vigia as modulo_vigia
from heitor.api.estado import estado
from heitor.api.fontes import PastaLocal
from heitor.api.rotas.eventos import _continuar_de
from heitor.api.vigia import Vigia

FICHAS = config.FICHA_EXEMPLO.read_text(encoding="utf-8")


# -- item 5: feed ao vivo não fica mudo depois de um reset -----------------------------------------

def test_reconectar_na_mesma_geracao_continua_de_onde_parou():
    assert _continuar_de("3.41", 3) == 42


def test_reconectar_depois_do_reset_le_do_inicio():
    """O navegador reconecta com o Last-Event-ID antigo; o log recomeçou do zero no reset."""
    assert _continuar_de("3.41", 4) == 0


def test_id_antigo_ou_invalido_le_do_inicio():
    for ruim in ("41", None, "", "x.y", "3.", ".41"):
        assert _continuar_de(ruim, 3) == 0


def test_cada_limpeza_comeca_uma_geracao_nova(client):
    antes = estado.geracao()
    estado.limpar()
    assert estado.geracao() == antes + 1


# -- item 6: sem token no deploy, rota de administração fecha ---------------------------------------

def test_no_deploy_sem_token_as_rotas_de_admin_fecham(client, monkeypatch):
    monkeypatch.delenv("HEITOR_TOKEN_ADMIN", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    r = client.post("/fontes", json={"url": "1AbCdEfGhIjKlMnOpQrS"})
    assert r.status_code == 503 and "HEITOR_TOKEN_ADMIN" in r.json()["detail"]
    assert client.post("/fontes/padrao").status_code == 503
    assert client.put("/configuracoes", json={}).status_code == 503


def test_no_deploy_com_token_funciona(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("HEITOR_TOKEN_ADMIN", "segredo")
    assert client.post("/fontes/padrao").status_code == 401  # sem token no pedido
    r = client.post("/fontes", json={"url": "link de planilha /spreadsheets/d/1AbCdEfGhIjKlMnOpQrS"},
                    headers={"Authorization": "Bearer segredo"})
    assert r.status_code == 400  # passou do token; o link é que é recusado


def test_na_maquina_de_quem_desenvolve_continua_liberado(client, monkeypatch):
    for v in ("HEITOR_TOKEN_ADMIN", "RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "HEITOR_PRODUCAO"):
        monkeypatch.delenv(v, raising=False)
    r = client.post("/fontes", json={"url": "https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrS/edit"})
    assert r.status_code == 400  # liberada: chegou na validação do link


# -- item 7: vigia parado no meio da verificação não cria auditoria da pasta antiga -----------------

def test_vigia_parado_no_meio_nao_cria_auditoria(client, tmp_path):
    pasta = tmp_path / "pasta_antiga"
    pasta.mkdir()
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    v = Vigia(PastaLocal(pasta), intervalo_s=60, pasta_trabalho=tmp_path / "trabalho")
    v.verificar()  # viu o arquivo uma vez
    v._parar.set()  # a troca de pasta mandou parar
    r = v.verificar()  # arquivo estável: sem a parada, criaria a auditoria
    assert r.get("parado") is True
    assert estado.listar_auditorias() == []


def test_troca_espera_a_verificacao_em_curso_terminar(client, tmp_path, monkeypatch):
    """parar() espera a thread só 5 s; a troca espera o lock antes de limpar o estado."""
    monkeypatch.setattr(config, "VIGIA_INTERVALO_S", 60)
    antigo = Vigia(PastaLocal(tmp_path), intervalo_s=60, pasta_trabalho=tmp_path / "t1")
    monkeypatch.setattr(modulo_vigia, "vigia", antigo)
    ordem = []

    def verificacao_lenta():
        with antigo._lock:
            time.sleep(0.4)
            ordem.append("verificação terminou")

    t = threading.Thread(target=verificacao_lenta)
    t.start()
    time.sleep(0.05)
    limpar_original = estado.limpar
    monkeypatch.setattr(estado, "limpar", lambda: (ordem.append("estado limpo"), limpar_original()))
    novo_dir = tmp_path / "pasta_nova"
    novo_dir.mkdir()
    novo = modulo_vigia.trocar_fonte(PastaLocal(novo_dir))
    try:
        assert ordem == ["verificação terminou", "estado limpo"]
    finally:
        novo.parar()
        t.join()
        monkeypatch.setattr(modulo_vigia, "personalizada", False)
