"""Ferramentas que o LLM pode chamar, com os guarda-corpos do CLAUDE.md.

- O LLM nunca escreve veredito: achados só nascem de audita_linha / audita_funcionario.
- O LLM aponta linhas pelo número; os dados vêm do estado, então ele não
  consegue alterar uma ficha nem inventar um CA.
- Pendência só para achado que existe, uma por achado.
- Ferramenta que falha duas vezes vira pendência de revisão, e o fluxo segue.
"""

from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

from heitor.agente import stubs
from heitor.agente.conferencia_datas import para_auditoria
from heitor.agente.tipos import AchadoDict as Achado, LinhaDict as Linha, PendenciaDict as Pendencia


# ------------------------------------------------ funções reais ou stubs ---

def _importar(candidatos: list[str], nome: str, stub: Callable) -> tuple[Callable, str]:
    """Usa a função real se o módulo do colega já existir; senão, o stub.

    Só cai no stub quando o módulo ainda não existe. Erro dentro de um módulo
    que existe sobe, para ninguém rodar a demo em stub sem perceber.
    """
    for modulo in candidatos:
        try:
            mod = importlib.import_module(modulo)
        except ModuleNotFoundError as e:
            if e.name and modulo.startswith(e.name):
                continue
            raise
        if hasattr(mod, nome):
            return getattr(mod, nome), f"{modulo}.{nome}"
    return stub, f"stub.{nome}"


_FONTES: dict[str, tuple[list[str], Callable]] = {
    "consulta_ca": (["heitor.dados.caepi"], stubs.consulta_ca),
    "buscar_ca_proximo": (["heitor.dados.caepi"], stubs.buscar_ca_proximo),
    "exigencia_funcao": (["heitor.dados.funcoes"], stubs.exigencia_funcao),
    "categoria_epi": (["heitor.dados.funcoes", "heitor.dados.regras"], stubs.categoria_epi),
    "audita_linha": (["heitor.dados.regras"], stubs.audita_linha),
    "audita_funcionario": (["heitor.dados.regras"], stubs.audita_funcionario),
    "calcula_exposicao": (["heitor.dados.exposicao"], stubs.calcula_exposicao),
    "criar_pendencia": (["heitor.api.ferramentas"], stubs.criar_pendencia),
    "fechar_pendencia": (["heitor.api.ferramentas"], stubs.fechar_pendencia),
    "obter_pendencia": (["heitor.api.ferramentas"], stubs.obter_pendencia),
}

IMPL: dict[str, Callable] = {}
ORIGEM: dict[str, str] = {}
for _nome, (_mods, _stub) in _FONTES.items():
    IMPL[_nome], ORIGEM[_nome] = _importar(_mods, _nome, _stub)


def usando_stubs() -> list[str]:
    return sorted(n for n, o in ORIGEM.items() if o.startswith("stub."))


# ------------------------------------------------------------- contexto ---

@dataclass
class Contexto:
    """O que as ferramentas enxergam num episódio (um funcionário)."""

    funcionario_id: str
    funcao: str
    linhas: dict[int, Linha]
    achados: dict[str, Achado] = field(default_factory=dict)  # da auditoria inteira
    pendencias: list[Pendencia] = field(default_factory=list)  # da auditoria inteira
    pendencia_por_achado: dict[str, str] = field(default_factory=dict)
    linhas_auditadas: set[int] = field(default_factory=set)
    funcionario_auditado: bool = False
    revisao: list[str] = field(default_factory=list)  # falhas que viraram pendência de revisão
    auditoria_id: str | None = None
    fora_da_planilha: list[dict[str, Any]] = field(default_factory=list)  # linhas do papel sem entrega na planilha

    def achados_do_funcionario(self) -> list[Achado]:
        return [a for a in self.achados.values() if a.get("funcionario_id") == self.funcionario_id]


@dataclass
class Resultado:
    saida: Any
    ok: bool = True
    terminou: bool = False


# --------------------------------------------------------- sanitização ---

_DATA_BR = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$")


def normalizar_data(valor: Any) -> str | None:
    if valor is None or valor == "":
        return None
    s = str(valor).strip()
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        pass
    m = _DATA_BR.match(s)
    if m:
        d, mth, y = (int(x) for x in m.groups())
        y += 2000 if y < 100 else 0
        try:
            return date(y, mth, d).isoformat()
        except ValueError:
            return None
    return None


