from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from heitor.api import config

_PEDACO = 1024 * 1024  # lê em pedaços de 1 MB: arquivo grande nunca entra inteiro na memória


def checar_quantidade(*listas: list) -> None:
    total = sum(len([a for a in lista if getattr(a, "filename", None)]) for lista in listas)
    if total > config.max_arquivos():
        raise HTTPException(413, f"no máximo {config.max_arquivos()} arquivos por envio")


async def salvar_upload(arquivo: UploadFile, *subpastas: str, aceitar_pdf: bool = False) -> Path:
    """Grava o upload em data/uploads/<subpastas>/<nome> e devolve o caminho.

    Recusa tipo fora da lista (415) e arquivo acima do limite (413), sem deixar nada no disco.
    aceitar_pdf: na resposta a pendência, o RH pode mandar a nota fiscal em PDF.
    """
    nome = Path(arquivo.filename or "arquivo").name  # descarta qualquer caminho vindo do cliente
    extensoes = config.EXTENSOES_UPLOAD | ({".pdf"} if aceitar_pdf else set())
    if Path(nome).suffix.lower() not in extensoes:
        aceitos = ", ".join(sorted(e.lstrip(".") for e in extensoes))
        raise HTTPException(415, f"tipo de arquivo não aceito: {nome} (aceitos: {aceitos})")
    pasta = config.PASTA_UPLOADS.joinpath(*subpastas)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / nome
    n = 1
    while destino.exists():
        destino = pasta / f"{Path(nome).stem}_{n}{Path(nome).suffix}"
        n += 1
    limite, lidos = config.max_upload_bytes(), 0
    try:
        with destino.open("wb") as f:
            while pedaco := await arquivo.read(_PEDACO):
                lidos += len(pedaco)
                if lidos > limite:
                    raise HTTPException(413, f"{nome} passa de {limite // (1024 * 1024)} MB")
                f.write(pedaco)
    except BaseException:
        destino.unlink(missing_ok=True)
        raise
    return destino
