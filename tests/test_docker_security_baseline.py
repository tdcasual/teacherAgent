from pathlib import Path
import re


def test_compose_defaults_require_auth_and_stronger_redis_boundary() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "AUTH_REQUIRED=${AUTH_REQUIRED:-1}" in text
    assert "${REDIS_PASSWORD:?REDIS_PASSWORD is required}" in text
    assert "127.0.0.1:${REDIS_PORT:-6379}:6379" in text


def test_frontend_dockerfile_runs_as_non_root() -> None:
    text = Path("frontend/Dockerfile").read_text(encoding="utf-8")
    assert "USER nginx" in text


def _service_block(compose_text: str, service_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^  {re.escape(service_name)}:\n(?P<body>.*?)(?=^  [A-Za-z0-9_-]+:\n|^volumes:\n|\Z)"
    )
    match = pattern.search(compose_text)
    assert match is not None, f"service not found: {service_name}"
    return match.group("body")


def test_compose_backup_and_qdrant_have_runtime_safety_baseline() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")

    for service in ("backup_scheduler", "backup_daily_full", "backup_verify_weekly"):
        block = _service_block(text, service)
        assert "restart:" in block, f"{service} should define restart policy"
        assert "mem_limit:" in block, f"{service} should define mem_limit"
        assert "cpus:" in block, f"{service} should define cpus"
        assert "healthcheck:" in block, f"{service} should define healthcheck"

    qdrant = _service_block(text, "qdrant")
    assert "restart:" in qdrant
    assert "mem_limit:" in qdrant
    assert "cpus:" in qdrant
    assert "healthcheck:" in qdrant
