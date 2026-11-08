"""Laço do agente no LangGraph.

    proximo_funcionario ──► modelo ──► ferramentas ──┐
          ▲   │               ▲                      │ (não terminou)
          │   │               └──────────────────────┘
          │   │ (fila vazia)          │ (terminei / limite)
          │   ▼                       ▼
          │ consolidar ──► FIM    fim_episodio (guarda-corpos)
          └───────────────────────────┘

Um episódio por funcionário. O LLM escolhe a ferramenta; as ferramentas
decidem a verdade. Se o LLM cair, a política determinística assume e o
fluxo segue (nunca trava).

Interface para o Pierre:
    rodar_auditoria(auditoria_id, linhas, emitir_evento) -> dict
    reauditar(pendencia_id, linhas, emitir_evento) -> dict
"""

from __future__ import annotations

import copy
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

from heitor.agente import ferramentas as F
from heitor.agente.conferencia_ca import aplicar as conferir_ca
from heitor.agente.conferencia_ca import hipoteses_da_empresa
from heitor.agente.conferencia_datas import aplicar as conferir_datas
from heitor.agente.llm import ClienteLLM, LLMIndisponivel, extrair_json, llm_ligado
from heitor.agente.tipos import AchadoDict as Achado, EmitirEvento, LinhaDict as Linha, PendenciaDict as Pendencia
from heitor.contrato import Evento

LIMITE_PASSOS = int(os.getenv("HEITOR_LIMITE_PASSOS", "12"))  # por funcionário
TEMPO_MAX_S = float(os.getenv("HEITOR_TEMPO_MAX_S", "600"))  # auditoria inteira
MAX_ERROS_FORMATO = 2  # respostas sem JSON válido antes de a política assumir o passo
PARALELO_PADRAO = 3  # funcionários auditados ao mesmo tempo (limite de chamadas simultâneas do Featherless)
FALHAS_PARA_DESISTIR = 2  # funcionários seguidos com o LLM fora do ar antes de parar de tentar
EVENTOS_DE_ERRO = {"modelo_indisponivel", "resposta_invalida", "pendencia_recusada"}


def _para_dict(obj: Any) -> dict[str, Any]:
    """Modelo Pydantic do contrato (ou dict) -> dict com datas em texto AAAA-MM-DD."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj)

PROMPT_SISTEMA = f"""Você é o Heitor, agente de auditoria PREVENTIVA de fichas de entrega de EPI.
Você cuida de UM funcionário por vez.

OBJETIVO: no histórico de entregas deste funcionário (até 5 anos), descobrir o que precisa ser CORRIGIDO AGORA,
antes de virar acidente, autuação ou processo, e dizer ao técnico de segurança o que fazer, até quando e por quê.

FERRAMENTAS:
{F.descrever_ferramentas()}

COMO DECIDIR (você escolhe o caminho; não precisa usar todas as ferramentas):
- Comece por auditar_ficha: ela traz as falhas apontadas pelas regras. Você NUNCA decide sozinho o que é
  irregular; você decide o que fazer com cada falha.
- Trabalhador SEM PROTEÇÃO HOJE (EPI exigido ausente, troca vencida): pendência URGENTE, prazo_dias 1 ou 2.
- Falha que se corrige daqui para frente: prazo_dias 5 a 10. Entrega sem assinatura é falha do PROCESSO de
  entrega: crie a pendência para o técnico colher a assinatura nas próximas entregas e orientar quem entrega
  (a entrega antiga não se assina com data passada). Treinamento sem registro: pendência também.
- Depende de prova (nota fiscal, lista de presença): pendência, que vai ao RH.
- Passivo (já aconteceu e não tem correção): NÃO crie pendência; ele vai para o relatório.
- Investigar é opcional; corrigir não: toda falha de corrigir_agora ou depende_de_prova precisa de pendência.
  Investigue só quando o resultado muda a correção: conferir_ficha_de_papel quando a assinatura importa e há foto;
  historico_da_empresa ou consulta_ca quando um CA parece estranho.
