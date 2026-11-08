"""Pasta do vigia trocável pela API (POST /fontes): uma pasta por vez, só o time (token).

O Drive é simulado com uma pasta local: os testes nunca falam com o Google."""

import time

import pytest

from heitor.api import config
from heitor.api import vigia as modulo_vigia
from heitor.api.estado import estado
from heitor.api.fontes import PastaDrive, PastaLocal, id_da_pasta

TOKEN = "segredo-de-teste"
ADMIN = {"Authorization": f"Bearer {TOKEN}"}
FICHAS = config.FICHA_EXEMPLO.read_text(encoding="utf-8")
PASTA_ID = "1AbCdEfGhIjKlMnOpQrS"


def ate(condicao, limite_s=8.0):
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        if valor := condicao():
            return valor
        time.sleep(0.05)
    raise AssertionError("tempo esgotado")


@pytest.fixture
def ambiente(client, monkeypatch, tmp_path):
    """Token configurado, vigia rápido, sem pasta no .env; desliga o vigia no fim."""
    monkeypatch.setenv("HEITOR_TOKEN_ADMIN", TOKEN)
    monkeypatch.setattr(config, "VIGIA_INTERVALO_S", 0.05)
    monkeypatch.setattr(config, "DRIVE_PASTA", None)
    monkeypatch.setattr(config, "FONTE_PASTA", None)
    antes = modulo_vigia.vigia
    yield tmp_path
    if modulo_vigia.vigia is not antes and modulo_vigia.vigia:
        modulo_vigia.vigia.parar()
    modulo_vigia.vigia, modulo_vigia.personalizada = antes, False


@pytest.fixture
def drive_falso(ambiente, monkeypatch):
    """abrir_drive devolve uma pasta local com as fichas de exemplo, no lugar do Drive."""
    pasta = ambiente / "drive_do_cliente"
    pasta.mkdir()
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    pedidos = []

    def abrir(pasta_id):
        pedidos.append(pasta_id)
        return PastaLocal(pasta)

    monkeypatch.setattr(modulo_vigia, "abrir_drive", abrir)
    return pedidos


def test_link_da_pasta_em_todos_os_formatos():
    for link in (f"https://drive.google.com/drive/folders/{PASTA_ID}?usp=sharing",
                 f"https://drive.google.com/drive/u/0/folders/{PASTA_ID}",
                 f"https://drive.google.com/open?id={PASTA_ID}", f"  {PASTA_ID} "):
        assert id_da_pasta(link) == PASTA_ID
    for errado in (f"https://docs.google.com/spreadsheets/d/{PASTA_ID}/edit", "oi", ""):
        with pytest.raises(ValueError):
            id_da_pasta(errado)


def test_trocar_a_pasta_exige_token(client, ambiente):
    assert client.post("/fontes", json={"url": PASTA_ID}).status_code == 401
    assert client.post("/fontes/padrao").status_code == 401


def test_link_de_planilha_e_recusado_e_nada_muda(client, ambiente, drive_falso):
    client.post("/auditorias", data={"exemplo": "true"})
    r = client.post("/fontes", json={"url": f"https://docs.google.com/spreadsheets/d/{PASTA_ID}/edit"}, headers=ADMIN)
    assert r.status_code == 400 and "link da pasta" in r.json()["detail"]
    assert drive_falso == [] and modulo_vigia.vigia is None
    assert estado.listar_auditorias()  # o estado não foi apagado


def test_pasta_nao_compartilhada_mantem_a_atual(client, ambiente, monkeypatch):
    def recusa(pasta_id):
        raise ValueError("o Drive não achou a pasta: compartilhe-a com elmo@conta.iam.gserviceaccount.com")

    monkeypatch.setattr(modulo_vigia, "abrir_drive", recusa)
    client.post("/auditorias", data={"exemplo": "true"})
    r = client.post("/fontes", json={"url": PASTA_ID}, headers=ADMIN)
    assert r.status_code == 400 and "compartilhe" in r.json()["detail"]
    assert modulo_vigia.vigia is None and estado.listar_auditorias()


def test_troca_apaga_o_estado_e_audita_a_pasta_nova(client, ambiente, drive_falso):
    client.post("/auditorias", data={"exemplo": "true"})
    antiga = {a.id for a in estado.listar_auditorias()}

    r = client.post("/fontes", json={"url": f"https://drive.google.com/drive/folders/{PASTA_ID}"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert drive_falso == [PASTA_ID]
    assert r.json()["personalizada"] is True and r.json()["rodando"] is True
    assert not antiga & {a.id for a in estado.listar_auditorias()}  # a pasta antiga saiu da tela

    nova = ate(lambda: [a for a in estado.listar_auditorias() if a.disparado_por == "alteracao_planilha"])
    assert nova and "fichas.csv" in (nova[0].descricao_disparo or "")
    assert client.get("/fontes").json()["personalizada"] is True


def test_voltar_a_pasta_do_env(client, ambiente, drive_falso, monkeypatch):
    assert client.post("/fontes/padrao", headers=ADMIN).status_code == 404  # sem pasta no .env

    padrao = ambiente / "pasta_da_demo"
    padrao.mkdir()
    monkeypatch.setattr(config, "FONTE_PASTA", str(padrao))
    assert client.post("/fontes", json={"url": PASTA_ID}, headers=ADMIN).status_code == 200

    r = client.post("/fontes/padrao", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["personalizada"] is False and str(padrao) in r.json()["fonte"]


class _Resposta:
    def __init__(self, dados):
        self._dados = dados

    def json(self):
        return self._dados


def _drive_sem_rede(get):
    d = object.__new__(PastaDrive)
    d.pasta_id, d.conta, d.descricao, d._get = PASTA_ID, "elmo@conta.iam.gserviceaccount.com", "", get
    return d


def test_conferir_acesso_le_a_propria_pasta():
    """Listar pasta não compartilhada volta vazia, sem erro; por isso a troca lê a pasta antes."""
    pasta = _drive_sem_rede(lambda url, **p: _Resposta({"name": "EPI Mandacaru", "mimeType": "application/vnd.google-apps.folder"}))
    assert pasta.conferir_acesso() == "EPI Mandacaru"
    assert "EPI Mandacaru" in pasta.descricao and pasta.link.endswith(PASTA_ID)

    arquivo = _drive_sem_rede(lambda url, **p: _Resposta({"name": "fichas", "mimeType": "application/vnd.google-apps.spreadsheet"}))
    with pytest.raises(ValueError, match="não é uma pasta"):
        arquivo.conferir_acesso()


def test_abrir_drive_explica_quando_nao_foi_compartilhada(monkeypatch, tmp_path):
    chave = tmp_path / "chave.json"
    chave.write_text("{}")
    monkeypatch.setattr(config, "DRIVE_CREDENCIAIS", str(chave))

    class SemAcesso:
        def __init__(self, pasta_id, credenciais):
            self.conta = "elmo@conta.iam.gserviceaccount.com"

        def conferir_acesso(self):
            raise FileNotFoundError("404")

    monkeypatch.setattr(modulo_vigia, "PastaDrive", SemAcesso)
    with pytest.raises(ValueError, match="compartilhe-a com elmo@conta"):
        modulo_vigia.abrir_drive(PASTA_ID)

    monkeypatch.setattr(config, "DRIVE_CREDENCIAIS", str(tmp_path / "nao_existe.json"))
    with pytest.raises(ValueError, match="chave da conta de serviço"):
        modulo_vigia.abrir_drive(PASTA_ID)
