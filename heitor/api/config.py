"""Configuração da API, lida das variáveis de ambiente (ver .env.example)."""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

PASTA_UPLOADS = Path(os.getenv("HEITOR_UPLOADS", RAIZ / "data" / "uploads"))
PASTA_EXEMPLOS = RAIZ / "heitor" / "exemplos"
FICHA_EXEMPLO = PASTA_EXEMPLOS / "fichas_exemplo.csv"

# "1" força os stubs mesmo que o código real da Sofia/Gustavo exista.
FORCAR_STUBS = os.getenv("HEITOR_STUBS") == "1"

# Pausa entre eventos do agente falso, para o log ao vivo ficar visível na tela.
STUB_ATRASO_S = float(os.getenv("HEITOR_STUB_ATRASO", "0.3"))
