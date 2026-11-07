"""Confere se o CA lido na foto combina com o EPI escrito na mesma linha (base CAEPI, sem LLM).

Um dígito manuscrito lido errado (4 por 7 ou 9) produz um CA que não existe ou que é de
outro equipamento: 25637 é "vestimenta tipo camisa", e a ficha diz capacete (o certo é 29637).

NUNCA troca o CA lido. Uma ficha pode ter erro de verdade (luva com CA de óculos, dígitos
trocados), e corrigir sozinho esconderia a falha. O CA que não confere fica com baixa
confiança e com sugestões, e a auditoria pede confirmação ao RH.
"""

from __future__ import annotations

import os
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any

CAMINHO_CAEPI = Path(os.getenv("HEITOR_CAEPI", Path(__file__).resolve().parents[2] / "data" / "tgg_export_caepi.txt"))
CONF_NAO_CONFERE = 0.4

FAMILIAS: dict[str, tuple[str, ...]] = {
    "capacete": ("capacete",),
    "calcado": ("botina", "bota", "calcado", "sapato", "botin"),
    "luva": ("luva",),
    "oculos": ("oculos",),
    "auditivo": ("protetor auditivo", "protetor auricular", "auricular", "auditivo", "plug", "abafador"),
    "respiratorio": ("respirador", "mascara", "pff", "semifacial", "peca facial"),
    "vestimenta": ("vestimenta", "avental", "camisa", "calca", "jaqueta", "macacao", "capuz"),
    "queda": ("cinturao", "cinto", "talabarte", "trava queda", "trava-queda"),
    "facial": ("protetor facial", "viseira"),
}

# Dígitos que se confundem na letra à mão.
PARECIDOS = {"0": "68", "1": "7", "2": "7", "3": "58", "4": "79", "5": "369", "6": "508", "7": "1249", "8": "306", "9": "457"}


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def familia(texto: str | None) -> str | None:
    t = _norm(texto or "")
    for fam, palavras in FAMILIAS.items():
        if any(p in t for p in palavras):
            return fam
    return None


@lru_cache(maxsize=1)
def _indice() -> dict[str, str]:
    """número do CA -> equipamento (coluna 8 da base CAEPI)."""
    indice: dict[str, str] = {}
    if not CAMINHO_CAEPI.exists():
        return indice
    with CAMINHO_CAEPI.open(encoding="utf-8", errors="replace") as f:
        next(f, None)
        for linha in f:
            p = linha.split("|", 8)
            if len(p) > 7 and p[0].strip():
                indice.setdefault(p[0].strip().lstrip("0"), p[7].strip())
    return indice


def base_disponivel() -> bool:
    return bool(_indice())


def _candidatos(ca: str) -> set[str]:
    c: set[str] = set()
    for i, d in enumerate(ca):
        for troca in PARECIDOS.get(d, ""):
            c.add(ca[:i] + troca + ca[i + 1:])
        if i + 1 < len(ca) and ca[i] != ca[i + 1]:
            c.add(ca[:i] + ca[i + 1] + ca[i] + ca[i + 2:])  # dígitos vizinhos trocados
    c.discard(ca)
    return c


def conferir(ca: str | None, epi: str | None) -> dict[str, Any]:
    """-> {"confere": bool | None, "equipamento": str | None, "sugestoes": [...], "motivo": str}

    confere None = não dá para dizer (sem CA, sem base ou EPI de família desconhecida).
    """
    idx = _indice()
    if not ca or not idx:
        return {"confere": None, "equipamento": None, "sugestoes": [], "motivo": "sem CA ou sem base"}
    fam_epi = familia(epi)
    equip = idx.get(ca)
    fam_ca = familia(equip)
    if equip and (fam_epi is None or fam_ca is None or fam_ca == fam_epi):
        return {"confere": True, "equipamento": equip, "sugestoes": [], "motivo": "CA existe e combina com o EPI"}
    sugestoes = sorted(c for c in _candidatos(ca) if c in idx and fam_epi and familia(idx[c]) == fam_epi)
    motivo = (f"CA {ca} não existe na base" if not equip
              else f"CA {ca} é de '{equip}', mas a ficha diz '{epi}'")
    return {"confere": False, "equipamento": equip, "sugestoes": sugestoes, "motivo": motivo}


def aplicar(linhas: list[dict[str, Any]]) -> None:
    """Marca baixa confiança no CA que não confere. Não altera o número lido."""
    for l in linhas:
        r = conferir(l.get("ca"), l.get("epi"))
        if r["confere"] is False:
            l.setdefault("confianca", {})["ca"] = min(l.get("confianca", {}).get("ca", 1.0), CONF_NAO_CONFERE)
            l["conferencia_ca"] = r  # campo interno: vai para a evidência do achado