- Falhas em "conferir_no_papel" (ou com "grupo": "conferir_ca") viram uma conferência automática: não crie pendência.
- Em criar_pendencia, escreva "acao" PARA O TÉCNICO, em uma ou duas frases: o que fazer, com quem e por quê.
  Ex.: "Entregar protetor auricular ao Rafael e colher a assinatura: a última troca foi em 03/2025 e a vida
  útil é de 6 meses, então ele está sem proteção contra o ruído."
- Nunca sugira preencher, assinar ou alterar ficha antiga com data passada: isso é fraude documental.
- Nunca mande retirar, recolher ou deixar de usar um EPI. EPI a mais (não exigido pela função) não é risco
  ao trabalhador; no máximo, peça para conferir se o EPI certo também foi entregue.
- Se há foto da ficha de papel, confira-a (conferir_ficha_de_papel): a planilha diz que foi assinado,
  mas só o papel prova a entrega. Faça isso antes de terminar.
- Ficha sem falhas: termine logo. Você tem no máximo {LIMITE_PASSOS} passos; quando terminar, chame terminei.

Responda SOMENTE com um objeto JSON, sem texto fora dele:
{{"pensamento": "<uma frase curta em português: o que você decidiu e por quê>", "ferramenta": "<nome>", "args": {{...}}}}"""


# ----------------------------------------------------------- execução ---

class Compartilhado:
    """Contadores da auditoria inteira, protegidos por trava: vários funcionários rodam em paralelo."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.passo = 0
        self.custo_usd = 0.0
        self.falhas_seguidas = 0


class Execucao:
    """O que vive fora do estado do grafo: dados, callbacks e o cliente LLM.

    Em paralelo, cada funcionário roda com uma CÓPIA rasa (episodio): contexto próprio, mas os mesmos
    achados, pendências, cliente LLM e contadores (Compartilhado).
    """

    def __init__(self, auditoria_id: str, linhas: list[Any], emitir: EmitirEvento | None,
                 fora_da_planilha: dict[str, list[dict]] | None = None, fotos: dict[str, str] | None = None):
        self.auditoria_id = auditoria_id
        self.fora_da_planilha = fora_da_planilha or {}
        self.fotos = {str(k): v for k, v in (fotos or {}).items()}
        self.emitir = emitir or (lambda e: None)
        self.por_funcionario: dict[str, list[Linha]] = defaultdict(list)
        todas = []
        self.incompletas: list[Linha] = []  # sem data e sem EPI: não entram nas regras (viram "revisar a linha")
        for i, l in enumerate((_para_dict(x) for x in linhas), start=1):
            l.setdefault("linha", i)
            if linha_incompleta(l):
                self.incompletas.append(l)
                continue
            self.por_funcionario[str(l.get("funcionario_id", "?"))].append(l)
            todas.append(l)
        # CA × EPI com todas as fichas juntas: os CAs que a empresa usa viram hipótese para os que não conferem.
        conferir_ca(todas)
        hipoteses_da_empresa(todas)
        conferir_datas(todas)
        self.todas = todas
        self.achados: dict[str, Achado] = {}
        self.pendencias: list[Pendencia] = []
        self.pendencia_por_achado: dict[str, str] = {}
        self.revisao: list[str] = []
        self.consultou_exigencia: set[str] = set()
        self.resumos: dict[str, str] = {}
        self.comp = Compartilhado()
        self.inicio = time.monotonic()
        self.ctx: F.Contexto | None = None
        self.cliente: ClienteLLM | None = None
        self.modo = "deterministico"
        self.modo_por_funcionario: dict[str, str] = {}
        if llm_ligado():
            try:
                self.cliente = ClienteLLM()
                self.modo = "llm"
            except LLMIndisponivel:
                pass

    # contadores compartilhados (leitura simples; escrita sempre pelos métodos abaixo, com trava)
    @property
    def passo(self) -> int:
        return self.comp.passo

    @property
    def custo_usd(self) -> float:
        return self.comp.custo_usd

    @property
    def falhas_seguidas(self) -> int:
        return self.comp.falhas_seguidas

    def somar_custo(self, valor: float) -> None:
        with self.comp.lock:
            self.comp.custo_usd += valor

    def registrar_falha_llm(self, falhou: bool) -> None:
        with self.comp.lock:
            self.comp.falhas_seguidas = self.comp.falhas_seguidas + 1 if falhou else 0

    def episodio(self) -> "Execucao":
        """Cópia rasa para rodar um funcionário em paralelo (contexto próprio, resto compartilhado).

        Os achados ficam num dicionário PRÓPRIO do episódio: as ferramentas percorrem os achados enquanto
        outros funcionários acrescentam os deles, e um dicionário compartilhado derruba a auditoria com
        "dictionary changed size during iteration". rodar_auditoria junta tudo depois que todos terminam.
        """
        c = copy.copy(self)
        c.ctx = None
        c.achados = {}
        return c

    def novo_contexto(self, fid: str) -> F.Contexto:
        linhas = self.por_funcionario[fid]
        self.ctx = F.Contexto(
            funcionario_id=fid, funcao=str(linhas[0].get("funcao", "")),
            linhas={int(l["linha"]): l for l in linhas}, achados=self.achados, pendencias=self.pendencias,
            pendencia_por_achado=self.pendencia_por_achado, revisao=self.revisao,
            auditoria_id=self.auditoria_id, fora_da_planilha=self.fora_da_planilha.get(fid, []),
            foto=self.fotos.get(fid), empresa=self.todas,
        )
        return self.ctx

    def evento(self, ferramenta: str, entrada: dict, saida: Any, custo: float = 0.0,
               pensamento: str | None = None) -> None:
        """Emite no log. Com pensamento, emite antes um evento "decisao" (o porquê do passo)."""
        if pensamento:
            self._emitir("decisao", None, {"escolheu": ferramenta, "args": entrada}, {"pensamento": pensamento}, custo)
            custo = 0.0  # o custo do LLM fica na decisão
        tipo = "erro" if ferramenta in EVENTOS_DE_ERRO else "ferramenta"
        self._emitir(tipo, ferramenta, entrada, saida, custo)

    def _emitir(self, tipo: str, ferramenta: str | None, entrada: dict, saida: Any, custo: float) -> None:
        # Numera e emite sob a trava: com funcionários em paralelo, o log continua 1, 2, 3... e em ordem.
        with self.comp.lock:
            self.comp.passo += 1
            try:
                ev = Evento(auditoria_id=self.auditoria_id, passo=self.comp.passo, tipo=tipo, ferramenta=ferramenta,
                            entrada=entrada if isinstance(entrada, dict) else {}, saida=saida,
                            custo_usd=round(custo, 8), ts=datetime.now(),
                            funcionario_id=self.ctx.funcionario_id if self.ctx else None)
                self.emitir(ev)
            except Exception:  # noqa: BLE001 — log quebrado não derruba a auditoria
                pass

    def tempo_esgotado(self) -> bool:
        return time.monotonic() - self.inicio > TEMPO_MAX_S


