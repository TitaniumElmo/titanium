"""Visões prontas para a interface: funcionários, cronograma e relatório por período.

São só leitura e usam o que já está no `estado` (auditorias, linhas, achados,
pendências). Nenhuma regra de auditoria nova: a vida útil vem de
`heitor.dados.funcoes` e a validade do CA de `heitor.dados.caepi`.

A ficha de cada funcionário é a da auditoria MAIS RECENTE que o incluiu (o vigia
audita só quem mudou), e os achados dele são os dessa mesma auditoria.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from heitor.api.estado import estado
from heitor.contrato import Achado, Linha, Pendencia
from heitor.dados.funcoes import categoria_epi, exigencia_funcao

log = logging.getLogger("heitor.visoes")

JANELA_TROCAS_DIAS = 365  # troca só entra na conta se a última entrega é deste último ano
FOLGA_ANTECEDENCIA_DIAS = 15  # a mais, além da antecedência configurada, que ainda entra no cronograma


def _hoje() -> date:
    return date.today()


def _como_data(valor: Any) -> Optional[date]:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        return None


# -- ficha atual de cada funcionário ----------------------------------------------


def _atuais() -> dict[str, dict[str, Any]]:
    """{funcionario_id: {"auditoria_id", "linhas", "achados"}} da auditoria mais recente que o incluiu."""
    atual: dict[str, dict[str, Any]] = {}
    for aud in estado.listar_auditorias():  # a mais recente primeiro
        por_func: dict[str, list[Linha]] = {}
        for linha in estado.obter_linhas(aud.id):
            por_func.setdefault(linha.funcionario_id, []).append(linha)
        achados = estado.listar_achados(aud.id)
        for fid, linhas in por_func.items():
            if fid in atual:
                continue
            atual[fid] = {
                "auditoria_id": aud.id,
                "linhas": sorted(linhas, key=lambda l: (l.data is None, l.data, l.linha)),
                "achados": [a for a in achados if a.funcionario_id == fid],
            }
    return atual


def _nome_e_funcao(linhas: list[Linha]) -> tuple[str, str]:
    for linha in linhas:
        if linha.nome:
            return linha.nome, linha.funcao
    return "", ""


def _achado_aberto(achado: Achado, pendencias: list[Pendencia]) -> bool:
    do_achado = [p for p in pendencias if p.achado_id == achado.id]
    return not do_achado or any(p.status != "fechada" for p in do_achado)


def _pior_gravidade(achados: list[Achado]) -> str:
    if any(a.gravidade == "irregular" for a in achados):
        return "irregular"
    if any(a.gravidade == "risco" for a in achados):
        return "risco"
    return "ok"


# -- trocas previstas (vida útil do fabricante) ------------------------------------


def trocas_previstas(funcao: str, linhas: list[Linha], hoje: date) -> list[dict[str, str]]:
    """Para cada EPI exigido da função, a última entrega e quando vence a vida útil."""
    exig = exigencia_funcao(funcao)
    if not exig.get("encontrada"):
        return []
    vida = {categoria_epi(e["epi"]): int(e["vida_util_dias"]) for e in exig["epis"] if e.get("vida_util_dias")}
    ultimas: dict[str, date] = {}
    for linha in linhas:
        categoria = categoria_epi(linha.epi)
        if categoria in vida and linha.data and (categoria not in ultimas or linha.data > ultimas[categoria]):
            ultimas[categoria] = linha.data
    limite = hoje - timedelta(days=JANELA_TROCAS_DIAS)
    trocas = [
        {"epi": cat, "ultima": ult.isoformat(), "vence": (ult + timedelta(days=vida[cat])).isoformat()}
        for cat, ult in ultimas.items()
        if ult >= limite
    ]
    return sorted(trocas, key=lambda t: t["vence"])


# -- funcionários ------------------------------------------------------------------


def _resumo(fid: str, ficha: dict[str, Any], pendencias: list[Pendencia], hoje: date) -> dict[str, Any]:
    nome, funcao = _nome_e_funcao(ficha["linhas"])
    abertos = [a for a in ficha["achados"] if _achado_aberto(a, pendencias)]
    datas = [l.data for l in ficha["linhas"] if l.data]
    trocas = trocas_previstas(funcao, ficha["linhas"], hoje)
    return {
        "funcionario_id": fid,
        "nome": nome,
        "funcao": funcao,
        "status": _pior_gravidade(abertos),
        "achados_abertos": len(abertos),
        "pendencias_abertas": sum(1 for p in pendencias if p.funcionario_id == fid and p.status != "fechada"),
        "ultima_entrega": max(datas).isoformat() if datas else None,
        "proxima_troca": trocas[0]["vence"] if trocas else None,
    }


def funcionarios(hoje: Optional[date] = None) -> list[dict[str, Any]]:
    hoje = hoje or _hoje()
    pendencias = estado.listar_pendencias()
    itens = [_resumo(fid, ficha, pendencias, hoje) for fid, ficha in _atuais().items()]
    return sorted(itens, key=lambda i: (i["nome"] or i["funcionario_id"]))


def funcionario(fid: str, hoje: Optional[date] = None) -> Optional[dict[str, Any]]:
    hoje = hoje or _hoje()
    ficha = _atuais().get(fid)
    if ficha is None:
        return None
    pendencias = estado.listar_pendencias()
    return {
        **_resumo(fid, ficha, pendencias, hoje),
        "auditoria_id": ficha["auditoria_id"],
        "linhas": [l.model_dump(mode="json") for l in ficha["linhas"]],
        "achados": [a.model_dump(mode="json") for a in ficha["achados"]],
        "pendencias": [p.model_dump(mode="json") for p in pendencias if p.funcionario_id == fid],
        "trocas": trocas_previstas(_nome_e_funcao(ficha["linhas"])[1], ficha["linhas"], hoje),
    }


# -- cronograma --------------------------------------------------------------------


def _validade_do_ca(numero: str, data: date) -> Optional[date]:
    """Validade do CA na base do MTE; None se a base não está carregada ou o CA não existe."""
    try:
        from heitor.dados.caepi import consulta_ca

        r = consulta_ca(numero, data)
    except Exception:
        log.debug("base CAEPI indisponível para o cronograma", exc_info=True)
        return None
    return _como_data(r.get("validade")) if r.get("encontrado") else None


def cronograma(de: date, ate: date, hoje: Optional[date] = None, antecedencia_dias: Optional[int] = None) -> list[dict[str, Any]]:
    """Trocas de EPI pela vida útil, CAs perto de vencer e prazos das pendências, de `de` a `ate`.

    Treinamento e DDS ainda não têm fonte de dados no back e por isso não aparecem."""
    from heitor.api import configuracoes

    hoje = hoje or _hoje()
    antecedencia = configuracoes.atual().antecedencia_troca_dias if antecedencia_dias is None else antecedencia_dias
    itens: list[dict[str, Any]] = []
    dentro = lambda d: de <= d <= ate  # noqa: E731

    fichas = _atuais()
    for fid, ficha in fichas.items():
        nome, funcao = _nome_e_funcao(ficha["linhas"])
        for t in trocas_previstas(funcao, ficha["linhas"], hoje):
            vence = date.fromisoformat(t["vence"])
            if not dentro(vence) or (vence - hoje).days > antecedencia + FOLGA_ANTECEDENCIA_DIAS:
                continue
            itens.append({
                "id": f"c-troca-{fid}-{t['epi']}", "tipo": "troca_epi", "funcionario_id": fid, "nome": nome, "funcao": funcao,
                "titulo": f"Trocar {t['epi']}",
                "descricao": f"Última entrega em {date.fromisoformat(t['ultima']):%d/%m/%Y}, conforme a durabilidade indicada pelo fabricante",
                "data": t["vence"], "status": "atrasado" if vence < hoje else "previsto", "origem": "agente", "pendencia_id": None,
            })
        recentes: dict[str, Linha] = {}
        for linha in ficha["linhas"]:
            if linha.ca and linha.data:
                recentes[categoria_epi(linha.epi)] = linha
        for categoria, linha in recentes.items():
            validade = _validade_do_ca(linha.ca, linha.data)  # type: ignore[arg-type]
            if validade is None or not dentro(validade) or (validade - hoje).days > antecedencia + FOLGA_ANTECEDENCIA_DIAS:
                continue
            itens.append({
                "id": f"c-ca-{fid}-{linha.ca}", "tipo": "ca_vencendo", "funcionario_id": fid, "nome": nome, "funcao": funcao,
                "titulo": f"CA {linha.ca} ({categoria}) vence",
                "descricao": "Validade na base do MTE; depois da compra vale a vida útil do produto",
                "data": validade.isoformat(), "status": "atrasado" if validade < hoje else "previsto", "origem": "agente",
                "pendencia_id": None,
            })

    funcoes = {fid: _nome_e_funcao(f["linhas"])[1] for fid, f in fichas.items()}
    for p in estado.listar_pendencias():
        if not dentro(p.prazo):
            continue
        itens.append({
            "id": f"c-{p.id}", "tipo": "prazo_pendencia", "funcionario_id": p.funcionario_id, "nome": p.funcionario_nome,
            "funcao": funcoes.get(p.funcionario_id or "") or None,
            "titulo": f"Prazo da pendência {p.id}: {p.acao}", "data": p.prazo.isoformat(),
            "status": "feito" if p.status == "fechada" else "atrasado" if p.prazo < hoje else "previsto",
            "origem": "agente", "pendencia_id": p.id,
        })
    return sorted(itens, key=lambda i: (i["data"], i["tipo"]))


# -- relatório por período ---------------------------------------------------------


def _duracao_dias(p: Pendencia) -> Optional[float]:
    if not p.historico:
        return None
    fim = next((h for h in reversed(p.historico) if h.etapa == "conferir"), None)
    if fim is None:
        return None
    return (fim.ts - p.historico[0].ts).total_seconds() / 86_400


def relatorio(dias: int, hoje: Optional[date] = None) -> dict[str, Any]:
    """Resumo dos últimos `dias` dias: série por dia, tipos, pendências, exposição e custo do agente.

    Achados, série, exposição e custo contam só as auditorias do período; as pendências
    mostram o retrato de agora."""
    hoje = hoje or _hoje()
    inicio = hoje - timedelta(days=dias - 1)
    auditorias = [a for a in estado.listar_auditorias() if inicio <= a.criada_em.date() <= hoje]

    serie = {inicio + timedelta(days=i): {"irregular": 0, "risco": 0, "ok": 0} for i in range(dias)}
    por_tipo = {"corrigivel": 0, "prova": 0, "passivo": 0}
    por_funcao: dict[str, float] = {}
    for aud in auditorias:
        dia = aud.criada_em.date()
        linhas = estado.obter_linhas(aud.id)
        funcoes = {l.funcionario_id: l.funcao for l in linhas}
        achados = estado.listar_achados(aud.id)
        com_achado = {(a.funcionario_id, a.linha) for a in achados if a.linha}
        serie[dia]["ok"] += sum(1 for l in linhas if (l.funcionario_id, l.linha) not in com_achado)
        for a in achados:
            if a.gravidade in ("irregular", "risco"):
                serie[dia][a.gravidade] += 1
            por_tipo[a.tipo] += 1
            if a.exposicao_rs:
                funcao = funcoes.get(a.funcionario_id) or "sem função"
                por_funcao[funcao] = por_funcao.get(funcao, 0.0) + a.exposicao_rs

    pendencias = estado.listar_pendencias()
    duracoes = [d for d in (_duracao_dias(p) for p in pendencias if p.status == "fechada") if d is not None]
    concluidas = [a for a in auditorias if a.status == "concluida"]
    passos = sum(len(estado.eventos_desde(a.id)) for a in concluidas)
    fichas = sum(max(a.n_fichas, 0) for a in concluidas)
    custo = sum(a.custo_usd or 0.0 for a in concluidas)
    return {
        "dias": dias,
        "serie": [{"data": d.isoformat(), **v} for d, v in sorted(serie.items())],
        "por_tipo": por_tipo,
        "pendencias": {
            "abertas": sum(1 for p in pendencias if p.status in ("aberta", "aguardando")),
            "fechadas": sum(1 for p in pendencias if p.status == "fechada"),
            "reabertas": sum(1 for p in pendencias if p.status == "reaberta"),
            "tempo_medio_dias": round(sum(duracoes) / len(duracoes), 2) if duracoes else 0.0,
        },
        "exposicao_total": round(sum(por_funcao.values()), 2),
        "exposicao_por_funcao": [{"funcao": f, "valor": round(v, 2)} for f, v in sorted(por_funcao.items(), key=lambda kv: -kv[1])],
        "salario_minimo": cfg_salario(),
        "custo_medio_ficha_usd": round(custo / fichas, 6) if fichas else 0.0,
        "passos_medios": round(passos / len(concluidas), 1) if concluidas else 0.0,
        "acerto": None,
    }


def cfg_salario() -> float:
    from heitor.dados.exposicao import SALARIO_MINIMO

    return SALARIO_MINIMO
