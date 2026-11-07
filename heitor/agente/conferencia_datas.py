"""Confere se a data de cada entrega é possível, usando a própria ficha (sem LLM).

Ninguém recebe EPI antes de ser contratado, nem numa data que ainda não chegou. Uma entrega
"02/06/2023" para alguém admitido em 02/06/2025 é contradição: ou a leitura errou (o 5 parecia 3)
ou quem preencheu errou (falha real do processo).

NUNCA troca a data. Marca a data como em dúvida (as regras não a usam), sugere a hipótese mais
provável e manda conferir no papel. Se no papel estiver mesmo 2023, é um achado real: registro com
data impossível, que enfraquece a prova daquela entrega.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from heitor.agente.conferencia_ca import PARECIDOS

CONF_DATA_INCOERENTE = 0.4


def _br(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _anos_parecidos(ano: int) -> set[int]:
    """Troca um dos dois últimos dígitos do ano por um que se confunde à mão (2023 -> 2025, 2028...)."""
    s = str(ano)
    anos = set()
    for i in (2, 3):
        for troca in PARECIDOS.get(s[i], ""):
            anos.add(int(s[:i] + troca + s[i + 1:]))
    return anos


def conferir(data_iso: str | None, admissao_iso: str | None, hoje: date | None = None) -> dict[str, Any] | None:
    """-> None se a data é possível; senão {"motivo", "lida", "hipotese"}."""
    if not data_iso:
        return None
    hoje = hoje or date.today()
    try:
        d = date.fromisoformat(str(data_iso)[:10])
        adm = date.fromisoformat(str(admissao_iso)[:10]) if admissao_iso else None
    except ValueError:
        return None
    if adm and d < adm:
        motivo = f"entrega em {_br(d)} é anterior à admissão ({_br(adm)})"
    elif d > hoje:
        motivo = f"entrega em {_br(d)} é depois de hoje"
    else:
        return None
    candidatas = []
    for ano in _anos_parecidos(d.year):
        try:
            c = d.replace(year=ano)
        except ValueError:  # 29/02 em ano não bissexto
            continue
        if (adm is None or c >= adm) and c <= hoje:
            candidatas.append(c)
    hipotese = candidatas[0].isoformat() if len(candidatas) == 1 else None
    return {"motivo": motivo, "lida": d.isoformat(), "hipotese": hipotese}


def aplicar(linhas: list[dict[str, Any]], hoje: date | None = None) -> None:
    """Marca baixa confiança na data impossível. Não altera a data lida."""
    for l in linhas:
        r = conferir(l.get("data"), l.get("data_admissao"), hoje)
        if r:
            l.setdefault("confianca", {})["data"] = min(l.get("confianca", {}).get("data", 1.0), CONF_DATA_INCOERENTE)
            l["conferencia_data"] = r


def para_auditoria(linha: dict[str, Any]) -> dict[str, Any]:
    """Cópia da linha para as regras: data em dúvida não entra (não gera troca atrasada nem CA vencido falsos)."""
    if not linha.get("conferencia_data"):
        return linha
    return {**linha, "data": None}
