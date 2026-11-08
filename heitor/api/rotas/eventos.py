from __future__ import annotations

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from heitor.api.estado import estado

router = APIRouter(tags=["eventos"])


def _continuar_de(last_event_id: Optional[str], geracao: int) -> int:
    """Posição de onde continuar o feed. O id é "<geração>.<posição>": se a geração mudou (reset da
    demo, troca de pasta), o log recomeçou e a leitura volta ao início. Id em outro formato: do início."""
    g, _, posicao = (last_event_id or "").partition(".")
    if g.isdigit() and posicao.isdigit() and int(g) == geracao:
        return int(posicao) + 1
    return 0


@router.get("/eventos")
async def feed(request: Request, last_event_id: Optional[str] = Header(None)) -> StreamingResponse:
    """SSE com TUDO o que o Heitor faz, de todas as auditorias: o feed da tela principal.

    Mensagens `event: evento` com um Evento (JSON); `id` = "<geração>.<posição no log>". Inclui
    as auditorias e reauditorias disparadas pelo vigia da pasta e os eventos do vigia antes de existir
    auditoria ("edicao_detectada", com auditoria_id "vigia"). Ao reconectar,
    o navegador manda Last-Event-ID e o envio continua de onde parou.
    """
    geracao, inicio = estado.geracao(), _continuar_de(last_event_id, estado.geracao())

    async def gerar():
        nonlocal geracao
        idx, ultimo_envio = inicio, time.monotonic()
        while not await request.is_disconnected():
            atual = estado.geracao()
            if atual != geracao:  # reset ou troca de pasta com a conexão aberta: o log recomeçou
                geracao, idx = atual, 0
                yield f'event: reset\ndata: {{"geracao": {atual}}}\n\n'
            for ev in estado.log_desde(idx):
                yield f"id: {geracao}.{idx}\nevent: evento\ndata: {ev.model_dump_json()}\n\n"
                idx += 1
                ultimo_envio = time.monotonic()
            if time.monotonic() - ultimo_envio > 15:
                yield ": ping\n\n"
                ultimo_envio = time.monotonic()
            await asyncio.sleep(0.25)

    return StreamingResponse(
        gerar(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
