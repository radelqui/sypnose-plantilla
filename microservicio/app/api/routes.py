# origen: rag-banking-agent@c7e5f54
from fastapi import APIRouter, HTTPException, Request

from app.api.schemas import HealthResponse

router = APIRouter(prefix="/api/v1")


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="alive")


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    if getattr(request.app.state, "engine", None) is None:
        raise HTTPException(status_code=503, detail="engine not ready")
    return HealthResponse(status="ready")
