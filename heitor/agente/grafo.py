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

import json
import os
import time
from collections import defaultdict
from datetime import datetime
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
EVENTOS_DE_ERRO = {"modelo_indisponivel", "resposta_invalida"}


def _para_dict(obj: Any) -> dict[str, Any]:
    """Modelo Pydantic do contrato (ou dict) -> dict com datas em texto AAAA-MM-DD."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return dict(obj)

PROMPT_SISTEMA = f"""Você é o Heitor, um agente que audita fichas de entrega de EPI de UM funcionário por vez.

Ferramentas:
{F.descrever_ferramentas()}

Regras:
1. Você NÃO decide se algo é irregular. Só audita_linha e audita_funcionario produzem veredito.
2. Audite TODAS as linhas da ficha e rode audita_funcionario uma vez.
3. Para cada achado com gravidade irregular ou risco, crie uma pendência com uma ação concreta.
   Passivo sem correção não gera pendência (vai para o relatório), exceto assinatura_ausente,
   que gera pendência para colher assinatura nas PRÓXIMAS entregas.
4. Nunca sugira preencher, assinar ou alterar ficha antiga com data passada: isso é fraude.
5. Campo com confiança < 0.7: use reextrair_campo antes de auditar a linha.
6. CA não encontrado: use buscar_ca_proximo. Sugestão é suposição, nunca irregularidade.
   Achado com "grupo": "conferir_ca" vira uma conferência no papel criada automaticamente: não crie pendência para ele.
7. Você tem no máximo {LIMITE_PASSOS} passos. Quando acabar, chame terminei.