def precisa_pendencia(ctx: F.Contexto, a: Achado) -> bool:
    if a.get("gravidade") == "ok" or a["id"] in ctx.pendencia_por_achado or a.get("grupo") == F.GRUPO_CONFERIR_CA:
        return False
    return a.get("tipo") != "passivo" or a.get("regra") in F.PASSIVO_COM_ACAO


def politica_deterministica(exe: Execucao) -> dict[str, Any]:
    """O mesmo roteiro que esperamos do LLM. Usada quando o LLM cai ou está desligado."""
    ctx = exe.ctx
    assert ctx is not None
    if ctx.funcionario_id not in exe.consultou_exigencia:
        return {"ferramenta": "exigencia_funcao", "args": {}, "pensamento": "ver o que a função exige"}
    if set(ctx.linhas) - ctx.linhas_auditadas or not ctx.funcionario_auditado:
        return {"ferramenta": "auditar_ficha", "args": {}, "pensamento": "auditar o histórico inteiro da ficha"}
    if ctx.foto and not ctx.papel_conferido:
        return {"ferramenta": "conferir_ficha_de_papel", "args": {},
                "pensamento": "sem o LLM, confiro sempre a ficha de papel quando há foto (opção segura)"}
    for a in ctx.achados_do_funcionario():
        if precisa_pendencia(ctx, a):
            return {"ferramenta": "criar_pendencia", "args": {"achado_id": a["id"]},
                    "pensamento": f"pendência para {a['regra']}"}
    return {"ferramenta": "terminei", "args": {"resumo": "ficha auditada"}, "pensamento": "nada mais a fazer"}


