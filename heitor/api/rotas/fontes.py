from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from heitor.api import seguranca, vigia as modulo_vigia

router = APIRouter(prefix="/fontes", tags=["fontes"])


def _vigia():
    if modulo_vigia.vigia is None:
        raise HTTPException(404, "nenhuma fonte configurada (HEITOR_DRIVE_PASTA ou HEITOR_FONTE_PASTA no .env)")
    return modulo_vigia.vigia


@router.get("")
def status() -> dict:
    """O que o vigia está observando, quando olhou pela última vez e o que disparou."""
    return _vigia().status()


@router.post("/verificar", dependencies=[Depends(seguranca.exigir_admin)])
async def verificar() -> dict:
    """Força uma verificação agora (depuração). Na demo, o vigia verifica sozinho."""
    return await run_in_threadpool(_vigia().verificar)
