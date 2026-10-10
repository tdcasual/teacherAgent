from pathlib import Path


def test_compose_defaults_publish_host_to_loopback() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "${PUBLISH_HOST:-127.0.0.1}:8000:8000" in text
    assert "${PUBLISH_HOST:-127.0.0.1}:3001:80" in text
    assert "${PUBLISH_HOST:-127.0.0.1}:3002:80" in text
    assert "0.0.0.0:8000:8000" not in text


def test_api_depends_on_redis_healthy() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    api_block = text.split("\n  api:\n", 1)[1].split("\n  mcp:", 1)[0]
    assert "depends_on:" in api_block
    assert "redis:" in api_block
    assert "condition: service_healthy" in api_block
