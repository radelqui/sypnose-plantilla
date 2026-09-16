# origen: rag-banking-agent@c7e5f54
import json
import logging
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def obs_client():
    app = create_app()
    app.state.engine = object()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── X-Request-Id ──────────────────────────────────────────────────────────


async def test_response_has_request_id(obs_client):
    r = await obs_client.get("/api/v1/health/live")
    assert r.status_code == 200
    rid = r.headers.get("x-request-id")
    assert rid is not None
    uuid.UUID(rid)


async def test_request_id_forwarded_if_provided(obs_client):
    custom_id = "custom-req-id-42"
    r = await obs_client.get("/api/v1/health/live", headers={"X-Request-Id": custom_id})
    assert r.headers["x-request-id"] == custom_id


# ── Log JSON estructurado ────────────────────────────────────────────────


async def test_logs_are_json_structured(obs_client, caplog):
    with caplog.at_level(logging.INFO, logger="app.observability"):
        await obs_client.get("/api/v1/health/live")
    records = [r for r in caplog.records if r.name == "app.observability"]
    assert len(records) >= 1
    data = json.loads(records[-1].message)
    assert "timestamp" in data
    assert "level" in data
    assert "request_id" in data


# ── GET /metrics ──────────────────────────────────────────────────────────


async def test_metrics_returns_200(obs_client):
    await obs_client.get("/api/v1/health/live")
    r = await obs_client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
