# origen: rag-banking-agent@c7e5f54
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="alive")


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    if getattr(request.app.state, "engine", None) is None:
        raise HTTPException(status_code=503, detail="engine not ready")
    return HealthResponse(status="ready")
