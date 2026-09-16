from fastapi import FastAPI

from app.api.health.routes import router as health_router

app = FastAPI(title="{{SERVICE_NAME}}")
app.include_router(health_router, prefix="/api/v1/health", tags=["health"])
