import sys
import types

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.main import _autodiscover


def test_autodiscover_mounts_domain_router(tmp_path):
    domain_dir = tmp_path / "demo_domain"
    domain_dir.mkdir()
    (domain_dir / "__init__.py").write_text("")

    fake_router = APIRouter()

    @fake_router.get("/api/v1/demo")
    def demo():
        return {"ok": True}

    fake_mod = types.ModuleType("app.demo_domain.router")
    fake_mod.router = fake_router

    test_app = FastAPI()
    orig = sys.modules.copy()
    sys.modules["app.demo_domain"] = types.ModuleType("app.demo_domain")
    sys.modules["app.demo_domain.router"] = fake_mod
    try:
        _autodiscover(test_app, tmp_path)
    finally:
        sys.modules.pop("app.demo_domain.router", None)
        sys.modules.pop("app.demo_domain", None)

    client = TestClient(test_app)
    r = client.get("/api/v1/demo")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_autodiscover_serves_static_if_exists(tmp_path):
    domain_dir = tmp_path / "my_domain"
    domain_dir.mkdir()
    (domain_dir / "__init__.py").write_text("")
    static_dir = domain_dir / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<h1>react placeholder</h1>")

    test_app = FastAPI()
    _autodiscover(test_app, tmp_path)

    client = TestClient(test_app)
    r = client.get("/my-domain/ui/")
    assert r.status_code == 200
    assert "react" in r.text


def test_autodiscover_skips_infra_packages(tmp_path):
    for name in ("api", "core", "security"):
        d = tmp_path / name
        d.mkdir()
        (d / "__init__.py").write_text("")

    test_app = FastAPI()
    before = len(test_app.routes)
    _autodiscover(test_app, tmp_path)
    assert len(test_app.routes) == before


def test_autodiscover_skips_private_dirs(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "_internal").mkdir()

    test_app = FastAPI()
    before = len(test_app.routes)
    _autodiscover(test_app, tmp_path)
    assert len(test_app.routes) == before
