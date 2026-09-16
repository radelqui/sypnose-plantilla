# origen: rag-banking-agent@c7e5f54
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health.routes import router as health_router
from app.core.config import get_settings
from app.observability import RequestIdMiddleware, router as metrics_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = None
    yield
    app.state.engine = None


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health_router, prefix="/api/v1/health", tags=["health"])
    app.include_router(metrics_router, tags=["observability"])
    return app


app = create_app()
