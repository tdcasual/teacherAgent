from pathlib import Path


def test_compose_defaults_require_auth_and_stronger_redis_boundary() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "AUTH_REQUIRED=${AUTH_REQUIRED:-1}" in text
    assert "${REDIS_PASSWORD:?REDIS_PASSWORD is required}" in text
    assert "127.0.0.1:${REDIS_PORT:-6379}:6379" in text


def test_frontend_dockerfile_runs_as_non_root() -> None:
    text = Path("frontend/Dockerfile").read_text(encoding="utf-8")
    assert "USER nginx" in text
