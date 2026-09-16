# origen: rag-banking-agent@c7e5f54
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