def normalizar_ca(valor: Any) -> str | None:
    if valor is None:
        return None
    digitos = re.sub(r"\D", "", str(valor))
    return digitos.lstrip("0") or None if digitos else None


def _numeros_de_linha(valor: Any) -> list[int]:
    if isinstance(valor, int):
        return [valor]
    if isinstance(valor, list):
        return [int(v) for v in valor if str(v).strip().lstrip("-").isdigit()]
    if isinstance(valor, str):
        m = re.match(r"^\s*(\d+)\s*(?:\.\.|-|a)\s*(\d+)\s*$", valor)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            return list(range(min(a, b), max(a, b) + 1))
        return [int(x) for x in re.findall(r"\d+", valor)]
    return []


# ------------------------------------------------------------ execução ---

DESTINO_POR_TIPO = {"corrigivel": "tecnico", "prova": "rh", "passivo": "tecnico"}
# Passivo só gera pendência quando há o que fazer daqui para frente.
PASSIVO_COM_ACAO = {"assinatura_ausente"}


def _t_exigencia_funcao(ctx: Contexto, args: dict) -> Resultado:
    return Resultado(IMPL["exigencia_funcao"](ctx.funcao))


def _t_consulta_ca(ctx: Contexto, args: dict) -> Resultado:
    numero, data_ = normalizar_ca(args.get("numero")), normalizar_data(args.get("data"))
    if not numero or not data_:
        return Resultado({"erro": "informe numero (só dígitos) e data (AAAA-MM-DD)"}, ok=False)
    return Resultado(IMPL["consulta_ca"](numero, data_))


def _t_buscar_ca_proximo(ctx: Contexto, args: dict) -> Resultado:
    numero = normalizar_ca(args.get("numero"))
    if not numero:
        return Resultado({"erro": "informe numero"}, ok=False)
    sugestoes = IMPL["buscar_ca_proximo"](numero)
    return Resultado({"sugestoes": sugestoes,
                      "aviso": "suposição de baixa confiança: nunca gera irregular; vira pedido de confirmação"})


GRUPO_CONFERIR_CA = "conferir_ca"


def _registrar(ctx: Contexto, achados: list[Achado]) -> list[Achado]:
    for a in achados:
        a.setdefault("funcionario_id", ctx.funcionario_id)
        a.setdefault("auditoria_id", ctx.auditoria_id)
        _marcar_conferencia_ca(ctx, a)
        ctx.achados[a["id"]] = a
    return achados


def _marcar_conferencia_ca(ctx: Contexto, a: Achado) -> None:
    """Achado de CA numa linha cujo CA não confere com o EPI: vira conferência no papel, agrupada por ficha.

    Pode ser erro de leitura ou erro de registro (falha real do processo); só o papel diz qual.
    """
    linha = ctx.linhas.get(a.get("linha")) if a.get("linha") is not None else None
    if linha and a.get("regra") == "assinatura_ausente" and (linha.get("confianca") or {}).get("assinatura", 1.0) < 0.7:
        a["grupo"] = GRUPO_CONFERIR_CA  # assinatura em dúvida: conferir no papel, junto com CAs e datas
        return
    conf = (linha or {}).get("conferencia_ca")
    if not linha or not conf or conf.get("confere") is not False or not str(a.get("regra", "")).startswith("ca_"):
        return
    a["grupo"] = GRUPO_CONFERIR_CA
    hip = conf.get("hipotese")
    if hip and "a empresa usa" not in a.get("evidencia", ""):
        a["evidencia"] = (f"{a.get('evidencia', '')}; a empresa usa o CA {hip} para este EPI: se na ficha está "
                          f"escrito {hip}, foi erro de leitura; se está escrito {linha.get('ca')}, o registro está errado")


