"""O que o front precisa da API: pendência rica, disparo da auditoria, resumo nos eventos,
cobrança de prazos vencidos (gatilho 2) e aviso de edição detectada."""

from datetime import date, datetime, timedelta

import pytest

from heitor.api import cobranca, config
from heitor.api import vigia as modulo_vigia
from heitor.api.estado import estado
from heitor.api.fontes import PastaLocal
from heitor.api.ferramentas import criar_pendencia
from heitor.api.resumos import FORMATADORES, com_resumo, resumo_da_ferramenta
from heitor.api.vigia import AUDITORIA_GLOBAL, Vigia
from heitor.contrato import Evento, Linha
from tests.test_api import CORRECAO_0302, auditar_exemplo, esperar, pendencia, responder
from tests.test_integracao import precisa_base, real  # noqa: F401
from tests.test_vigia import FICHAS, ate, disparar, esperar_auditoria

HOJE = date(2026, 11, 10)


def achado(aud, id_="a-1", funcionario="0302", regra="epi_inadequado", tipo="corrigivel"):
    return {"id": id_, "auditoria_id": aud, "funcionario_id": funcionario, "linha": None, "regra": regra,
            "gravidade": "irregular", "tipo": tipo, "evidencia": "x", "acao_sugerida": "entregar protetor"}


@pytest.fixture
def aud(client):
    aud_id = estado.novo_id("au")
    estado.criar_auditoria(aud_id, [], disparado_por="manual")
    estado.salvar_linhas(aud_id, [Linha(funcionario_id="0302", nome="Rafael Souza Costa", funcao="servente",
                                        linha=1, epi="luva", origem="t")])
    return aud_id


def pendencia_manual(aud, prazo="2026-11-01", destino="tecnico", id_="a-1"):
    return estado.obter_pendencia(criar_pendencia(achado(aud, id_), destino, "entregar protetor", prazo)["id"])


# -- 1. Pendencia ------------------------------------------------------------------------


def test_pendencia_traz_nome_disparo_e_historico_do_agente(client):
    aud = auditar_exemplo(client)
    p = pendencia(client, aud["id"], "epi_inadequado", "0302")
    assert p["funcionario_nome"] == "Rafael Souza Costa"
    assert p["disparado_por"] == "upload"
    assert (p["cobrancas"], p["escalada"], p["prioridade"]) == (0, False, "normal")
    assert (p["historico"][0]["etapa"], p["historico"][0]["ator"]) == ("pedir_correcao", "agente")


def test_resposta_do_tecnico_vira_corrigir_e_a_reauditoria_vira_conferir(client):
    aud = auditar_exemplo(client)
    p = pendencia(client, aud["id"], "epi_inadequado", "0302")
    assert p["destino"] == "tecnico"
    depois = responder(client, p["id"], CORRECAO_0302).json()
    assert depois["status"] == "fechada"
    etapas = [(h["status"], h["etapa"], h["ator"]) for h in depois["historico"][1:]]
    assert etapas == [("aguardando", "corrigir", "tecnico"), ("fechada", "conferir", "agente")]


def test_pendencia_antiga_sem_os_campos_novos_continua_valida():
    from heitor.contrato import Pendencia

    p = Pendencia(id="p-1", achado_id="a-1", destino="rh", acao="x", prazo="2026-11-10")
    assert (p.funcionario_nome, p.disparado_por, p.cobrancas, p.escalada, p.prioridade) == (None, None, 0, False, "normal")


# -- 2. Auditoria --------------------------------------------------------------------------


def test_auditoria_por_upload_e_por_demo_reset(client):
    aud = auditar_exemplo(client)
    assert (aud["disparado_por"], aud["descricao_disparo"]) == ("upload", None)
    assert (aud["n_fichas"], aud["n_linhas"]) == (4, 12)
    reset = client.post("/demo/reset").json()
    assert reset["disparado_por"] == "manual"
    assert esperar(client, reset["id"])["n_fichas"] == 4


