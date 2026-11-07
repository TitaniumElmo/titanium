"""API do Heitor.

Rodar (na raiz do repositório):
    source .venv/bin/activate
    uvicorn heitor.api.main:app --reload --port 8000

Documentação interativa: http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv

load_dotenv()  # antes de importar o resto: config lê as variáveis de ambiente

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from heitor.api import config, integracao  # noqa: E402
from heitor.api.estado import estado  # noqa: E402
from heitor.api.modelos import Auditoria  # noqa: E402
from heitor.api.rotas import auditorias, ca, pendencias  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Heitor", description="Auditoria de fichas de EPI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auditorias.router)
app.include_router(pendencias.router)
app.include_router(ca.router)


@app.get("/health", tags=["sistema"])
def health() -> dict:
    return {"status": "ok", "integracao": integracao.origem}


@app.post("/demo/reset", status_code=202, response_model=Auditoria, tags=["sistema"])
def demo_reset() -> Auditoria:
    """Apaga tudo e começa uma auditoria nova com as fichas de exemplo."""
    estado.limpar()
    return auditorias.criar_e_iniciar([str(config.FICHA_EXEMPLO)])
