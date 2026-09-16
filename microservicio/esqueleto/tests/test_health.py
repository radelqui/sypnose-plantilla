# origen: rag-banking-agent@c7e5f54
from httpx import ASGITransport, AsyncClient

from tests.conftest import make_app


async def test_liveness(client):
    r = await client.get("/api/v1/health/live")
    assert r.status_code == 200 and r.json() == {"status": "alive"}


async def test_readiness_ok(client):
    assert (await client.get("/api/v1/health/ready")).status_code == 200


async def test_readiness_503_when_engine_missing():
    app = make_app(engine=None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/health/ready")).status_code == 503
