from __future__ import annotations

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from heitor.api.estado import estado

router = APIRouter(tags=["eventos"])


@router.get("/eventos")
async def feed(request: Request, last_event_id: Optional[str] = Header(None)) -> StreamingResponse:
    """SSE com TUDO o que o Heitor faz, de todas as auditorias: o feed da tela principal.

    Mensagens `event: evento` com um Evento (JSON); `id` = posição no log. Inclui
    as auditorias e reauditorias disparadas pelo vigia da pasta e os eventos do vigia antes de existir
    auditoria ("edicao_detectada", com auditoria_id "vigia"). Ao reconectar,
    o navegador manda Last-Event-ID e o envio continua de onde parou.
    """
    inicio = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0

    async def gerar():
        idx, ultimo_envio = inicio, time.monotonic()
        while not await request.is_disconnected():
            for ev in estado.log_desde(idx):
                yield f"id: {idx}\nevent: evento\ndata: {ev.model_dump_json()}\n\n"
                idx += 1
                ultimo_envio = time.monotonic()
            if time.monotonic() - ultimo_envio > 15:
                yield ": ping\n\n"
                ultimo_envio = time.monotonic()
            await asyncio.sleep(0.25)

    return StreamingResponse(
        gerar(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