# -------------------------------------------------------------- grafo ---

class Estado(TypedDict, total=False):
    degradado: bool  # este funcionário segue sem LLM
    fila: list[str]
    atual: Optional[str]
    mensagens: list[dict[str, str]]
    passos_episodio: int
    erros_formato: int
    acao: Optional[dict[str, Any]]
    terminou: bool
    resultado: dict[str, Any]


def _mensagem_ficha(ctx: F.Contexto) -> str:
    campos = ("linha", "data", "epi", "qtd", "ca", "motivo", "assinatura")
    linhas = [{k: l.get(k) for k in campos} for l in ctx.linhas.values()]
    nome = next(iter(ctx.linhas.values())).get("nome", "")
    papel = "há foto da ficha de papel" if ctx.foto else "não há foto da ficha de papel"
    return (f"Hoje é {date.today().isoformat()}. Funcionário {ctx.funcionario_id} ({nome}), função: {ctx.funcao}; {papel}.\n"
            f"Entregas registradas ({len(linhas)}):\n{json.dumps(linhas, ensure_ascii=False, default=str)}\n"
            "O que precisa ser corrigido agora?")


def construir_grafo(exe: Execucao, com_consolidacao: bool = True):
    def proximo_funcionario(state: Estado) -> Estado:
        fila = state.get("fila", [])
        if not fila:
            return {"atual": None}
        ctx = exe.novo_contexto(fila[0])
        # Disjuntor: depois de 2 funcionários seguidos sem LLM, para de tentar (cada tentativa custa até ~30 s).
        degradado = exe.cliente is None or exe.falhas_seguidas >= FALHAS_PARA_DESISTIR
        exe.modo_por_funcionario[ctx.funcionario_id] = "deterministico" if degradado else "llm"
        return {"fila": fila[1:], "atual": ctx.funcionario_id, "passos_episodio": 0, "erros_formato": 0,
                "acao": None, "terminou": False, "degradado": degradado,
                "mensagens": [{"role": "system", "content": PROMPT_SISTEMA},
                              {"role": "user", "content": _mensagem_ficha(ctx)}]}

    def modelo(state: Estado) -> Estado:
        mensagens = list(state["mensagens"])
        passos = state.get("passos_episodio", 0)
        if passos >= LIMITE_PASSOS or exe.tempo_esgotado():
            motivo = "limite de passos" if passos >= LIMITE_PASSOS else "tempo total esgotado"
            return {"acao": {"ferramenta": "terminei", "args": {"resumo": motivo},
                             "pensamento": f"guarda-corpo: {motivo}"}}
        if state.get("degradado") or state.get("erros_formato", 0) >= MAX_ERROS_FORMATO:
            return {"acao": politica_deterministica(exe), "erros_formato": 0}
        try:
            resp = exe.cliente.completar(mensagens)  # type: ignore[union-attr]
        except LLMIndisponivel as e:
            # Modo degradado só neste funcionário; o próximo tenta o LLM de novo (queda passageira não estraga tudo).
            exe.registrar_falha_llm(True)
            exe.modo_por_funcionario[exe.ctx.funcionario_id] = "degradado"  # type: ignore[union-attr]
            desiste = exe.falhas_seguidas >= FALHAS_PARA_DESISTIR
            exe.evento("modelo_indisponivel", {}, {
                "erro": str(e)[:200],
                "agora": "LLM indisponível: este funcionário segue com a política determinística (modo degradado)"
                         + ("; os próximos também, depois de falhas seguidas" if desiste else "; o próximo tenta o LLM de novo")})
            return {"acao": politica_deterministica(exe), "degradado": True}
        exe.registrar_falha_llm(False)
        exe.somar_custo(resp.custo_usd)
        try:
            obj = extrair_json(resp.texto)
            acao = {"ferramenta": str(obj.get("ferramenta", "")).strip(), "args": obj.get("args") or {},
                    "pensamento": str(obj.get("pensamento", ""))[:300], "custo": resp.custo_usd}
        except ValueError:
            mensagens += [{"role": "assistant", "content": resp.texto[:500]},
                          {"role": "user", "content": "Formato inválido. Responda SOMENTE com o objeto JSON."}]
            exe.evento("resposta_invalida", {}, {"texto": resp.texto[:200]}, custo=resp.custo_usd)
            return {"acao": None, "mensagens": mensagens, "passos_episodio": passos + 1,
                    "erros_formato": state.get("erros_formato", 0) + 1}
        return {"acao": acao, "mensagens": mensagens}

    def ferramentas(state: Estado) -> Estado:
        acao = state["acao"] or {}
        nome, args = acao.get("ferramenta", ""), acao.get("args", {})
        r = F.executar(nome, args, exe.ctx)  # type: ignore[arg-type]
        if nome == "exigencia_funcao" and r.ok:
            exe.consultou_exigencia.add(exe.ctx.funcionario_id)  # type: ignore[union-attr]
        if r.terminou:
            exe.resumos[exe.ctx.funcionario_id] = args.get("resumo", "")  # type: ignore[union-attr]
        exe.evento(nome, args if isinstance(args, dict) else {}, r.saida, custo=acao.get("custo", 0.0),
                   pensamento=acao.get("pensamento"))
        restantes = LIMITE_PASSOS - state.get("passos_episodio", 0) - 1
        obs = f"Resultado de {nome}: {F.para_observacao(r.saida)}"
        if not r.ok:
            obs += "\n(Recusado. Corrija e tente de novo.)"
        obs += f"\nPassos restantes: {restantes}."
        decisao = json.dumps({k: acao.get(k) for k in ("pensamento", "ferramenta", "args")}, ensure_ascii=False)
        return {"mensagens": state["mensagens"] + [{"role": "assistant", "content": decisao},
                                                   {"role": "user", "content": obs}],
                "passos_episodio": state.get("passos_episodio", 0) + 1, "terminou": r.terminou}

    def fim_episodio(state: Estado) -> Estado:
        """Guarda-corpos: o que o modelo deixou para trás é feito aqui, e fica no log."""
        ctx = exe.ctx
        assert ctx is not None
        faltam = sorted(set(ctx.linhas) - ctx.linhas_auditadas)
        if faltam:
            r = F.executar("audita_linha", {"linhas": faltam}, ctx)
            exe.evento("audita_linha", {"linhas": faltam}, r.saida,
                       pensamento=f"guarda-corpo: linhas {faltam} não foram auditadas pelo modelo")
        if not ctx.funcionario_auditado:
            r = F.executar("audita_funcionario", {}, ctx)
            exe.evento("audita_funcionario", {}, r.saida, pensamento="guarda-corpo: regras da ficha inteira")
        if ctx.foto and not ctx.papel_conferido:
            r = F.executar("conferir_ficha_de_papel", {}, ctx)
            exe.evento("conferir_ficha_de_papel", {}, r.saida,
                       pensamento="guarda-corpo: há foto da ficha de papel e ela não foi conferida; só o papel prova a assinatura")
        # Falhas que o agente deixou sem pendência: a mesma ação vira UMA pendência listando as linhas
        # (5 avisos "colher assinatura nas próximas entregas" para o mesmo funcionário viram 1).
        grupos: dict[tuple, list[Achado]] = {}
        for a in ctx.achados_do_funcionario():
            if precisa_pendencia(ctx, a):
                grupos.setdefault((a.get("regra"), a.get("acao_sugerida")), []).append(a)
        for (_regra, acao), achados in grupos.items():
            linhas = sorted(a["linha"] for a in achados if a.get("linha") is not None)
            texto = acao or "revisar o achado"
            if len(achados) > 1 and linhas:
                texto += " (linhas " + ", ".join(map(str, linhas)) + ")"
            try:
                p = F.criar_pendencia_validada(ctx, achados[0], acao=texto)
            except Exception as e:  # noqa: BLE001 — ex.: regra ainda fora do contrato; a auditoria segue
                exe.evento("pendencia_recusada", {"achado_id": achados[0]["id"]}, {"erro": f"{type(e).__name__}: {str(e)[:150]}"})
                continue
            for a in achados[1:]:
                ctx.pendencia_por_achado[a["id"]] = p["id"]
            exe.evento("criar_pendencia", {"achados": [a["id"] for a in achados]}, p,
                       pensamento="guarda-corpo: falha sem pendência" + (f" ({len(achados)} iguais, agrupadas)" if len(achados) > 1 else ""))
        try:
            p = F.criar_conferencia(ctx)
        except Exception as e:  # noqa: BLE001
            exe.evento("pendencia_recusada", {"grupo": F.GRUPO_CONFERIR_CA}, {"erro": f"{type(e).__name__}: {str(e)[:150]}"})
            p = None
        if p:
            exe.evento("criar_pendencia", {"grupo": F.GRUPO_CONFERIR_CA}, p,
                       pensamento="o que não fecha entre ficha, planilha e base: uma conferência no papel")
        return {}

    def consolidar(state: Estado) -> Estado:
        return {"resultado": _consolidar(exe)}

    g = StateGraph(Estado)
    for nome, fn in [("proximo_funcionario", proximo_funcionario), ("modelo", modelo),
                     ("ferramentas", ferramentas), ("fim_episodio", fim_episodio), ("consolidar", consolidar)]:
        g.add_node(nome, fn)
    g.set_entry_point("proximo_funcionario")
    fim = "consolidar" if com_consolidacao else END
    g.add_conditional_edges("proximo_funcionario", lambda s: "modelo" if s.get("atual") else fim)
    g.add_conditional_edges("modelo", lambda s: "ferramentas" if s.get("acao") else "modelo")
    g.add_conditional_edges("ferramentas", lambda s: "fim_episodio" if s.get("terminou") else "modelo")
    g.add_edge("fim_episodio", "proximo_funcionario")
    g.add_edge("consolidar", END)
    return g.compile()


