from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile

from heitor.api import config


async def salvar_upload(arquivo: UploadFile, *subpastas: str) -> Path:
    """Grava o upload em data/uploads/<subpastas>/<nome> e devolve o caminho."""
    pasta = config.PASTA_UPLOADS.joinpath(*subpastas)
    pasta.mkdir(parents=True, exist_ok=True)
    nome = Path(arquivo.filename or "arquivo").name  # descarta qualquer caminho vindo do cliente
    destino = pasta / nome
    n = 1
    while destino.exists():
        destino = pasta / f"{Path(nome).stem}_{n}{Path(nome).suffix}"
        n += 1
    destino.write_bytes(await arquivo.read())
    return destino
