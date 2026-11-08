"""Qual funcionário é dono de cada foto de ficha de papel.

Decisão do time: a foto NÃO é fonte de dados (data, EPI e CA vêm da planilha);
ela só confere as assinaturas, via `conferir_e_auditar` do agente. Por isso a
foto precisa estar ligada a um funcionário que está na planilha:

1. pelo `funcionario_id` informado junto com a foto (upload), ou
2. pela matrícula no nome do arquivo: 0302.jpg, ficha_0302.jpg, fabio-0310.jpg.

A comparação ignora zeros à esquerda: o Google Sheets transforma 0302 em 302.
Foto sem dono reconhecido fica de fora (e o log diz qual foi).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

EXTENSOES_FOTO = {".jpg", ".jpeg", ".png", ".webp"}


def eh_foto(nome: str) -> bool:
    return Path(nome).suffix.lower() in EXTENSOES_FOTO


def _norm(matricula: str) -> str:
    return matricula.strip().lstrip("0") or "0"


def dono_da_foto(nome_arquivo: str, funcionarios: Iterable[str], informado: Optional[str] = None) -> Optional[str]:
    """funcionario_id (como está na planilha) dono da foto, ou None."""
    por_norma = {_norm(f): f for f in funcionarios}
    if informado and informado.strip():
        return por_norma.get(_norm(informado))
    candidatos = {por_norma[_norm(n)] for n in re.findall(r"\d+", Path(nome_arquivo).stem) if _norm(n) in por_norma}
    return candidatos.pop() if len(candidatos) == 1 else None  # nenhum ou ambíguo: não chuta
