"""Proteção mínima da API para o deploy público (os jurados testam pelo link).

- Rotas de ADMINISTRAÇÃO (apagar tudo, forçar o vigia) exigem o token de
  HEITOR_TOKEN_ADMIN, no cabeçalho `Authorization: Bearer <token>` ou
  `X-Heitor-Token: <token>`. Sem HEITOR_TOKEN_ADMIN (máquina de quem desenvolve),
  ficam liberadas.
- `POST /demo/reset` só existe com HEITOR_DEMO=1 (no deploy, fica desligado
  até o time precisar).
- Rotas que os jurados usam (subir planilha, responder pendência) ficam abertas,
  mas com limite de quantidade, tamanho e tipo de arquivo (heitor/api/uploads.py).
"""

from __future__ import annotations

import hmac
import logging
from typing import Optional

from fastapi import Header, HTTPException

from heitor.api import config

log = logging.getLogger("heitor.seguranca")


def exigir_admin(
    authorization: Optional[str] = Header(None),
    x_heitor_token: Optional[str] = Header(None),
) -> None:
    esperado = config.token_admin()
    if not esperado:
        return  # sem token configurado: ambiente de desenvolvimento
    enviado = x_heitor_token
    if not enviado and authorization and authorization.lower().startswith("bearer "):
        enviado = authorization[7:].strip()
    if not enviado or not hmac.compare_digest(enviado.encode(), esperado.encode()):
        raise HTTPException(401, "rota de administração: envie o token (Authorization: Bearer <token>)")


def exigir_modo_demo() -> None:
    if not config.modo_demo():
        raise HTTPException(404, "não disponível (ligue HEITOR_DEMO=1)")
