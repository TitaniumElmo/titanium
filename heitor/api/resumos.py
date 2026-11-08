"""Uma linha em português para cada saída de ferramenta no log de eventos.

Funções puras e determinísticas (sem LLM, sem relógio): o texto depende só do
evento. Um dict ferramenta -> formatador; ferramenta sem formatador usa o padrão.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from heitor.contrato import Evento

Formatador = Callable[[dict, dict, datetime], str]

_DESTINO = {"tecnico": "o técnico", "rh": "o RH"}


def _dia(iso: Any) -> str:
    try:
        return f"{date.fromisoformat(str(iso)[:10]):%d/%m/%Y}"
    except ValueError:
        return str(iso)


def _n(qtd: int, singular: str, plural: str) -> str:
    return f"{qtd} {singular if qtd == 1 else plural}"


def _criar_pendencia(entrada: dict, saida: dict, ts: datetime) -> str:
    if "erro" in saida:
        return f"pendência não criada: {saida['erro']}"
    destino = _DESTINO.get(saida.get("destino"), saida.get("destino") or "o destino")
    try:
        dias = (date.fromisoformat(str(saida["prazo"])[:10]) - ts.date()).days
        prazo = f"prazo {_n(dias, 'dia', 'dias')}"
    except (KeyError, ValueError):
        prazo = "sem prazo"
    return f"pendência {saida.get('id') or saida.get('pendencia_id', '?')} para {destino}, {prazo}"


def _fechar_pendencia(entrada: dict, saida: dict, ts: datetime) -> str:
    return f"pendência {saida.get('id') or entrada.get('pendencia_id', '?')} {saida.get('status', 'atualizada')}"


def _manter_pendencia(entrada: dict, saida: dict, ts: datetime) -> str:
    return f"pendência {entrada.get('pendencia_id', '?')} mantida: {saida.get('motivo', 'sem motivo')}"


def _audita_linha(entrada: dict, saida: dict, ts: datetime) -> str:
    por_linha = saida.get("por_linha")
    if not isinstance(por_linha, dict):
        return "linhas auditadas"
    com = sum(1 for v in por_linha.values() if v != "ok")
    return f"{_n(len(por_linha), 'linha auditada', 'linhas auditadas')}: {_n(com, 'com achado', 'com achados')}, {len(por_linha) - com} ok"


def _lista_de_achados(saida: dict) -> list:
    achados = saida.get("achados")
    return achados if isinstance(achados, list) else []


def _audita_funcionario(entrada: dict, saida: dict, ts: datetime) -> str:
    achados = _lista_de_achados(saida)
    return f"ficha completa com {_n(len(achados), 'achado', 'achados')}" if achados else "ficha completa sem achados"


def _auditar_ficha(entrada: dict, saida: dict, ts: datetime) -> str:
    total = len(_lista_de_achados(saida)) or len(saida.get("por_linha") or {})
    return f"ficha auditada: {_n(total, 'item', 'itens')}" if total else "ficha auditada sem achados"


def _consulta_ca(entrada: dict, saida: dict, ts: datetime) -> str:
    numero = saida.get("numero") or entrada.get("numero", "?")
    if saida.get("encontrado") is False:
        return f"CA {numero} não encontrado na base"
    situacao = str(saida.get("situacao", "")).upper()
    if situacao in ("CANCELADO", "SUSPENSO"):
        return f"CA {numero} {situacao.lower()} na base"
    validade = _dia(saida.get("validade"))
    if saida.get("valido_na_data"):
        return f"CA {numero} válido na data, com validade até {validade}"
    return f"CA {numero} vencido na data (validade {validade})"


def _buscar_ca_proximo(entrada: dict, saida: dict, ts: datetime) -> str:
    sugestoes = saida.get("sugestoes") or []
    return f"{_n(len(sugestoes), 'CA parecido', 'CAs parecidos')} para confirmar" if sugestoes else "nenhum CA parecido"


def _exigencia_funcao(entrada: dict, saida: dict, ts: datetime) -> str:
    funcao = saida.get("funcao") or "?"
    if saida.get("encontrada") is False:
        return f"função {funcao} fora da tabela"
    return f"função {funcao} exige {_n(len(saida.get('epis') or []), 'EPI', 'EPIs')}"


def _calcula_exposicao(entrada: dict, saida: dict, ts: datetime) -> str:
    total = float(saida.get("total_brl") or 0)
    valor = f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"exposição potencial máxima de R$ {valor} em {_n(len(saida.get('funcionarios') or []), 'funcionário', 'funcionários')}"


def _gerar_relatorio(entrada: dict, saida: dict, ts: datetime) -> str:
    return f"relatório com {_n(int(saida.get('itens') or 0), 'item', 'itens')}"


def _reauditar(entrada: dict, saida: dict, ts: datetime) -> str:
    return f"reauditoria da pendência {entrada.get('pendencia_id', '?')}: {saida.get('status', 'concluída')}"


def _cobrar_atraso(entrada: dict, saida: dict, ts: datetime) -> str:
    texto = f"cobrança {saida.get('cobrancas', '?')} da pendência {saida.get('pendencia_id', '?')}"
    return texto + "; escalada ao coordenador" if saida.get("escalada") else texto


def _edicao_detectada(entrada: dict, saida: dict, ts: datetime) -> str:
    segundos = float(saida.get("aguardando_segundos") or 0)
    onde = saida.get("arquivo") or saida.get("fonte") or "a planilha"
    return f"edição detectada em {onde}; aguardando {segundos:g} s antes de auditar"


FORMATADORES: dict[str, Formatador] = {
    "criar_pendencia": _criar_pendencia,
    "fechar_pendencia": _fechar_pendencia,
    "manter_pendencia": _manter_pendencia,
    "audita_linha": _audita_linha,
    "audita_funcionario": _audita_funcionario,
    "auditar_ficha": _auditar_ficha,
    "consulta_ca": _consulta_ca,
    "buscar_ca_proximo": _buscar_ca_proximo,
    "exigencia_funcao": _exigencia_funcao,
    "calcula_exposicao": _calcula_exposicao,
    "gerar_relatorio": _gerar_relatorio,
    "reauditar": _reauditar,
    "cobrar_atraso": _cobrar_atraso,
    "edicao_detectada": _edicao_detectada,
}


def resumo_da_ferramenta(ferramenta: str, entrada: dict, saida: Any, ts: datetime) -> str:
    dados = saida if isinstance(saida, dict) else {}
    formatador = FORMATADORES.get(ferramenta)
    if formatador is not None:
        try:
            return formatador(entrada or {}, dados, ts)
        except Exception:
            pass
    return f"{ferramenta} executada"


def com_resumo(evento: Evento) -> Evento:
    """Devolve o evento com saida.resumo. Saída que não é dict vai em saida.conteudo."""
    if evento.tipo != "ferramenta" or not evento.ferramenta:
        return evento
    if isinstance(evento.saida, dict):
        if "resumo" in evento.saida:
            return evento
        saida = {**evento.saida, "resumo": resumo_da_ferramenta(evento.ferramenta, evento.entrada, evento.saida, evento.ts)}
    else:
        resumo = resumo_da_ferramenta(evento.ferramenta, evento.entrada, evento.saida, evento.ts)
        saida = {"conteudo": evento.saida, "resumo": resumo}
    return evento.model_copy(update={"saida": saida})
