# origen: rag-banking-agent@c7e5f54
"""Identidad del cliente: viene SIEMPRE de la pasarela del banco, NUNCA del prompt.

El banco autentica al usuario (OAuth2 / AD) en su API gateway y propaga la identidad al
microservicio en una cabecera. Aquí solo la leemos y validamos. Sin identidad -> 401.
"""
from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings


def _valid_customer_id(value: str) -> bool:
    return bool(value) and value.isalnum() and len(value) <= 32


def get_customer_id(request: Request, settings: Settings = Depends(get_settings)) -> str:
    raw = (request.headers.get(settings.identity_header) or "").strip()
    if not _valid_customer_id(raw):
        raise HTTPException(status_code=401, detail="identidad no presente o inválida")
    return raw
