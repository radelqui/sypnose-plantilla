# origen: rag-banking-agent@c7e5f54
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health.routes import router as health_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = None
    yield
    app.state.engine = None


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
    app.include_router(health_router, prefix="/api/v1/health", tags=["health"])
    return app


app = create_app()