def criar_conferencia(ctx: Contexto) -> Pendencia | None:
    """UMA pendência por funcionário com tudo o que precisa ser conferido no papel: CAs e datas em dúvida.

    Em cada item: o que foi lido, o provável e por quê. Se o escrito for o provável, foi erro de leitura;
    se for o lido, é falha do registro (achado real; o registro antigo não é reescrito).
    """
    grupo = [a for a in ctx.achados_do_funcionario()
             if a.get("grupo") == GRUPO_CONFERIR_CA and a["id"] not in ctx.pendencia_por_achado]
    itens = []
    for a in sorted(grupo, key=lambda x: x.get("linha") or 0):
        linha = ctx.linhas.get(a.get("linha")) or {}
        if a.get("regra") == "assinatura_ausente":
            if linha.get("assinatura_tipo") == "sem_linha_na_ficha":
                itens.append(f"linha {a.get('linha')}: entrega de {linha.get('data')} ({linha.get('epi')}) não localizada na ficha")
            else:
                texto = linha.get("assinatura_texto")
                itens.append(f"linha {a.get('linha')}: assinatura em dúvida" + (f" (lido '{texto}')" if texto else ""))
            continue
        conf = linha.get("conferencia_ca") or {}
        if conf.get("hipotese"):
            detalhe = f"CA lido {linha.get('ca')}, provável {conf['hipotese']}"
        elif conf.get("equipamento"):
            detalhe = f"CA {linha.get('ca')} é de {conf['equipamento'].lower()[:30]}, ficha diz '{linha.get('epi')}'"
        else:
            detalhe = f"CA lido {linha.get('ca')}, que não existe na base"
        itens.append(f"linha {a.get('linha')}: {detalhe}")
    # datas: agrupa linhas com a mesma leitura e a mesma hipótese ("linhas 1-5: data lida ..., provável ...")
    datas: dict[tuple, list[int]] = {}
    for n, l in sorted(ctx.linhas.items()):
        cd = l.get("conferencia_data")
        if cd:
            datas.setdefault((cd["lida"], cd.get("hipotese"), cd["motivo"]), []).append(n)
    for (lida, hip, motivo), ns in datas.items():
        quais = f"linhas {ns[0]}-{ns[-1]}" if len(ns) > 1 and ns == list(range(ns[0], ns[-1] + 1)) else \
            ("linha " + ", ".join(map(str, ns)))
        itens.append(f"{quais}: data lida {lida}" + (f", provável {hip}" if hip else "") + f" ({motivo})")
    # Linha no papel sem entrega na planilha: depende de leitura aberta (datas frágeis), então só conferência.
    for x in ctx.fora_da_planilha:
        itens.append(f"linha no papel sem entrega na planilha: {x.get('data')} {x.get('epi')} (planilha desatualizada?)")
    if not itens:
        return None
    acao = ("conferir na ficha física: " + "; ".join(itens)
            + ". Se o escrito for diferente do lido, foi erro de leitura; se for igual, o registro está errado e vira achado")
    if grupo:
        ancora = grupo[0]
    else:  # só datas em dúvida: um achado de risco para a pendência existir
        ancora = {"id": f"leitura-{ctx.funcionario_id}", "funcionario_id": ctx.funcionario_id,
                  "auditoria_id": ctx.auditoria_id, "linha": None,
                  "regra": "falha_de_ferramenta",  # PROPOSTA ao Pierre: regra "leitura_incerta"
                  "gravidade": "risco", "tipo": "corrigivel", "grupo": GRUPO_CONFERIR_CA,
                  "evidencia": "; ".join(itens)[:300], "acao_sugerida": "conferir na ficha física"}
        ctx.achados[ancora["id"]] = ancora
    p = criar_pendencia_validada(ctx, ancora, acao=acao, destino="tecnico", limite=900)
    for a in grupo[1:]:
        ctx.pendencia_por_achado[a["id"]] = p["id"]
    return p


def _t_audita_linha(ctx: Contexto, args: dict) -> Resultado:
    numeros = _numeros_de_linha(args.get("linhas", args.get("linha")))
    invalidas = [n for n in numeros if n not in ctx.linhas]
    numeros = [n for n in numeros if n in ctx.linhas]
    if not numeros:
        return Resultado({"erro": f"linhas válidas: {sorted(ctx.linhas)}"}, ok=False)
    por_linha = {}
    for n in numeros:
        achados = _registrar(ctx, IMPL["audita_linha"](para_auditoria(ctx.linhas[n]), ctx.funcao))
        ctx.linhas_auditadas.add(n)
        por_linha[n] = [_resumo_achado(a) for a in achados if a.get("gravidade") != "ok"] or "ok"
    saida: dict[str, Any] = {"por_linha": por_linha}
    if invalidas:
        saida["ignoradas"] = invalidas
    return Resultado(saida)


