# origen: rag-banking-agent@c7e5f54
"""Seguridad transversal: identidad, PII y guardrails.

- Identidad: viene SIEMPRE de la pasarela del banco, NUNCA del prompt.
- PII: enmascara IBAN, DNI, tarjeta y email en logs y streaming.
- Guardrails: detección básica de prompt injection y sanitización.
"""
import re
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings

# ── Identidad ──────────────────────────────────────────────────────────────


def _valid_customer_id(value: str) -> bool:
    return bool(value) and value.isalnum() and len(value) <= 32


def get_customer_id(request: Request, settings: Settings = Depends(get_settings)) -> str:
    raw = (request.headers.get(settings.identity_header) or "").strip()
    if not _valid_customer_id(raw):
        raise HTTPException(status_code=401, detail="identidad no presente o inválida")
    return raw


# ── PII ────────────────────────────────────────────────────────────────────

IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b")
DNI_RE = re.compile(r"\b\d{8}[A-Z]\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def mask_pii(text: str) -> str:
    text = IBAN_RE.sub("[IBAN]", text)
    text = DNI_RE.sub("[DNI]", text)
    text = CARD_RE.sub("[TARJETA]", text)
    text = EMAIL_RE.sub("[EMAIL]", text)
    return text


_SAFE_BOUNDARY = re.compile(r"(?:\.\s|\n)")
_MAX_ENTITY = 48


class StreamMasker:
    """Enmascara PII sobre un flujo de tokens sin que las entidades se escapen partidas."""

    def __init__(self, max_buffer: int = 400):
        self._buf = ""
        self._max_buffer = max_buffer

    def feed(self, token: str) -> str:
        self._buf += token
        cut = self._safe_cut()
        if cut <= 0:
            return ""
        out, self._buf = self._buf[:cut], self._buf[cut:]
        return mask_pii(out)

    def flush(self) -> str:
        out, self._buf = self._buf, ""
        return mask_pii(out)

    def _safe_cut(self) -> int:
        last = None
        for m in _SAFE_BOUNDARY.finditer(self._buf):
            last = m.end()
        if last:
            return last
        if len(self._buf) > self._max_buffer:
            limit = len(self._buf) - _MAX_ENTITY
            space = self._buf.rfind(" ", 0, limit)
            return space + 1 if space > 0 else 0
        return 0


# ── Guardrails ─────────────────────────────────────────────────────────────

INJECTION_PATTERNS = [
    r"ignor(a|e)\s+(todas\s+)?(las\s+)?instrucciones",
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"\bsystem\s*prompt\b",
    r"\b(drop|delete|truncate|alter|update|insert)\s+(table|from|into)\b",
    r"\bact\s+as\s+(root|admin|dba)\b",
    r"revela(r)?\s+(la\s+)?contraseña",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

MAX_PROMPT_CHARS = 4000


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str | None = None
    sanitized: str = ""


def check_prompt(text: str) -> GuardrailResult:
    if not text or not text.strip():
        return GuardrailResult(False, "empty_prompt")
    if len(text) > MAX_PROMPT_CHARS:
        return GuardrailResult(False, "prompt_too_long")
    for pattern in _COMPILED:
        if pattern.search(text):
            return GuardrailResult(False, f"injection_pattern:{pattern.pattern}")
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return GuardrailResult(True, None, sanitized)
