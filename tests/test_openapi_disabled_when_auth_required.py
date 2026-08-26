from __future__ import annotations

import importlib
import time
from pathlib import Path

from fastapi.testclient import TestClient

from services.api.auth_service import mint_test_token
from tests.helpers.app_factory import create_test_app

_SECRET = "openapi-docs-test-secret"
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def _create_api_after_env(tmp_path: Path, **env: str):
    # docs_url is computed in create_app, not at request time.
    return create_test_app(tmp_path, env_overrides=env)


def _reload_mcp_after_env():
    import services.mcp.app as mcp_mod

    return importlib.reload(mcp_mod)


def test_auth_required_unmounts_docs_as_404_not_401(tmp_path) -> None:
    mod = _create_api_after_env(
        tmp_path,
        AUTH_REQUIRED="1",
        AUTH_TOKEN_SECRET=_SECRET,
        APP_ENV="development",
    )
    assert mod.app.docs_url is None
    assert mod.app.redoc_url is None
    assert mod.app.openapi_url is None
    with TestClient(mod.app) as client:
        for path in _DOC_PATHS:
            response = client.get(path)
            assert response.status_code == 404, f"{path} expected 404, got {response.status_code}"


def test_student_token_cannot_scrape_schema_when_auth_required(tmp_path) -> None:
    mod = _create_api_after_env(
        tmp_path,
        AUTH_REQUIRED="1",
        AUTH_TOKEN_SECRET=_SECRET,
        APP_ENV="development",
    )
    token = mint_test_token(
        {"sub": "S1", "role": "student", "exp": int(time.time()) + 3600},
        secret=_SECRET,
    )
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(mod.app) as client:
        assert client.get("/docs", headers=headers).status_code == 404
        assert client.get("/openapi.json", headers=headers).status_code == 404


def test_dev_auth_off_keeps_docs_mounted(tmp_path) -> None:
    mod = _create_api_after_env(
        tmp_path,
        AUTH_REQUIRED="0",
        APP_ENV="development",
    )
    assert mod.app.docs_url == "/docs"
    with TestClient(mod.app) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


def test_production_unmounts_docs_even_when_auth_off(tmp_path) -> None:
    mod = _create_api_after_env(
        tmp_path,
        AUTH_REQUIRED="0",
        APP_ENV="production",
        CORS_ORIGINS="http://localhost:3001",
        AUTH_TOKEN_SECRET=_SECRET,
        MASTER_KEY="test-master-key",
    )
    assert mod.app.docs_url is None
    with TestClient(mod.app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_docs_flag_is_fixed_at_create_app(tmp_path, monkeypatch) -> None:
    mod = _create_api_after_env(
        tmp_path,
        AUTH_REQUIRED="1",
        AUTH_TOKEN_SECRET=_SECRET,
        APP_ENV="development",
    )
    monkeypatch.setenv("AUTH_REQUIRED", "0")
    with TestClient(mod.app) as client:
        assert client.get("/docs").status_code == 404


def test_mcp_docs_unmounted_when_auth_required(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("MCP_API_KEY", "test-key")
    mcp_mod = _reload_mcp_after_env()
    assert mcp_mod.app.docs_url is None
    assert mcp_mod.app.redoc_url is None
    assert mcp_mod.app.openapi_url is None
    with TestClient(mcp_mod.app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_mcp_docs_unmounted_in_production(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "0")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MCP_API_KEY", "test-key")
    mcp_mod = _reload_mcp_after_env()
    assert mcp_mod.app.docs_url is None
    with TestClient(mcp_mod.app) as client:
        assert client.get("/docs").status_code == 404


def test_mcp_docs_mounted_in_dev_when_auth_off(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "0")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("MCP_API_KEY", "test-key")
    mcp_mod = _reload_mcp_after_env()
    assert mcp_mod.app.docs_url == "/docs"
    with TestClient(mcp_mod.app) as client:
        assert client.get("/docs").status_code == 200
