from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

from heitor.api import integracao

router = APIRouter(prefix="/ca", tags=["ca"])


@router.get("/{numero}")
def consultar(numero: str, data: Optional[date] = None) -> Any:
    """Consulta de CA para depuração e demo. Sem `data`, usa hoje."""
    return jsonable_encoder(integracao.consulta_ca(numero, data or date.today()))