def linha_incompleta(l: Linha) -> bool:
    """Linha sem data e sem EPI: a planilha não foi lida direito (ex.: tudo colado na coluna A).

    Auditar uma linha assim acusaria "assinatura ausente" de um registro que nem foi lido.
    """
    return not l.get("data") and not str(l.get("epi") or "").strip()


def _revisar_incompletas(exe: Execucao) -> None:
    """Cada linha incompleta vira risco "revisar a linha da planilha", nunca acusação."""
    for l in exe.incompletas:
        fid, n = str(l.get("funcionario_id") or "?"), l.get("linha")
        achado: Achado = {
            "id": f"incompleta-{fid}-{n}", "auditoria_id": exe.auditoria_id, "funcionario_id": fid, "linha": n,
            "regra": "leitura_incerta", "gravidade": "risco", "tipo": "corrigivel",
            "evidencia": f"linha {n} da planilha sem data e sem EPI (colunas não separadas?); nada foi auditado nela",
            "acao_sugerida": f"revisar a linha {n} da planilha: separar os dados nas colunas",
        }
        exe.achados[achado["id"]] = achado
        ctx = F.Contexto(funcionario_id=fid, funcao="", linhas={}, achados=exe.achados, pendencias=exe.pendencias,
                         pendencia_por_achado=exe.pendencia_por_achado, auditoria_id=exe.auditoria_id)
        try:
            p = F.criar_pendencia_validada(ctx, achado, destino="tecnico")
        except Exception as e:  # noqa: BLE001
            exe.evento("pendencia_recusada", {"achado_id": achado["id"]}, {"erro": type(e).__name__})
            continue
        exe.evento("criar_pendencia", {"achado_id": achado["id"]}, p,
                   pensamento="guarda-corpo: linha incompleta na planilha não é auditada; pedir revisão")


