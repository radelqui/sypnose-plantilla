# origen: rag-banking-agent@c7e5f54
"""Configuración: SOLO lee variables de entorno. Sin secretos hardcodeados.

Las variables las inyecta el pipeline CI/CD / Kubernetes Secret / Vault.
El código conoce los NOMBRES; los VALORES los pone el banco al arrancar el contenedor.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "{{SERVICE_NAME}}"
    app_database_url: str = Field(default="postgresql+asyncpg://app:app@localhost:5432/banco")
    llamaindex_database_url: str = Field(default="postgresql+asyncpg://ai_ro:ro@localhost:5432/banco")
    identity_header: str = "X-Customer-Id"


@lru_cache
def get_settings() -> Settings:
    return Settings()
