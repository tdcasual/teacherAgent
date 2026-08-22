from __future__ import annotations

from pathlib import Path

import pytest

from services.api.app import _cors_origins

_TEACHER_STUDENT_ORIGINS = [
    "http://localhost:3001",
    "http://localhost:3002",
]


def test_production_unset_cors_origins_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _cors_origins()


def test_production_empty_cors_origins_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "  ,  ")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _cors_origins()


def test_production_via_env_alias_unset_cors_origins_fails_closed(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        _cors_origins()


def test_development_unset_cors_origins_uses_teacher_student_origins(monkeypatch) -> None:
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    origins, allow_credentials = _cors_origins()
    assert origins == _TEACHER_STUDENT_ORIGINS
    assert "*" not in origins
    assert allow_credentials is True


def test_explicit_cors_origins_honored_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://teacher.example,https://student.example")
    origins, allow_credentials = _cors_origins()
    assert origins == ["https://teacher.example", "https://student.example"]
    assert allow_credentials is True


def test_production_env_examples_contain_master_key_and_app_env() -> None:
    for path in (Path(".env.production.min.example"), Path(".env.example")):
        text = path.read_text(encoding="utf-8")
        assert "MASTER_KEY=" in text, f"{path} missing MASTER_KEY"
        assert "APP_ENV=production" in text, f"{path} missing APP_ENV=production"
        assert "CORS_ORIGINS=http://localhost:3001,http://localhost:3002" in text
        assert "localhost:3000" not in text


def test_compose_requires_master_key_and_defaults_app_env_cors() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "APP_ENV=${APP_ENV:-production}" in text
    assert "CORS_ORIGINS=${CORS_ORIGINS:-http://localhost:3001,http://localhost:3002}" in text
    assert "${MASTER_KEY:?MASTER_KEY is required}" in text
    assert "localhost:3000" not in text