def test_auditoria_do_vigia_guarda_codigo_e_descricao(client, tmp_path):
    pasta = tmp_path / "drive"
    pasta.mkdir()
    (pasta / "fichas.csv").write_text(FICHAS, encoding="utf-8")
    v = Vigia(PastaLocal(pasta), intervalo_s=0.1, pasta_trabalho=tmp_path / "trabalho")
    aud = esperar_auditoria(disparar(v)["auditoria_id"])
    assert aud.disparado_por == "alteracao_planilha"
    assert aud.descricao_disparo == "mudança na pasta: fichas.csv"
    assert (aud.n_fichas, aud.n_linhas) == (4, 12)


# -- 3. saida.resumo -----------------------------------------------------------------------


def evento(ferramenta, entrada=None, saida=None, tipo="ferramenta"):
    return Evento(auditoria_id="au-t", passo=1, tipo=tipo, ferramenta=ferramenta, entrada=entrada or {},
                  saida=saida, ts=datetime(2026, 11, 7, 10, 0))


def test_resumo_de_criar_pendencia_diz_destino_e_prazo():
    e = com_resumo(evento("criar_pendencia", saida={"id": "p-3", "destino": "tecnico", "prazo": "2026-11-08"}))
    assert e.saida["resumo"] == "pendência p-3 para o técnico, prazo 1 dia"
    assert e.saida["destino"] == "tecnico" and e.saida["id"] == "p-3"
    rh = com_resumo(evento("criar_pendencia", saida={"id": "p-4", "destino": "rh", "prazo": "2026-11-12"}))
    assert rh.saida["resumo"] == "pendência p-4 para o RH, prazo 5 dias"


def test_resumo_nao_dict_e_envolvido_sem_perder_o_conteudo():
    e = com_resumo(evento("audita_linha", saida=["a", "b"]))
    assert e.saida["conteudo"] == ["a", "b"] and e.saida["resumo"]
    assert com_resumo(evento("consulta_ca", saida=None)).saida["conteudo"] is None


def test_resumo_so_em_evento_de_ferramenta_e_nao_sobrescreve():
    assert com_resumo(evento(None, saida={"pensamento": "x"}, tipo="decisao")).saida == {"pensamento": "x"}
    assert com_resumo(evento("x", saida="falhou", tipo="erro")).saida == "falhou"
    assert com_resumo(evento("consulta_ca", saida={"resumo": "meu"})).saida == {"resumo": "meu"}


def test_resumo_e_deterministico_e_cobre_ferramentas_sem_formatador():
    e = evento("consulta_ca", {"numero": "25"}, {"numero": "25", "encontrado": True, "valido_na_data": False,
                                                  "situacao": "VENCIDO", "validade": "2010-09-08"})
    assert com_resumo(e).saida["resumo"] == com_resumo(e).saida["resumo"] == "CA 25 vencido na data (validade 08/09/2010)"
    assert resumo_da_ferramenta("ferramenta_nova", {}, {}, e.ts) == "ferramenta_nova executada"
    assert resumo_da_ferramenta("consulta_ca", {}, {"saida": "estranha"}, e.ts)


def test_todo_formatador_aguenta_saida_vazia():
    ts = datetime(2026, 11, 7)
    for nome in FORMATADORES:
        assert isinstance(resumo_da_ferramenta(nome, {}, {}, ts), str)


def test_eventos_da_auditoria_chegam_com_resumo_e_criar_pendencia_traz_o_destino(client):
    aud = auditar_exemplo(client)
    eventos = [e for e in estado.eventos_desde(aud["id"]) if e.tipo == "ferramenta"]
    assert eventos and all(isinstance(e.saida, dict) and e.saida.get("resumo") for e in eventos)
    criacoes = [e for e in eventos if e.ferramenta == "criar_pendencia"]
    assert criacoes and all(e.saida["destino"] in ("tecnico", "rh") for e in criacoes)
    assert all(e.saida["resumo"].startswith("pendência ") for e in criacoes)


# -- 4. Gatilho 2: prazo vencido -------------------------------------------------------------


@pytest.fixture
def avisos(monkeypatch):
    enviados = []
    monkeypatch.setattr(cobranca, "notificar", lambda p, **kw: enviados.append((p.id, kw)))
    return enviados


