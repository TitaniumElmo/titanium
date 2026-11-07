import json
import time

from heitor.api import config

CORRECAO_0302 = config.PASTA_EXEMPLOS / "correcao_0302.csv"


def esperar(client, auditoria_id, limite_s=5.0):
    fim = time.monotonic() + limite_s
    while time.monotonic() < fim:
        r = client.get(f"/auditorias/{auditoria_id}").json()
        if r["status"] != "processando":
            return r
        time.sleep(0.05)
    raise AssertionError("auditoria não terminou a tempo")


def auditar_exemplo(client):
    r = client.post("/auditorias", data={"exemplo": "true"})
    assert r.status_code == 202, r.text
    return esperar(client, r.json()["id"])


def pendencia(client, auditoria_id, regra, funcionario_id):
    for p in client.get("/pendencias", params={"auditoria_id": auditoria_id}).json():
        d = client.get(f"/pendencias/{p['id']}").json()
        if d["achado"]["regra"] == regra and d["funcionario_id"] == funcionario_id:
            return d
    raise AssertionError(f"sem pendência {regra} para {funcionario_id}")


def responder(client, pendencia_id, caminho, nome=None):
    with open(caminho, "rb") as f:
        return client.post(
            f"/pendencias/{pendencia_id}/resposta",
            files={"arquivo": (nome or caminho.name, f)},
        )


# ---------------------------------------------------------------------------


def test_health_mostra_stubs(client):
    r = client.get("/health").json()
    assert r["status"] == "ok"
    assert r["integracao"]["rodar_auditoria"] == "stub"


def test_auditoria_do_exemplo(client):
    resumo = auditar_exemplo(client)
    assert resumo["status"] == "concluida"

    regras = {(a["regra"], a["funcionario_id"]) for a in client.get(f"/auditorias/{resumo['id']}/achados").json()}
    assert regras == {
        ("assinatura_ausente", "0301"),
        ("ca_vencido", "0302"),
        ("ca_ausente", "0302"),
        ("epi_inadequado", "0302"),
        ("ca_vencido", "0304"),
    }
    assert resumo["contagem_tipo"] == {"passivo": 1, "prova": 3, "corrigivel": 1}
    assert resumo["exposicao_total_rs"] > 0
    assert resumo["pendencias_abertas"] == 5
    assert resumo["passos"] > 0 and resumo["custo_total_usd"] > 0

    # Pedido de documento ao RH é pendência com destino "rh".
    rh = client.get("/pendencias", params={"auditoria_id": resumo["id"], "destino": "rh"}).json()
    assert len(rh) == 3


def test_ciclo_correcao_fecha_pendencia(client):
    aud = auditar_exemplo(client)
    p = pendencia(client, aud["id"], "epi_inadequado", "0302")
    assert p["status"] == "aberta" and p["destino"] == "tecnico"

    r = responder(client, p["id"], CORRECAO_0302)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "fechada"
    assert [h["status"] for h in r.json()["historico"]] == ["aberta", "aguardando", "fechada"]

    # Pendência fechada não aceita nova resposta.
    assert responder(client, p["id"], CORRECAO_0302).status_code == 409


def test_resposta_que_nao_confere_reabre_e_depois_fecha(client):
    aud = auditar_exemplo(client)
    p = pendencia(client, aud["id"], "epi_inadequado", "0302")

    r = responder(client, p["id"], config.FICHA_EXEMPLO)  # ficha sem o protetor auditivo
    assert r.json()["status"] == "reaberta"

    r = responder(client, p["id"], CORRECAO_0302)
    assert r.json()["status"] == "fechada"
    assert [h["status"] for h in r.json()["historico"]] == [
        "aberta", "aguardando", "reaberta", "aguardando", "fechada",
    ]


def test_passivo_nao_se_corrige_editando_ficha_antiga(client):
    aud = auditar_exemplo(client)
    p = pendencia(client, aud["id"], "assinatura_ausente", "0301")
    r = responder(client, p["id"], config.FICHA_EXEMPLO)
    assert r.json()["status"] == "reaberta"


def test_rh_envia_nota_fiscal(client, tmp_path):
    aud = auditar_exemplo(client)
    p = pendencia(client, aud["id"], "ca_vencido", "0302")
    assert p["destino"] == "rh"
    nf = tmp_path / "nota_fiscal.pdf"
    nf.write_bytes(b"%PDF-1.4 falso")
    assert responder(client, p["id"], nf).json()["status"] == "fechada"


def test_upload_de_csv_proprio(client):
    with open(CORRECAO_0302, "rb") as f:
        r = client.post("/auditorias", files=[("arquivos", ("minha_ficha.csv", f, "text/csv"))])
    assert r.status_code == 202
    assert r.json()["arquivos"] == ["minha_ficha.csv"]
    resumo = esperar(client, r.json()["id"])
    regras = {a["regra"] for a in client.get(f"/auditorias/{resumo['id']}/achados").json()}
    assert "epi_inadequado" not in regras  # a correção tem protetor auditivo


def test_sem_arquivo_da_400(client):
    assert client.post("/auditorias").status_code == 400


def test_sse_transmite_eventos_e_status(client):
    r = client.post("/auditorias", data={"exemplo": "true"})
    aud_id = r.json()["id"]
    eventos, status = [], []
    with client.stream("GET", f"/auditorias/{aud_id}/eventos", params={"ate_concluir": "true"}) as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
        tipo = None
        for linha in resp.iter_lines():
            if linha.startswith("event: "):
                tipo = linha[7:]
            elif linha.startswith("data: "):
                (eventos if tipo == "evento" else status).append(json.loads(linha[6:]))
    assert status[-1] == {"status": "concluida"}
    assert {e["ferramenta"] for e in eventos} >= {"consulta_ca", "audita_linha", "criar_pendencia"}
    assert len(eventos) == client.get(f"/auditorias/{aud_id}").json()["passos"]  # nada se perdeu


def test_relatorio(client):
    aud = auditar_exemplo(client)
    r = client.get(f"/auditorias/{aud['id']}/relatorio").json()
    assert "exposição potencial máxima" in r["relatorio"].lower()


def test_consulta_ca(client):
    assert client.get("/ca/28499", params={"data": "2024-02-05"}).json()["valido"] is False
    assert client.get("/ca/21245", params={"data": "2024-05-15"}).json()["valido"] is False
    assert client.get("/ca/21245", params={"data": "2024-07-01"}).json()["valido"] is True
    assert client.get("/ca/99999999").json()["encontrado"] is False


def test_demo_reset(client):
    auditar_exemplo(client)
    r = client.post("/demo/reset")
    assert r.status_code == 202
    esperar(client, r.json()["id"])
    assert {p["auditoria_id"] for p in client.get("/pendencias").json()} == {r.json()["id"]}


def test_404(client):
    assert client.get("/auditorias/au-999").status_code == 404
    assert client.get("/pendencias/p-999").status_code == 404
