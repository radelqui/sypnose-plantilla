# origen: rag-banking-agent@c7e5f54
"""Observabilidad: X-Request-Id, log JSON estructurado, métricas Prometheus."""
import json
import logging
import time
import uuid

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

logger = logging.getLogger("app.observability")

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration = time.perf_counter() - start
        response.headers["X-Request-Id"] = request_id

        path = request.url.path
        method = request.method
        status = str(response.status_code)

        if path != "/metrics":
            http_requests_total.labels(method=method, path=path, status=status).inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(duration)

        logger.info(json.dumps({
            "timestamp": time.time(),
            "level": "INFO",
            "request_id": request_id,
            "method": method,
            "path": path,
            "status": int(status),
            "duration_ms": round(duration * 1000, 2),
        }))

        return response


router = APIRouter()


@router.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
