"""Gatilho 1: o vigia percebe mudanças numa pasta (aqui, local, no lugar do Drive)."""

import time

import pytest

from heitor.api import config
from heitor.api import vigia as modulo_vigia
from heitor.api.estado import estado
from heitor.api.fontes import PastaDrive, PastaLocal
from heitor.api.vigia import Vigia

FICHAS = config.FICHA_EXEMPLO.read_text(encoding="utf-8")
PROTETOR_0302 = "0302,Rafael Souza Costa,servente,2026-11-07,protetor auditivo,1,17664,E,sim\n"


def ate(condicao, limite_s=5.0):
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        valor = condicao()
        if valor:
            return valor
        time.sleep(0.02)
    raise AssertionError("tempo esgotado")


def esperar_auditoria(auditoria_id):
    return ate(lambda: (a := estado.obter_auditoria(auditoria_id)).status != "processando" and a)


def pendencias_abertas(funcionario_id, regra):
    out = []
    for p in estado.listar_pendencias(funcionario_id=funcionario_id):
        a = estado.obter_achado(p.achado_id, p.auditoria_id)
        if a and a.regra == regra and p.status != "fechada":
            out.append(p)
    return out


@pytest.fixture
def pasta(tmp_path, client):  # client: estado limpo
    p = tmp_path / "drive"
    p.mkdir()
    return p


@pytest.fixture
def vigia(pasta, tmp_path):
    return Vigia(PastaLocal(pasta), intervalo_s=0.1, pasta_trabalho=tmp_path / "trabalho")


def disparar(vigia):
    """Duas verificações: a primeira vê, a segunda confirma que parou de mudar."""
    vigia.verificar()
    return vigia.verificar()


def test_so_age_quando_o_arquivo_para_de_mudar(vigia, pasta):
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    r = vigia.verificar()
    assert r["mudou"] is False and r["aguardando_confirmar"] == 1

    (pasta / "fichas.csv").write_text(FICHAS + PROTETOR_0302, encoding="utf-8")  # ainda editando
    assert vigia.verificar()["mudou"] is False

    r = vigia.verificar()  # igual à anterior: agora sim
    assert r["mudou"] is True
    assert r["funcionarios"] == ["0301", "0302", "0303", "0304"]

    aud = esperar_auditoria(r["auditoria_id"])
    assert aud.status == "concluida"
    assert aud.disparado_por == "alteracao_planilha"
    assert aud.descricao_disparo == "mudança na pasta: fichas.csv"
    eventos = estado.eventos_desde(aud.id)
    assert eventos[0].saida == "disparado por: mudança na pasta: fichas.csv"


def test_nada_mudou_nada_acontece(vigia, pasta):
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    esperar_auditoria(disparar(vigia)["auditoria_id"])
    antes = len(estado.listar_auditorias())
    assert vigia.verificar()["mudou"] is False
    assert len(estado.listar_auditorias()) == antes


def test_correcao_na_pasta_fecha_a_pendencia_sozinha(vigia, pasta):
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    esperar_auditoria(disparar(vigia)["auditoria_id"])
    [p] = pendencias_abertas("0302", "epi_inadequado")
    outras = {x.id: x.status for x in estado.listar_pendencias(funcionario_id="0302") if x.id != p.id}

    # O técnico registra hoje a entrega do protetor auditivo, na mesma planilha.
    (pasta / "fichas.csv").write_text(FICHAS + PROTETOR_0302, encoding="utf-8")
    r = disparar(vigia)
    assert r["funcionarios"] == ["0302"]  # só quem mudou é auditado de novo
    esperar_auditoria(r["auditoria_id"])

    final = ate(lambda: (x := estado.obter_pendencia(p.id)).status == "fechada" and x)
    assert "não aparece mais" in final.historico[-1].nota

    # As outras pendências do Rafael continuam como estavam, sem duplicar nem reabrir.
    depois = {x.id: x.status for x in estado.listar_pendencias(funcionario_id="0302") if x.id != p.id}
    assert depois == outras


def test_apagar_a_linha_antiga_nao_fecha_a_pendencia(vigia, pasta):
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    esperar_auditoria(disparar(vigia)["auditoria_id"])
    [p] = pendencias_abertas("0301", "assinatura_ausente")

    sem_a_linha = "".join(l for l in FICHAS.splitlines(keepends=True) if not ("0301" in l and "não" in l))
    (pasta / "fichas.csv").write_text(sem_a_linha, encoding="utf-8")
    r = disparar(vigia)
    esperar_auditoria(r["auditoria_id"])

    manter = ate(lambda: [e for e in estado.eventos_desde(r["auditoria_id"]) if e.ferramenta == "manter_pendencia"])
    assert estado.obter_pendencia(p.id).status == "aberta"
    assert "apagar linha antiga não corrige" in manter[0].saida["motivo"]