def test_cobra_pendencia_vencida_registra_historico_evento_e_avisa(aud, avisos):
    p = pendencia_manual(aud)
    feitas = cobranca.cobrar_atrasadas(HOJE)
    assert feitas == [{"pendencia_id": p.id, "cobrancas": 1, "escalada": False}]
    nova = estado.obter_pendencia(p.id)
    assert (nova.cobrancas, nova.escalada, nova.prioridade, nova.status) == (1, False, "normal", "aberta")
    assert (nova.historico[-1].etapa, nova.historico[-1].ator) == ("cobrar_atraso", "agente")
    ev = [e for e in estado.eventos_desde(aud) if e.ferramenta == "cobrar_atraso"]
    assert len(ev) == 1 and ev[0].tipo == "ferramenta"
    assert ev[0].entrada == {"pendencia_id": p.id, "cobrancas": 1, "escalada": False}
    assert ev[0].saida["cobrancas"] == 1 and "cobrança 1" in ev[0].saida["resumo"]
    assert avisos == [(p.id, {"acao_da_regra": "entregar protetor", "cobranca": 1, "coordenador": False})]


def test_nao_cobra_duas_vezes_no_mesmo_dia_e_escala_na_segunda(aud, avisos):
    p = pendencia_manual(aud)
    assert len(cobranca.cobrar_atrasadas(HOJE)) == 1
    assert cobranca.cobrar_atrasadas(HOJE) == []
    assert estado.obter_pendencia(p.id).cobrancas == 1

    feitas = cobranca.cobrar_atrasadas(HOJE + timedelta(days=1))
    assert feitas == [{"pendencia_id": p.id, "cobrancas": 2, "escalada": True}]
    nova = estado.obter_pendencia(p.id)
    assert (nova.escalada, nova.prioridade) == (True, "alta")
    assert avisos[-1][1]["coordenador"] is True and avisos[0][1]["coordenador"] is False


def test_so_cobra_aberta_ou_reaberta_com_prazo_passado(aud, avisos):
    pendencia_manual(aud, prazo="2026-11-20", id_="a-futura")
    fechada = pendencia_manual(aud, id_="a-fechada")
    estado.atualizar_pendencia(fechada.id, lambda p: setattr(p, "status", "fechada"))
    aguardando = pendencia_manual(aud, id_="a-aguardando")
    estado.atualizar_pendencia(aguardando.id, lambda p: setattr(p, "status", "aguardando"))
    reaberta = pendencia_manual(aud, id_="a-reaberta")
    estado.atualizar_pendencia(reaberta.id, lambda p: setattr(p, "status", "reaberta"))
    assert [f["pendencia_id"] for f in cobranca.cobrar_atrasadas(HOJE)] == [reaberta.id]


def test_prazo_teste_adianta_o_relogio(aud, avisos, monkeypatch):
    prazo = (date.today() + timedelta(days=3)).isoformat()
    p = pendencia_manual(aud, prazo=prazo)
    monkeypatch.delenv("HEITOR_PRAZO_TESTE", raising=False)
    assert cobranca.cobrar_atrasadas() == []
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "5")
    assert [f["pendencia_id"] for f in cobranca.cobrar_atrasadas()] == [p.id]
    monkeypatch.setenv("HEITOR_PRAZO_TESTE", "6")
    assert cobranca.cobrar_atrasadas()[0]["escalada"] is True


def test_notificacao_de_cobranca_vai_tambem_ao_coordenador(aud, monkeypatch):
    from heitor.api import notificacao

    p = pendencia_manual(aud)
    registros = []
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setattr(notificacao.log, "info", lambda msg, *a: registros.append((a[0], a[1])))
    notificacao.notificar(p, cobranca=2, coordenador=True)
    assert [quem for quem, _ in registros] == ["tecnico", "coordenador"]
    assert all("Cobrança 2" in texto for _, texto in registros)


