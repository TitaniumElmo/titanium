from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from heitor.api import seguranca, vigia as modulo_vigia
from heitor.api.fontes import id_da_pasta

router = APIRouter(prefix="/fontes", tags=["fontes"])


def _vigia():
    if modulo_vigia.vigia is None:
        raise HTTPException(404, "nenhuma fonte configurada (HEITOR_DRIVE_PASTA ou HEITOR_FONTE_PASTA no .env)")
    return modulo_vigia.vigia


class NovaFonte(BaseModel):
    url: str = Field(..., description="link da pasta do Drive (drive.google.com/drive/folders/...) ou o id dela")


@router.get("")
def status() -> dict:
    """O que o vigia está observando, quando olhou pela última vez e o que disparou."""
    return _vigia().status()


@router.post("", dependencies=[Depends(seguranca.exigir_admin)])
async def trocar(corpo: NovaFonte) -> dict:
    """Passa a observar outra pasta do Drive (só o time: exige o token de administração).

    A pasta precisa estar compartilhada com a conta de serviço (Leitor); o acesso é conferido
    antes da troca e, se falhar, a pasta atual continua. Há um vigia só: a troca vale para todos
    e apaga as auditorias e pendências em memória, como o reset da demo."""
    try:
        pasta_id = id_da_pasta(corpo.url)
        fonte = await run_in_threadpool(modulo_vigia.abrir_drive, pasta_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except Exception as exc:  # rede, credencial inválida...
        raise HTTPException(502, f"não consegui falar com o Drive: {type(exc).__name__}: {exc}") from None
    novo = await run_in_threadpool(modulo_vigia.trocar_fonte, fonte)
    return novo.status()


@router.post("/padrao", dependencies=[Depends(seguranca.exigir_admin)])
async def voltar_ao_padrao() -> dict:
    """Volta à pasta do .env (HEITOR_DRIVE_PASTA ou HEITOR_FONTE_PASTA). Apaga o estado em memória."""
    fonte: Optional[object] = modulo_vigia.fonte_da_config()
    if fonte is None:
        raise HTTPException(404, "não há pasta no .env para voltar")
    novo = await run_in_threadpool(lambda: modulo_vigia.trocar_fonte(fonte, da_config=True))
    return novo.status()


@router.post("/verificar", dependencies=[Depends(seguranca.exigir_admin)])
async def verificar() -> dict:
    """Força uma verificação agora (depuração). Na demo, o vigia verifica sozinho."""
    return await run_in_threadpool(_vigia().verificar)