def test_arquivo_novo_na_pasta(vigia, pasta):
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    esperar_auditoria(disparar(vigia)["auditoria_id"])
    cabecalho = FICHAS.splitlines(keepends=True)[0]
    (pasta / "ficha_0305.csv").write_text(
        cabecalho + "0305,Ana Lima,pedreiro,2026-11-01,capacete,1,29637,E,sim\n", encoding="utf-8"
    )
    r = disparar(vigia)
    assert r["arquivos"] == ["ficha_0305.csv"] and r["funcionarios"] == ["0305"]


def test_arquivo_ilegivel_nao_derruba_e_nao_insiste(vigia, pasta):
    (pasta / "quebrado.csv").write_text("coluna_errada\nx\n", encoding="utf-8")
    disparar(vigia)
    s = vigia.status()
    assert s["arquivos_com_falha"] == 1 and "quebrado.csv" in s["ultimo_erro"]
    assert vigia.verificar()["mudou"] is False  # mesma versão: não tenta ler de novo


def test_rotas(client, vigia, pasta, monkeypatch):
    monkeypatch.setattr(modulo_vigia, "vigia", vigia)
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    client.post("/fontes/verificar")
    r = client.post("/fontes/verificar").json()
    assert r["mudou"] is True
    esperar_auditoria(r["auditoria_id"])

    s = client.get("/fontes").json()
    assert s["fonte"].startswith("pasta local") and s["arquivos_lidos"] == 1
    lista = client.get("/auditorias").json()
    assert lista[0]["id"] == r["auditoria_id"] and lista[0]["descricao_disparo"].startswith("mudança na pasta")
    assert client.get("/health").json()["vigia"]["fonte"].startswith("pasta local")
    assert estado.log_desde(0)  # o feed global (/eventos) recebe os eventos do vigia


def test_sem_fonte_configurada(client):
    assert client.get("/fontes").status_code == 404


def test_drive_entende_os_arquivos():
    sheet = PastaDrive._converter({"id": "1", "name": "Fichas", "mimeType": "application/vnd.google-apps.spreadsheet",
                                   "version": "7", "modifiedTime": "2026-11-07T15:00:00Z"})
    assert (sheet.nome, sheet.tipo, sheet.exportar) == ("Fichas.csv", "planilha", True)
    foto = PastaDrive._converter({"id": "2", "name": "IMG_0042", "mimeType": "image/jpeg", "md5Checksum": "abc"})
    assert (foto.nome, foto.tipo, foto.assinatura, foto.exportar) == ("IMG_0042.jpg", "foto", "abc", False)
    assert PastaDrive._converter({"id": "3", "name": "contrato.pdf", "mimeType": "application/pdf"}) is None


class _RespostaFalsa:
    def __init__(self, dados=None, conteudo=b""):
        self._dados, self.content = dados, conteudo

    def json(self):
        return self._dados


class _DriveFalso(PastaDrive):
    """O Drive como visto no teste real: a versão da planilha muda na hora, mas
    o CSV exportado só reflete a edição algumas consultas depois."""

    def __init__(self, versao, exportacoes):
        self.pasta_id, self.conta, self.descricao = "pasta", "robo@teste", "pasta do Drive (falsa)"
        self._planilhas = {}
        self.versao, self.exportacoes = versao, list(exportacoes)

    def _get(self, url, **params):
        if url.endswith("/export"):
            conteudo = self.exportacoes[0] if len(self.exportacoes) == 1 else self.exportacoes.pop(0)
            return _RespostaFalsa(conteudo=conteudo.encode())
        return _RespostaFalsa({"files": [{"id": "s1", "name": "fichas", "version": str(self.versao),
                                          "modifiedTime": "2026-11-07T19:35:23Z",
                                          "mimeType": "application/vnd.google-apps.spreadsheet"}]})


def test_planilha_do_google_com_exportacao_atrasada(client, tmp_path):
    drive = _DriveFalso(versao=10, exportacoes=[FICHAS])
    v = Vigia(drive, intervalo_s=0.1, pasta_trabalho=tmp_path / "trabalho")
    esperar_auditoria(disparar(v)["auditoria_id"])
    [p] = pendencias_abertas("0302", "epi_inadequado")

    # Edição: a versão sobe na hora, mas as 3 próximas exportações ainda vêm antigas.
    drive.versao = 11
    drive.exportacoes = [FICHAS, FICHAS, FICHAS, FICHAS + PROTETOR_0302]
    resultados = [v.verificar() for _ in range(5)]
    assert [r["mudou"] for r in resultados] == [False, False, False, False, True]
    assert resultados[-1]["funcionarios"] == ["0302"]
    esperar_auditoria(resultados[-1]["auditoria_id"])
    assert ate(lambda: estado.obter_pendencia(p.id).status == "fechada")
