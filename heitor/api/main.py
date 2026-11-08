"""API do Heitor.

Rodar (na raiz do repositório):
    source .venv/bin/activate
    uvicorn heitor.api.main:app --reload --port 8000

Documentação interativa: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # antes de importar o resto: config lê as variáveis de ambiente

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from heitor.api import cobranca, config, integracao, seguranca, vigia  # noqa: E402
from heitor.api.estado import estado  # noqa: E402
from heitor.api.modelos import Auditoria  # noqa: E402
from heitor.api.rotas import auditorias, ca, eventos, fichas, fontes, pendencias  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

log = logging.getLogger("heitor.main")


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Liga o vigia da pasta (gatilho 1) se houver fonte no .env. Se a fonte
    falhar ao conectar, a API sobe mesmo assim (upload continua funcionando).
    Sem vigia, a cobrança de prazos vencidos (gatilho 2) roda num relógio próprio."""
    cobranca.avisar_prazo_teste()
    try:
        v = vigia.criar_da_config()
        if v:
            v.iniciar()
    except Exception:
        log.exception("vigia não iniciou; a API segue só com upload")
        v = None
    relogio = None if v else cobranca.iniciar_relogio(config.COBRANCA_INTERVALO_S)
    yield
    if v:
        v.parar()
    if relogio:
        relogio.set()


app = FastAPI(title="Elmo", description="Auditoria de fichas de EPI", version="0.1.0", lifespan=ciclo_de_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auditorias.router)
app.include_router(pendencias.router)
app.include_router(ca.router)
app.include_router(fontes.router)
app.include_router(eventos.router)
app.include_router(fichas.router)


@app.get("/", include_in_schema=False)
def inicio() -> RedirectResponse:
    """Quem abre o link do deploy cai na documentação interativa da API."""
    return RedirectResponse("/docs")


@app.get("/health", tags=["sistema"])
def health() -> dict:
    v = vigia.vigia
    return {
        "status": "ok",
        "integracao": integracao.origem,
        "vigia": {"fonte": v.fonte.descricao, "rodando": v.status()["rodando"]} if v else None,
    }


@app.post(
    "/demo/reset", status_code=202, response_model=Auditoria, tags=["sistema"],
    dependencies=[Depends(seguranca.exigir_modo_demo), Depends(seguranca.exigir_admin)],
)
def demo_reset() -> Auditoria:
    """Apaga tudo e começa uma auditoria nova com as fichas de exemplo. O vigia
    esquece o que já leu e, na próxima verificação estável, audita a pasta inteira.
    Só com HEITOR_DEMO=1 e o token de administração (HEITOR_TOKEN_ADMIN)."""
    estado.limpar()
    if vigia.vigia:
        vigia.vigia.esquecer()
    return auditorias.criar_e_iniciar([str(config.FICHA_EXEMPLO)], disparado_por="manual")