def _t_audita_funcionario(ctx: Contexto, args: dict) -> Resultado:
    achados = _registrar(ctx, IMPL["audita_funcionario"]([para_auditoria(l) for l in ctx.linhas.values()], ctx.funcao))
    ctx.funcionario_auditado = True
    return Resultado({"achados": [_resumo_achado(a) for a in achados if a.get("gravidade") != "ok"] or "ok"})


def _t_reextrair_campo(ctx: Contexto, args: dict) -> Resultado:
    from heitor.agente import extracao

    n, campo = (_numeros_de_linha(args.get("linha")) or [None])[0], args.get("campo")
    if n not in ctx.linhas or not campo:
        return Resultado({"erro": "informe linha e campo"}, ok=False)
    linha = ctx.linhas[n]
    novo = extracao.reextrair_campo(linha.get("origem", ""), n, campo, dados=linha)
    if novo and novo.get("confianca", 0) > linha.get("confianca", {}).get(campo, 0):
        linha[campo] = novo["valor"]
        linha.setdefault("confianca", {})[campo] = novo["confianca"]
        ctx.linhas_auditadas.discard(n)  # precisa auditar de novo com o valor novo
    return Resultado({"linha": n, "campo": campo, "resultado": novo})


def _t_criar_pendencia(ctx: Contexto, args: dict) -> Resultado:
    achado = ctx.achados.get(str(args.get("achado_id", "")))
    if not achado or achado.get("funcionario_id") != ctx.funcionario_id:
        ids = [a["id"] for a in ctx.achados_do_funcionario() if a.get("gravidade") != "ok"]
        return Resultado({"erro": f"achado inexistente; achados deste funcionário: {ids}"}, ok=False)
    if achado.get("gravidade") == "ok":
        return Resultado({"erro": "achado ok não gera pendência"}, ok=False)
    if achado.get("grupo") == GRUPO_CONFERIR_CA:
        return Resultado({"erro": "CA a conferir no papel: essas conferências viram UMA pendência por ficha, "
                                  "criada automaticamente no fim; não crie pendência para este achado"}, ok=False)
    if achado["id"] in ctx.pendencia_por_achado:
        return Resultado({"erro": f"já existe a pendência {ctx.pendencia_por_achado[achado['id']]}"}, ok=False)
    if achado.get("tipo") == "passivo" and achado.get("regra") not in PASSIVO_COM_ACAO:
        return Resultado({"erro": "passivo sem correção não gera pendência: vai para o relatório com a exposição"},
                         ok=False)
    pendencia = criar_pendencia_validada(ctx, achado, args.get("acao"), args.get("prazo_dias"))
    return Resultado(pendencia)


def criar_pendencia_validada(ctx: Contexto, achado: Achado, acao: Any = None, prazo_dias: Any = None,
                             destino: str | None = None, limite: int = 300) -> Pendencia:
    destino = destino or DESTINO_POR_TIPO.get(achado.get("tipo", ""), "tecnico")
    acao = str(acao or achado.get("acao_sugerida") or "revisar o achado").strip()[:limite]
    if _sugere_fraude(acao):
        acao = achado.get("acao_sugerida") or "revisar o achado"
    try:
        dias = max(1, min(30, int(prazo_dias)))
    except (TypeError, ValueError):
        dias = 5
    prazo = (date.today() + timedelta(days=dias)).isoformat()
    p = IMPL["criar_pendencia"](achado, destino, acao, prazo)
    ctx.pendencias.append(p)
    ctx.pendencia_por_achado[achado["id"]] = p["id"]
    return p


_FRAUDE = re.compile(r"(assinar|preencher|alterar|retroag|antedat).{0,40}(antig|passad|retroativ|anterior)", re.I)


def _sugere_fraude(texto: str) -> bool:
    """Guarda-corpo: nunca pedir para preencher ou assinar ficha antiga com data passada."""
    return bool(_FRAUDE.search(texto))


def _t_terminei(ctx: Contexto, args: dict) -> Resultado:
    return Resultado({"resumo": str(args.get("resumo", ""))[:500]}, terminou=True)


def _resumo_achado(a: Achado) -> dict[str, Any]:
    return {k: a.get(k) for k in ("id", "regra", "gravidade", "tipo", "evidencia", "acao_sugerida")}


@dataclass
class Ferramenta:
    nome: str
    assinatura: str
    descricao: str
    fn: Callable[[Contexto, dict], Resultado]


