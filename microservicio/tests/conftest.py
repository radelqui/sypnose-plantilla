# origen: rag-banking-agent@c7e5f54
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import router


def make_app(engine=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.engine = engine
    return app


@pytest.fixture
async def client():
    app = make_app(engine=object())
    headers = {"X-Customer-Id": "C123"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers) as c:
        yield c