def _consolidar(exe: Execucao) -> dict[str, Any]:
    """Depois de todos os funcionários: exposição em R$, relatório e o resultado da auditoria."""
    exe.ctx = None
    _revisar_incompletas(exe)
    achados = list(exe.achados.values())
    # A exposição real (Gustavo) usa a função de cada funcionário (grau) e a data de cada achado (meses).
    funcoes = {fid: str(ls[0].get("funcao", "")) for fid, ls in exe.por_funcionario.items() if ls}
    for a in achados:
        a.setdefault("data", _data_do_achado(exe, a))
    exposicao = F.IMPL["calcula_exposicao"](achados, funcoes=funcoes)
    exe.evento("calcula_exposicao", {"achados": len(achados), "funcoes": funcoes}, exposicao)
    relatorio = _gerar_relatorio(achados, exposicao)
    if relatorio is not None:
        exe.evento("gerar_relatorio", {"achados": len(achados)}, {"itens": len(relatorio.get("itens", []))})
    cont = {g: sum(1 for a in achados if a.get("gravidade") == g) for g in ("irregular", "risco")}
    return {
        "auditoria_id": exe.auditoria_id, "status": "concluida", "modo": _modo_final(exe),
        "modo_por_funcionario": exe.modo_por_funcionario,
        "contagem": cont, "achados": achados, "pendencias": exe.pendencias, "exposicao": exposicao,
        "relatorio": relatorio, "passos": exe.passo, "custo_usd": round(exe.custo_usd, 6),
        "duracao_s": round(time.monotonic() - exe.inicio, 1), "stubs": F.usando_stubs(),
    }


