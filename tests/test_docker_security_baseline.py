import re
from pathlib import Path


def test_compose_defaults_require_auth_and_stronger_redis_boundary() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "AUTH_REQUIRED=${AUTH_REQUIRED:-1}" in text
    assert "${REDIS_PASSWORD:?REDIS_PASSWORD is required}" in text
    assert "127.0.0.1:${REDIS_PORT:-6379}:6379" in text


def test_compose_redis_uses_noeviction() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    redis_block = _service_block(text, "redis")
    assert "--maxmemory-policy noeviction" in redis_block
    assert "allkeys-lru" not in redis_block
    assert "allkeys-lru" not in text


def test_compose_api_fail_closed_app_env_cors_and_master_key() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    api_block = _service_block(text, "api")
    assert "APP_ENV=${APP_ENV:-production}" in api_block
    assert "CORS_ORIGINS=${CORS_ORIGINS:-http://localhost:3001,http://localhost:3002}" in api_block
    assert "${MASTER_KEY:?MASTER_KEY is required}" in api_block


def test_compose_api_mounts_config_for_auth_secret_persistence() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    api_block = _service_block(text, "api")
    assert "./config:/app/config" in api_block


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
    assert "127.0.0.1:6333:6333" in qdrant
    image_match = re.search(r"image:\s*(\S+)", qdrant)
    assert image_match is not None, "qdrant service should pin an image"
    image_ref = image_match.group(1)
    assert ":" in image_ref, f"qdrant image must include an explicit tag, got {image_ref}"
    assert not image_ref.endswith(":latest"), f"qdrant image must not use :latest, got {image_ref}"


def test_compose_mcp_binds_loopback_and_requires_key() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    mcp_block = _service_block(text, "mcp")
    assert "127.0.0.1:9000:9000" in mcp_block
    assert "${MCP_API_KEY:?MCP_API_KEY is required}" in mcp_block
    assert '"9000:9000"' not in mcp_block
    dockerfile = Path("services/mcp/Dockerfile").read_text(encoding="utf-8")
    assert '"--host", "0.0.0.0"' in dockerfile
    assert '"--port", "9000"' in dockerfile


def test_env_examples_have_nonempty_mcp_api_key_placeholder() -> None:
    for path in (".env.production.min.example", ".env.example"):
        text = Path(path).read_text(encoding="utf-8")
        match = re.search(r"^MCP_API_KEY=(.*)$", text, re.M)
        assert match is not None, f"{path} must set MCP_API_KEY"
        assert match.group(1).strip(), f"{path} MCP_API_KEY must be a non-empty placeholder"


def test_compose_backup_services_use_minimum_required_mounts() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    required_mounts = (
        "./scripts/backup:/workspace/scripts/backup:ro",
        "./data:/workspace/data:ro",
        "./uploads:/workspace/uploads:ro",
        "./output:/workspace/output",
    )
    for service in ("backup_scheduler", "backup_daily_full", "backup_verify_weekly"):
        block = _service_block(text, service)
        assert "./:/workspace" not in block
        for mount in required_mounts:
            assert mount in block, f"{service} missing mount: {mount}"
