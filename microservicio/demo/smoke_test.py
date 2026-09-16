#!/usr/bin/env python3
# origen: rag-banking-agent@c7e5f54
"""Smoke test contra servicios vivos: rag-banking-agent y como-estoy-hecho.

    BASE_RAG=http://localhost:8000 BASE_CEH=http://localhost:8010 python smoke_test.py

Variables de entorno:
    BASE_RAG  URL base de rag-banking-agent (default: http://localhost:8000)
    BASE_CEH  URL base de como-estoy-hecho  (default: http://localhost:8010)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE_RAG = os.environ.get("BASE_RAG", "http://localhost:8000").rstrip("/")
BASE_CEH = os.environ.get("BASE_CEH", "http://localhost:8010").rstrip("/")

_FAILED = 0


def _http(method: str, url: str, body: dict | None = None,
          headers: dict | None = None, timeout: int = 10) -> tuple[int, str]:
    data = json.dumps(body).encode() if body else None
    hdrs = dict(headers or {})
    if body:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)


def check(name: str, passed: bool, detail: str = "") -> None:
    global _FAILED
    tag = "OK" if passed else "FAIL"
    if not passed:
        _FAILED += 1
    line = f"  [{tag}] {name}"
    if detail:
        line += f"  ({detail})"
    print(line)


def main() -> None:
    print(f"smoke_test  BASE_RAG={BASE_RAG}  BASE_CEH={BASE_CEH}\n")

    # ── rag-banking-agent ─────────────────────────────────────────────────
    print("rag-banking-agent:")

    st, _ = _http("GET", f"{BASE_RAG}/api/v1/health/live")
    check("GET /health/live", st == 200, f"status={st}")

    st, _ = _http("GET", f"{BASE_RAG}/api/v1/health/ready")
    check("GET /health/ready", st == 200 or st == 503, f"status={st}")

    st, body = _http("POST", f"{BASE_RAG}/api/v1/consultar",
                      body={"pregunta": "Cual es la tasa del PROD-TEST-001?"},
                      headers={"X-Customer-Id": "SMOKE01"})
    check("POST /api/v1/consultar", st == 200, f"status={st}")

    print()

    # ── como-estoy-hecho ─────────────────────────────────────────────────
    print("como-estoy-hecho:")

    st, _ = _http("GET", f"{BASE_CEH}/api/v1/health/live")
    check("GET /health/live", st == 200, f"status={st}")

    st, body = _http("POST", f"{BASE_CEH}/api/v1/como-estoy-hecho",
                      body={"pregunta": "Que ficheros tiene este servicio?"},
                      headers={"X-Customer-Id": "SMOKE01"})
    check("POST /api/v1/como-estoy-hecho", st == 200, f"status={st}")

    st, body = _http("GET", f"{BASE_CEH}/como-estoy-hecho/ui/")
    check("GET /como-estoy-hecho/ui/", st == 200 and "viewport" in body.lower(),
          f"status={st}")

    print()
    if _FAILED == 0:
        print("OK smoke: all passed")
    else:
        print(f"FAIL smoke: {_FAILED} check(s) failed")
    sys.exit(0 if _FAILED == 0 else 1)


if __name__ == "__main__":
    main()