Responda SOMENTE com um objeto JSON, sem texto fora dele:
{{"pensamento": "<uma frase curta em português>", "ferramenta": "<nome>", "args": {{...}}}}"""


# ----------------------------------------------------------- execução ---

class Execucao:
    """O que vive fora do estado do grafo: dados, callbacks e o cliente LLM."""

    def __init__(self, auditoria_id: str, linhas: list[Any], emitir: EmitirEvento | None,
                 fora_da_planilha: dict[str, list[dict]] | None = None):
        self.auditoria_id = auditoria_id
        self.fora_da_planilha = fora_da_planilha or {}
        self.emitir = emitir or (lambda e: None)
        self.por_funcionario: dict[str, list[Linha]] = defaultdict(list)
        todas = []
        for i, l in enumerate((_para_dict(x) for x in linhas), start=1):
            l.setdefault("linha", i)
            self.por_funcionario[str(l.get("funcionario_id", "?"))].append(l)
            todas.append(l)
        # CA × EPI com todas as fichas juntas: os CAs que a empresa usa viram hipótese para os que não conferem.
        conferir_ca(todas)
        hipoteses_da_empresa(todas)
        conferir_datas(todas)
        self.achados: dict[str, Achado] = {}
        self.pendencias: list[Pendencia] = []
        self.pendencia_por_achado: dict[str, str] = {}
        self.revisao: list[str] = []
        self.consultou_exigencia: set[str] = set()
        self.resumos: dict[str, str] = {}
        self.passo = 0
        self.custo_usd = 0.0
        self.inicio = time.monotonic()
        self.ctx: F.Contexto | None = None
        self.cliente: ClienteLLM | None = None
        self.modo = "deterministico"
        if llm_ligado():
            try:
                self.cliente = ClienteLLM()
                self.modo = "llm"
            except LLMIndisponivel:
                pass

    def novo_contexto(self, fid: str) -> F.Contexto:
        linhas = self.por_funcionario[fid]
        self.ctx = F.Contexto(
            funcionario_id=fid, funcao=str(linhas[0].get("funcao", "")),
            linhas={int(l["linha"]): l for l in linhas}, achados=self.achados, pendencias=self.pendencias,
            pendencia_por_achado=self.pendencia_por_achado, revisao=self.revisao,
            auditoria_id=self.auditoria_id, fora_da_planilha=self.fora_da_planilha.get(fid, []),
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
        self.passo += 1
        try:
            ev = Evento(auditoria_id=self.auditoria_id, passo=self.passo, tipo=tipo, ferramenta=ferramenta,
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
    pendentes = sorted(set(ctx.linhas) - ctx.linhas_auditadas)
    if pendentes:
        return {"ferramenta": "audita_linha", "args": {"linhas": pendentes}, "pensamento": "auditar as linhas"}
    if not ctx.funcionario_auditado:
        return {"ferramenta": "audita_funcionario", "args": {}, "pensamento": "regras da ficha inteira"}
    for a in ctx.achados_do_funcionario():
        if precisa_pendencia(ctx, a):
            return {"ferramenta": "criar_pendencia", "args": {"achado_id": a["id"]},
                    "pensamento": f"pendência para {a['regra']}"}
    return {"ferramenta": "terminei", "args": {"resumo": "ficha auditada"}, "pensamento": "nada mais a fazer"}


# -------------------------------------------------------------- grafo ---

class Estado(TypedDict, total=False):
    fila: list[str]
    atual: Optional[str]
    mensagens: list[dict[str, str]]
    passos_episodio: int
    erros_formato: int
    acao: Optional[dict[str, Any]]
    terminou: bool
    resultado: dict[str, Any]


def _mensagem_ficha(ctx: F.Contexto) -> str:
    linhas = [{k: v for k, v in l.items() if k not in ("funcionario_id", "nome", "funcao", "origem")}
              for l in ctx.linhas.values()]
    nome = next(iter(ctx.linhas.values())).get("nome", "")
    return (f"Funcionário {ctx.funcionario_id} ({nome}), função: {ctx.funcao}.\n"
            f"Linhas da ficha:\n{json.dumps(linhas, ensure_ascii=False, default=str)}\n"
            "Audite esta ficha.")


def construir_grafo(exe: Execucao):
    def proximo_funcionario(state: Estado) -> Estado:
        fila = state.get("fila", [])
        if not fila:
            return {"atual": None}
        ctx = exe.novo_contexto(fila[0])
        return {"fila": fila[1:], "atual": ctx.funcionario_id, "passos_episodio": 0, "erros_formato": 0,
                "acao": None, "terminou": False,
                "mensagens": [{"role": "system", "content": PROMPT_SISTEMA},
                              {"role": "user", "content": _mensagem_ficha(ctx)}]}

    def modelo(state: Estado) -> Estado:
        mensagens = list(state["mensagens"])
        passos = state.get("passos_episodio", 0)
        if passos >= LIMITE_PASSOS or exe.tempo_esgotado():
            motivo = "limite de passos" if passos >= LIMITE_PASSOS else "tempo total esgotado"
            return {"acao": {"ferramenta": "terminei", "args": {"resumo": motivo},
                             "pensamento": f"guarda-corpo: {motivo}"}}
        if exe.modo != "llm" or state.get("erros_formato", 0) >= MAX_ERROS_FORMATO:
            return {"acao": politica_deterministica(exe), "erros_formato": 0}
        try:
            resp = exe.cliente.completar(mensagens)  # type: ignore[union-attr]
        except LLMIndisponivel as e:
            exe.modo = "deterministico"
            exe.evento("modelo_indisponivel", {}, {"erro": str(e)[:200], "agora": "política determinística"})
            return {"acao": politica_deterministica(exe)}
        exe.custo_usd += resp.custo_usd
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
        for a in ctx.achados_do_funcionario():
            if precisa_pendencia(ctx, a):
                p = F.criar_pendencia_validada(ctx, a)
                exe.evento("criar_pendencia", {"achado_id": a["id"]}, p,
                           pensamento="guarda-corpo: achado sem pendência")
        p = F.criar_conferencia(ctx)
        if p:
            exe.evento("criar_pendencia", {"grupo": F.GRUPO_CONFERIR_CA}, p,
                       pensamento="CAs ou datas que não fecham com o resto da ficha: uma conferência no papel")
        return {}

    def consolidar(state: Estado) -> Estado:
        exe.ctx = None
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
        return {"resultado": {
            "auditoria_id": exe.auditoria_id, "status": "concluida", "modo": exe.modo,
            "contagem": cont, "achados": achados, "pendencias": exe.pendencias, "exposicao": exposicao,
            "relatorio": relatorio, "passos": exe.passo, "custo_usd": round(exe.custo_usd, 6),
            "duracao_s": round(time.monotonic() - exe.inicio, 1), "stubs": F.usando_stubs(),
        }}

    g = StateGraph(Estado)
    for nome, fn in [("proximo_funcionario", proximo_funcionario), ("modelo", modelo),
                     ("ferramentas", ferramentas), ("fim_episodio", fim_episodio), ("consolidar", consolidar)]:
        g.add_node(nome, fn)
    g.set_entry_point("proximo_funcionario")
    g.add_conditional_edges("proximo_funcionario", lambda s: "modelo" if s.get("atual") else "consolidar")
    g.add_conditional_edges("modelo", lambda s: "ferramentas" if s.get("acao") else "modelo")
    g.add_conditional_edges("ferramentas", lambda s: "fim_episodio" if s.get("terminou") else "modelo")
    g.add_edge("fim_episodio", "proximo_funcionario")
    g.add_edge("consolidar", END)
    return g.compile()


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
                    fora_da_planilha: dict[str, list[dict]] | None = None, _passo_inicial: int = 0) -> dict:
    exe = Execucao(auditoria_id, linhas, emitir_evento, fora_da_planilha)
    exe.passo = _passo_inicial  # o log continua a numeração de quem chamou (conferir_e_auditar)
    grafo = construir_grafo(exe)
    limite = len(exe.por_funcionario) * (LIMITE_PASSOS * 2 + 8) + 10
    final = grafo.invoke({"fila": list(exe.por_funcionario)}, {"recursion_limit": limite})
    return final["resultado"]


def conferir_e_auditar(auditoria_id: str, linhas: list[Any], fotos: dict[str, str],
                       emitir_evento: EmitirEvento | None = None) -> dict:
    """Fluxo principal com ficha de papel: os dados vêm da PLANILHA; a foto só prova a assinatura.

    linhas: entregas da planilha (todas as fichas da auditoria).
    fotos:  {funcionario_id: caminho da foto da ficha de papel daquele funcionário}.
    Para cada funcionário com foto, confere as assinaturas contra a planilha (conferencia_assinaturas)
    e depois roda a auditoria normal. Fica aqui (e não na API) porque os campos internos da conferência
    (tipo da assinatura, entrega sem linha na ficha) se perdem quando a linha passa pelo modelo Linha.
    """
    from heitor.agente.conferencia_assinaturas import conferir_assinaturas

    todas = [_para_dict(x) for x in linhas]
    log = Execucao(auditoria_id, [], emitir_evento)  # só para emitir os eventos da conferência no log
    fora: dict[str, list[dict]] = {}
    for fid, foto in fotos.items():
        do_func = [l for l in todas if str(l.get("funcionario_id")) == str(fid)]
        if not do_func:
            continue
        try:
            r = conferir_assinaturas(foto, do_func)
        except Exception as e:  # noqa: BLE001 — sem a conferência, as assinaturas ficam como vieram da planilha
            log.evento("conferir_assinaturas", {"funcionario_id": fid}, {"erro": str(e)[:200]})
            continue
        por_linha = {l["linha"]: l for l in r["linhas"]}
        for i, l in enumerate(todas):
            if str(l.get("funcionario_id")) == str(fid) and l.get("linha") in por_linha:
                todas[i] = por_linha[l["linha"]]
        fora[str(fid)] = r["fora_da_planilha"]
        resumo = {"entregas": len(r["linhas"]),
                  "assinadas": sum(1 for l in r["linhas"] if l.get("assinatura") is True and l["confianca"].get("assinatura", 0) >= 0.7),
                  "em_duvida": sum(1 for l in r["linhas"] if l["confianca"].get("assinatura", 0) < 0.7),
                  "fora_da_planilha": len(r["fora_da_planilha"]), "custo_usd": r["custo_usd"]}
        log.evento("conferir_assinaturas", {"funcionario_id": fid}, resumo, custo=r["custo_usd"],
                   pensamento="a planilha diz o que foi entregue; a ficha de papel precisa provar com a assinatura")
    return rodar_auditoria(auditoria_id, todas, emitir_evento, fora_da_planilha=fora, _passo_inicial=log.passo)


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
