"""Foto da ficha de papel: ligada a um funcionário da planilha e enviada ao agente para conferir as assinaturas.

A foto nunca é lida como ficha (decisão do time: os dados vêm da planilha).
"""

import pytest

from heitor.api import config, integracao, stubs
from heitor.api.estado import estado
from heitor.api.fontes import PastaLocal
from heitor.api.fotos import dono_da_foto
from heitor.api.vigia import Vigia
from tests.test_api import esperar
from tests.test_vigia import FICHAS, disparar, esperar_auditoria

JPG = b"\xff\xd8\xff\xe0 foto falsa"


@pytest.fixture
def chamadas(monkeypatch):
    """Registra as fotos que chegam ao agente (conferir_e_auditar) e segue com o stub."""
    registro = []

    def conferir_e_auditar(auditoria_id, linhas, fotos, emitir_evento):
        registro.append({"auditoria_id": auditoria_id, "fotos": dict(fotos),
                         "funcionarios": sorted({l.funcionario_id for l in linhas})})
        return stubs.conferir_e_auditar(auditoria_id, linhas, fotos, emitir_evento)

    monkeypatch.setattr(integracao, "conferir_e_auditar", conferir_e_auditar)
    return registro


def test_dono_da_foto():
    funcionarios = {"302", "0303", "0310"}  # o Sheets tira o zero da frente: 0302 vira 302
    assert dono_da_foto("0302.jpg", funcionarios) == "302"
    assert dono_da_foto("ficha_0303.jpeg", funcionarios) == "0303"
    assert dono_da_foto("fabio-0310.jpg", funcionarios) == "0310"
    assert dono_da_foto("IMG_4421.jpg", funcionarios, informado="0302") == "302"  # o informado vence o nome
    assert dono_da_foto("IMG_4421.jpg", funcionarios) is None  # 4421 não está na planilha
    assert dono_da_foto("0302_e_0303.jpg", funcionarios) is None  # ambíguo: não chuta
    assert dono_da_foto("0302.jpg", funcionarios, informado="9999") is None  # informado errado: não chuta


def test_upload_com_fotos(client, chamadas):
    with open(config.FICHA_EXEMPLO, "rb") as planilha:
        r = client.post(
            "/auditorias",
            files=[
                ("arquivos", ("fichas.csv", planilha, "text/csv")),
                ("fotos", ("IMG_0001.jpg", JPG, "image/jpeg")),  # dono informado
                ("fotos", ("ficha_0303.jpg", JPG, "image/jpeg")),  # dono pelo nome
                ("fotos", ("sem_dono.jpg", JPG, "image/jpeg")),
            ],
            data={"funcionarios_das_fotos": ["0302", "", ""]},
        )
    assert r.status_code == 202, r.text
    aud = esperar(client, r.json()["id"])
    assert aud["status"] == "concluida"
    assert set(aud["arquivos"]) == {"fichas.csv", "IMG_0001.jpg", "ficha_0303.jpg", "sem_dono.jpg"}

    [c] = chamadas
    assert {f: p.rsplit("/", 1)[-1] for f, p in c["fotos"].items()} == {"0302": "IMG_0001.jpg", "0303": "ficha_0303.jpg"}
    assert c["funcionarios"] == ["0301", "0302", "0303", "0304"]  # os dados vêm todos da planilha
    avisos = [e for e in estado.eventos_desde(aud["id"]) if e.ferramenta == "ligar_foto"]
    assert len(avisos) == 1 and avisos[0].entrada["foto"] == "sem_dono.jpg" and avisos[0].tipo == "erro"


def test_upload_sem_foto_nao_chama_a_conferencia(client, chamadas):
    r = client.post("/auditorias", data={"exemplo": "true"})
    assert esperar(client, r.json()["id"])["status"] == "concluida"
    assert chamadas == []


def test_foto_em_arquivos_nao_vira_ficha(client, chamadas):
    with open(config.FICHA_EXEMPLO, "rb") as planilha:
        r = client.post("/auditorias", files=[("arquivos", ("fichas.csv", planilha, "text/csv")),
                                               ("arquivos", ("0304.jpg", JPG, "image/jpeg"))])
    esperar(client, r.json()["id"])
    assert {f: p.rsplit("/", 1)[-1] for f, p in chamadas[0]["fotos"].items()} == {"0304": "0304.jpg"}


def test_vigia_manda_a_foto_da_pasta_para_o_agente(client, chamadas, tmp_path):
    pasta = tmp_path / "drive"
    pasta.mkdir()
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    (pasta / "0302.jpg").write_bytes(JPG)
    v = Vigia(PastaLocal(pasta), 0.1, tmp_path / "trabalho")

    esperar_auditoria(disparar(v)["auditoria_id"])
    assert list(chamadas[-1]["fotos"]) == ["0302"]

    # Chega a foto da ficha do 0303: só ele é auditado de novo, agora com a foto.
    (pasta / "ficha_0303.jpg").write_bytes(JPG + b"outra")
    r = disparar(v)
    assert r["funcionarios"] == ["0303"]
    esperar_auditoria(r["auditoria_id"])
    assert list(chamadas[-1]["fotos"]) == ["0303"] and chamadas[-1]["funcionarios"] == ["0303"]

    # Foto sem matrícula no nome: fica de fora e aparece no status.
    (pasta / "WhatsApp Image.jpg").write_bytes(JPG + b"x")
    assert disparar(v)["mudou"] is False
    assert v.status()["fotos_sem_dono"] == ["WhatsApp Image.jpg"]
