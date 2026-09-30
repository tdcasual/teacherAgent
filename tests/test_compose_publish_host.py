from pathlib import Path


def test_compose_defaults_publish_host_to_loopback() -> None:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "${PUBLISH_HOST:-127.0.0.1}:8000:8000" in text
    assert "${PUBLISH_HOST:-127.0.0.1}:3001:80" in text
    assert "${PUBLISH_HOST:-127.0.0.1}:3002:80" in text
    assert "0.0.0.0:8000:8000" not in text