def _modo_final(exe: Execucao) -> str:
    """llm: todos com LLM; misto: algum em modo degradado; deterministico: nenhum com LLM."""
    modos = set(exe.modo_por_funcionario.values())
    if not modos or modos == {"deterministico"}:
        return "deterministico"
    return "llm" if modos == {"llm"} else "misto"


def _data_do_achado(exe: Execucao, a: Achado) -> str | None:
    """Data da linha do achado; para achado da ficha inteira (linha None), a entrega mais antiga do funcionário."""
    linhas = exe.por_funcionario.get(str(a.get("funcionario_id")), [])
    if a.get("linha") is not None:
        for l in linhas:
            if l.get("linha") == a["linha"] and l.get("data"):
                return str(l["data"])
    datas = sorted(str(l["data"]) for l in linhas if l.get("data"))
    return datas[0] if datas else None


def _gerar_relatorio(achados: list[Achado], exposicao: dict) -> dict | None:
    try:
        from heitor.agente.relatorio import gerar_relatorio
    except ImportError:
        return None  # relatorio.py ainda não existe
    return gerar_relatorio(achados, exposicao)


# ------------------------------------------------------- interface ---

def rodar_auditoria(auditoria_id: str, linhas: list[Any], emitir_evento: EmitirEvento | None = None,
                    fora_da_planilha: dict[str, list[dict]] | None = None, _passo_inicial: int = 0,
                    fotos: dict[str, str] | None = None) -> dict:
    exe = Execucao(auditoria_id, linhas, emitir_evento, fora_da_planilha, fotos)
    exe.comp.passo = _passo_inicial  # o log continua a numeração de quem chamou (conferir_e_auditar)
    fids = list(exe.por_funcionario)
    paralelo = max(1, int(os.getenv("HEITOR_PARALELO", PARALELO_PADRAO)))
    if paralelo == 1 or len(fids) <= 1:
        limite = len(fids) * (LIMITE_PASSOS * 2 + 8) + 10
        return construir_grafo(exe).invoke({"fila": fids}, {"recursion_limit": limite})["resultado"]

    # Um grafo por funcionário, até `paralelo` ao mesmo tempo; a consolidação roda uma vez no fim.
    def episodio(fid: str) -> Execucao:
        ep = exe.episodio()
        construir_grafo(ep, com_consolidacao=False).invoke({"fila": [fid]}, {"recursion_limit": LIMITE_PASSOS * 2 + 18})
        return ep

    with ThreadPoolExecutor(max_workers=paralelo) as pool:
        episodios = [f.result() for f in [pool.submit(episodio, fid) for fid in fids]]
        # f.result() propaga exceção inesperada (as esperadas já viram pendência de revisão)
    for ep in episodios:  # todos terminaram: junta os achados de cada funcionário, sem concorrência
        exe.achados.update(ep.achados)
    return _consolidar(exe)


