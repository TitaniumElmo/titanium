"""Proteção do deploy público: rotas de administração com token, reset só em modo demo,
upload com limite de quantidade, tamanho e tipo."""

import pytest

from heitor.api import config

TOKEN = "segredo-de-teste"


@pytest.fixture
def com_token(monkeypatch):
    monkeypatch.setenv("HEITOR_TOKEN_ADMIN", TOKEN)


def test_reset_exige_token(client, com_token):
    assert client.post("/demo/reset").status_code == 401
    assert client.post("/demo/reset", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert client.post("/demo/reset", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 202
    assert client.post("/demo/reset", headers={"X-Heitor-Token": TOKEN}).status_code == 202


def test_reset_so_existe_em_modo_demo(client, com_token, monkeypatch):
    monkeypatch.setenv("HEITOR_DEMO", "")
    r = client.post("/demo/reset", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 404


def test_sem_token_configurado_fica_liberado(client):
    assert client.post("/demo/reset").status_code == 202  # máquina de quem desenvolve


def test_verificar_o_vigia_exige_token(client, com_token):
    assert client.post("/fontes/verificar").status_code == 401


def test_rotas_dos_jurados_seguem_abertas(client, com_token):
    """Subir planilha e ler resultados não pedem token: os jurados testam pelo link."""
    r = client.post("/auditorias", data={"exemplo": "true"})
    assert r.status_code == 202
    assert client.get(f"/auditorias/{r.json()['id']}").status_code == 200
    assert client.get("/pendencias").status_code == 200


def test_upload_grande_e_recusado_sem_deixar_arquivo(client, monkeypatch):
    monkeypatch.setenv("HEITOR_MAX_UPLOAD_MB", "1")
    grande = b"funcionario_id,nome\n" + b"x" * (2 * 1024 * 1024)
    r = client.post("/auditorias", files=[("arquivos", ("grande.csv", grande, "text/csv"))])
    assert r.status_code == 413
    assert not list(config.PASTA_UPLOADS.rglob("grande*.csv"))


def test_tipo_de_arquivo_recusado(client):
    r = client.post("/auditorias", files=[("arquivos", ("script.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 415
    r = client.post("/auditorias", files=[("arquivos", ("nota.pdf", b"%PDF", "application/pdf"))])
    assert r.status_code == 415  # PDF só na resposta a pendência (nota fiscal do RH)


def test_muitos_arquivos_recusado(client, monkeypatch):
    monkeypatch.setenv("HEITOR_MAX_ARQUIVOS", "2")
    arquivos = [("arquivos", (f"f{i}.csv", b"a,b\n", "text/csv")) for i in range(3)]
    assert client.post("/auditorias", files=arquivos).status_code == 413


def test_resposta_do_rh_aceita_pdf(client):
    r = client.post("/auditorias", data={"exemplo": "true"})
    from tests.test_api import esperar

    esperar(client, r.json()["id"])
    rh = client.get("/pendencias", params={"auditoria_id": r.json()["id"], "destino": "rh"}).json()[0]
    r = client.post(f"/pendencias/{rh['id']}/resposta", files={"arquivo": ("nota_fiscal.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code != 415
