from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import SERVICE_NAME

router = APIRouter()


@router.get("/")
async def health():
    return {"status": "alive", "service": SERVICE_NAME}


@router.get("/live")
async def liveness():
    return {"status": "alive", "service": SERVICE_NAME}


@router.get("/ready")
async def readiness():
    return JSONResponse(content={"status": "ready", "service": SERVICE_NAME})