def conferir_e_auditar(auditoria_id: str, linhas: list[Any], fotos: dict[str, str],
                       emitir_evento: EmitirEvento | None = None) -> dict:
    """Fluxo com ficha de papel: os dados vêm da PLANILHA; a foto prova a assinatura.

    linhas: entregas da planilha (todas as fichas da auditoria).
    fotos:  {funcionario_id: caminho da foto da ficha de papel daquele funcionário}.
    O AGENTE decide, por funcionário, se vale conferir a ficha de papel (ferramenta conferir_ficha_de_papel).
    Sem LLM, a política determinística confere sempre que há foto.
    """
    return rodar_auditoria(auditoria_id, linhas, emitir_evento, fotos=fotos)


_REGRAS_DA_FICHA = {"epi_inadequado", "troca_atrasada"}


def reauditar(pendencia_id: str, linhas: list[Any], emitir_evento: EmitirEvento | None = None) -> dict:
    """Confere a correção com as mesmas regras e fecha ou reabre a pendência.

    Determinística de propósito: quem fecha uma pendência são as regras.
    """
    obtido = F.IMPL["obter_pendencia"](pendencia_id)
    if not obtido:
        return {"pendencia_id": pendencia_id, "status": "erro", "motivo": "pendência não encontrada"}
    pendencia, achado = obtido
    exe = Execucao(f"re-{pendencia_id}", linhas, emitir_evento)
    exe.modo = "deterministico"
    fid = str(achado.get("funcionario_id"))
    if not exe.por_funcionario.get(fid):
        # Nenhuma linha DESTE funcionário: documento (nota fiscal, lista de presença: o modelo de visão lê os itens
        # da nota como "linhas" sem dono), arquivo de outro funcionário ou leitura que falhou. As regras não têm o
        # que conferir; reabrir diria "não corrigiu" sem saber. Fica para uma pessoa olhar (a API já marcou a
        # pendência como "aguardando" ao receber a resposta).
        motivo = (f"o arquivo não tem entregas do funcionário {fid} (documento ou ficha de outra pessoa?); "
                  "fica aguardando conferência humana")
        exe.evento("fechar_pendencia", {"pendencia_id": pendencia_id, "resultado": "sem_decisao"}, {}, pensamento=motivo)
        status = pendencia.get("status") if isinstance(pendencia, dict) else getattr(pendencia, "status", None)
        return {"pendencia_id": pendencia_id, "status": status or "aguardando", "motivo": motivo, "achados_novos": []}
    ctx = exe.novo_contexto(fid) if exe.por_funcionario.get(fid) else None

    novos: list[Achado] = []
    if ctx:
        r = F.executar("audita_linha", {"linhas": sorted(ctx.linhas)}, ctx)
        exe.evento("audita_linha", {"linhas": sorted(ctx.linhas)}, r.saida, pensamento="reauditar a correção")
        novos = [a for a in ctx.achados_do_funcionario() if a.get("gravidade") != "ok"]

    if not ctx:
        confere, motivo = False, "nenhuma linha nova deste funcionário"
    elif achado.get("regra") in _REGRAS_DA_FICHA:
        cat = _categoria_do_achado(achado, ctx.funcao)
        boas = [l for l in ctx.linhas.values()
                if F.IMPL["categoria_epi"](l.get("epi")) == cat
                and not any(a.get("linha") == l["linha"] for a in novos)]
        confere = bool(boas)
        motivo = f"entrega de {cat} registrada sem falhas" if confere else f"nenhuma entrega válida de {cat}"
    else:
        mesma = [a for a in novos if a.get("regra") == achado.get("regra")]
        confere = not mesma
        motivo = "a falha não aparece mais" if confere else f"a falha continua: {mesma[0]['evidencia']}"

    resultado = "confirmada" if confere else "nao_confirmada"
    p = F.IMPL["fechar_pendencia"](pendencia, resultado)
    exe.evento("fechar_pendencia", {"pendencia_id": pendencia_id, "resultado": resultado}, p, pensamento=motivo)
    return {"pendencia_id": pendencia_id, "status": p["status"], "motivo": motivo, "achados_novos": novos}


def _categoria_do_achado(achado: Achado, funcao: str) -> str | None:
    exig = F.IMPL["exigencia_funcao"](funcao)
    texto = f"{achado.get('evidencia', '')} {achado.get('acao_sugerida', '')}".lower()
    for e in exig.get("epis", []):
        if e["epi"] in texto:
            return e["epi"]
    return None