def test_vigia_cobra_a_cada_ciclo(aud, tmp_path, avisos):
    p = pendencia_manual(aud)
    pasta = tmp_path / "drive"
    pasta.mkdir()
    v = Vigia(PastaLocal(pasta), intervalo_s=0.05, pasta_trabalho=tmp_path / "trabalho")
    v.iniciar()
    try:
        ate(lambda: estado.obter_pendencia(p.id).cobrancas >= 1)
    finally:
        v.parar()
    assert estado.obter_pendencia(p.id).cobrancas == 1


# -- 5. edicao_detectada -------------------------------------------------------------------------


def test_vigia_avisa_edicao_detectada_antes_de_auditar(client, tmp_path):
    pasta = tmp_path / "drive"
    pasta.mkdir()
    arquivo = pasta / "fichas.csv"
    arquivo.write_text(FICHAS, encoding="utf-8")
    v = Vigia(PastaLocal(pasta), intervalo_s=0.1, pasta_trabalho=tmp_path / "trabalho")
    esperar_auditoria(disparar(v)["auditoria_id"])
    assert not [e for e in estado.log_desde() if e.ferramenta == "edicao_detectada"]  # primeira leitura não é edição

    arquivo.write_text(FICHAS + "0302,Rafael Souza Costa,servente,2026-11-07,protetor auditivo,1,17664,E,sim\n",
                       encoding="utf-8")
    antes = len(estado.log_desde())
    assert v.verificar()["mudou"] is False  # em espera, ainda não audita
    novos = [e for e in estado.log_desde(antes) if e.ferramenta == "edicao_detectada"]
    assert len(novos) == 1
    e = novos[0]
    assert e.auditoria_id == AUDITORIA_GLOBAL and e.tipo == "ferramenta"
    assert e.saida["fonte"] == v.fonte.descricao and e.saida["aguardando_segundos"] == 0.1
    assert e.saida["arquivo"] == "fichas.csv" and "edição detectada" in e.saida["resumo"]

    r = v.verificar()  # confirmou: agora sim audita, e o evento de início da auditoria vem depois
    assert r["mudou"] is True
    esperar_auditoria(r["auditoria_id"])
    ferramentas = [e.ferramenta for e in estado.log_desde(antes)]
    assert ferramentas.index("edicao_detectada") == 0


def test_evento_global_aparece_no_feed_de_eventos(client):
    from heitor.api.execucao import emitir_evento

    emitir_evento(AUDITORIA_GLOBAL, {"passo": 0, "tipo": "ferramenta", "ferramenta": "edicao_detectada",
                                     "entrada": {}, "saida": {"fonte": "x", "aguardando_segundos": 10}})
    assert [e.auditoria_id for e in estado.log_desde()] == [AUDITORIA_GLOBAL]
    assert estado.eventos_desde("au-qualquer") == []


# -- 6. Fluxo do RH ----------------------------------------------------------------------------------


def test_rh_responde_com_upload_e_a_pendencia_fecha(client, tmp_path):
    aud = auditar_exemplo(client)
    p = pendencia(client, aud["id"], "ca_vencido", "0302")
    assert p["destino"] == "rh" and p["prioridade"] == "normal"
    nf = tmp_path / "nota_fiscal.pdf"
    nf.write_bytes(b"%PDF-1.4 falso")
    depois = responder(client, p["id"], nf).json()
    assert depois["status"] == "fechada"
    etapas = [(h["etapa"], h["ator"]) for h in depois["historico"][1:]]
    assert etapas == [("comprovar", "rh"), ("conferir", "agente")]
    assert client.options("/pendencias", headers={"Origin": "http://localhost:5173",
                                                  "Access-Control-Request-Method": "GET"}).headers[
        "access-control-allow-origin"] == "*"


@precisa_base
def test_agente_real_emite_criar_pendencia_com_destino_e_resumo(client, real):
    r = client.post("/auditorias", data={"exemplo": "true"})
    aud = esperar(client, r.json()["id"], limite_s=30)
    criacoes = [e for e in estado.eventos_desde(aud["id"]) if e.ferramenta == "criar_pendencia"]
    assert criacoes
    for e in criacoes:
        assert e.saida["destino"] in ("tecnico", "rh") and e.saida["resumo"].startswith("pendência ")