FERRAMENTAS: dict[str, Ferramenta] = {f.nome: f for f in [
    Ferramenta("exigencia_funcao", "exigencia_funcao()",
               "Agente nocivo, EPIs exigidos, vida útil e grau da função deste funcionário.", _t_exigencia_funcao),
    Ferramenta("audita_linha", 'audita_linha(linhas: list[int] | "1..6")',
               "Aplica as regras às linhas indicadas. É a ÚNICA fonte de veredito (irregular/risco/ok).",
               _t_audita_linha),
    Ferramenta("audita_funcionario", "audita_funcionario()",
               "Regras que olham a ficha inteira: EPI exigido ausente e troca fora da vida útil.",
               _t_audita_funcionario),
    Ferramenta("consulta_ca", "consulta_ca(numero: str, data: 'AAAA-MM-DD')",
               "O CA era válido nessa data? Use para investigar um achado de CA.", _t_consulta_ca),
    Ferramenta("buscar_ca_proximo", "buscar_ca_proximo(numero: str)",
               "CAs com número parecido, para um CA não encontrado. Sempre suposição.", _t_buscar_ca_proximo),
    Ferramenta("reextrair_campo", "reextrair_campo(linha: int, campo: str)",
               "Lê de novo um campo com confiança < 0.7 (só para fichas em foto).", _t_reextrair_campo),
    Ferramenta("criar_pendencia", "criar_pendencia(achado_id: str, acao: str, prazo_dias: int)",
               "Cria a pendência de um achado (o destino técnico/RH é definido pelo tipo).", _t_criar_pendencia),
    Ferramenta("terminei", "terminei(resumo: str)", "Encerra a auditoria deste funcionário.", _t_terminei),
]}


def executar(nome: str, args: dict[str, Any], ctx: Contexto) -> Resultado:
    """Executa com uma nova tentativa; falha dupla vira pendência de revisão."""
    f = FERRAMENTAS.get(nome)
    if not f:
        return Resultado({"erro": f"ferramenta desconhecida '{nome}'. Opções: {list(FERRAMENTAS)}"}, ok=False)
    if not isinstance(args, dict):
        args = {}
    erro: Exception | None = None
    for _ in range(2):
        try:
            return f.fn(ctx, args)
        except Exception as e:  # noqa: BLE001 — qualquer falha de ferramenta segue o fluxo
            erro = e
    return _falha_vira_revisao(ctx, nome, erro)


def _falha_vira_revisao(ctx: Contexto, nome: str, erro: Exception | None) -> Resultado:
    # Uma pendência de revisão por funcionário e ferramenta: sem a base CAEPI, cada linha falharia
    # e o técnico receberia dezenas de avisos iguais sobre a mesma ficha.
    id_revisao = f"rev-{ctx.funcionario_id}-{nome}"
    if id_revisao in ctx.achados:
        evidencia = ctx.achados[id_revisao]["evidencia"]
        return Resultado({"erro": evidencia, "pendencia_de_revisao": ctx.pendencia_por_achado.get(id_revisao),
                          "aviso": "falha repetida; a pendência de revisão já existe"}, ok=False)
    achado: Achado = {"id": id_revisao, "funcionario_id": ctx.funcionario_id,
                      "auditoria_id": ctx.auditoria_id,
                      "linha": None, "regra": "falha_de_ferramenta", "gravidade": "risco", "tipo": "corrigivel",
                      "evidencia": f"{nome} falhou duas vezes: {type(erro).__name__}: {str(erro)[:150]}",
                      "acao_sugerida": "revisar manualmente esta ficha"}
    ctx.achados[achado["id"]] = achado
    ctx.revisao.append(achado["id"])
    try:
        p = criar_pendencia_validada(ctx, achado)
    except Exception:  # noqa: BLE001
        p = None
    return Resultado({"erro": achado["evidencia"], "pendencia_de_revisao": p and p["id"]}, ok=False)


def descrever_ferramentas() -> str:
    return "\n".join(f"- {f.assinatura}: {f.descricao}" for f in FERRAMENTAS.values())


def para_observacao(saida: Any, limite: int = 1800) -> str:
    texto = json.dumps(saida, ensure_ascii=False, default=str)
    return texto if len(texto) <= limite else texto[:limite] + "…(cortado)"
