import importlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.health.routes import router as health_router

log = logging.getLogger(__name__)

_INFRA_PACKAGES = {"api", "core", "security"}


def _autodiscover(application: FastAPI, app_dir: Path) -> None:
    for pkg in sorted(app_dir.iterdir()):
        if not pkg.is_dir() or pkg.name.startswith("_") or pkg.name in _INFRA_PACKAGES:
            continue
        mod_path = f"app.{pkg.name}.router"
        try:
            mod = importlib.import_module(mod_path)
            domain_router = getattr(mod, "router", None)
            if domain_router is not None:
                application.include_router(domain_router)
                log.info("auto-mount router: %s", mod_path)
        except ImportError:
            pass
        static_dir = pkg / "static"
        if static_dir.is_dir():
            url_name = pkg.name.replace("_", "-")
            application.mount(
                f"/{url_name}/ui",
                StaticFiles(directory=str(static_dir), html=True),
                name=f"{pkg.name}-ui",
            )
            log.info("auto-mount static: /%s/ui", url_name)


app = FastAPI(title="{{SERVICE_NAME}}")
app.include_router(health_router, prefix="/api/v1/health", tags=["health"])
app.include_router(health_router, prefix="/health", tags=["health"], include_in_schema=False)
_autodiscover(app, Path(__file__).resolve().parent)
