import re
from pathlib import Path

_COMPOSE_REQUIRED = re.compile(r"\$\{([A-Z][A-Z0-9_]+):\?")
_ENV_KEY = re.compile(r"^([A-Z][A-Z0-9_]+)=", re.M)
_ENV_ASSIGNMENT = re.compile(r"^([A-Z][A-Z0-9_]+)=(.*)$", re.M)
_EXAMPLE_PATHS = (".env.production.min.example", ".env.example")
_REQUIRED_SECRETS = ("REDIS_PASSWORD", "MCP_API_KEY", "AUTH_TOKEN_SECRET", "MASTER_KEY")
_REMAINING_PLACEHOLDERS = {
    "REDIS_PASSWORD": "change_me",
    "AUTH_TOKEN_SECRET": "change_me",
    "AUTH_REQUIRED": "1",
    "RQ_SCAN_PENDING_ON_START": "1",
    "MASTER_KEY": "change_me",
    "APP_ENV": "production",
    "CORS_ORIGINS": "http://localhost:3001,http://localhost:3002",
}


def _example_keys(path: str) -> set[str]:
    text = Path(path).read_text(encoding="utf-8")
    return set(_ENV_KEY.findall(text))


def _example_assignments(path: str) -> dict[str, str]:
    text = Path(path).read_text(encoding="utf-8")
    return {key: value for key, value in _ENV_ASSIGNMENT.findall(text)}


def _compose_fail_closed_keys() -> set[str]:
    text = Path("docker-compose.yml").read_text(encoding="utf-8")
    return set(_COMPOSE_REQUIRED.findall(text))


def _readme_five_minute_section() -> str:
    text = Path("README.md").read_text(encoding="utf-8")
    _, rest = text.split("## 5 分钟快速开始", 1)
    return rest.split("\n## ", 1)[0]


def test_production_env_examples_contain_compose_fail_closed_keys() -> None:
    required = _compose_fail_closed_keys()
    assert "MCP_API_KEY" in required
    assert "REDIS_PASSWORD" in required
    assert "MASTER_KEY" in required
    for path in _EXAMPLE_PATHS:
        missing = required - _example_keys(path)
        assert not missing, f"{path} missing compose fail-closed keys: {sorted(missing)}"


def test_production_env_examples_have_remaining_required_placeholders() -> None:
    for path in _EXAMPLE_PATHS:
        assignments = _example_assignments(path)
        for key, expected in _REMAINING_PLACEHOLDERS.items():
            assert assignments.get(key) == expected, f"{path} {key} must be {expected!r}"


def test_production_min_example_includes_app_env_cors_master_key() -> None:
    keys = _example_keys(".env.production.min.example")
    missing = {"APP_ENV", "CORS_ORIGINS", "MASTER_KEY"} - keys
    assert not missing, f".env.production.min.example missing W1-P5 keys: {sorted(missing)}"


def test_production_redis_url_includes_password_placeholder_when_compose_requires_it() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    if "REDIS_PASSWORD" not in compose:
        return
    for path in _EXAMPLE_PATHS:
        assignments = _example_assignments(path)
        redis_url = assignments.get("REDIS_URL", "")
        assert "REDIS_PASSWORD" in redis_url or ":change_me@" in redis_url, (
            f"{path} REDIS_URL must include a password placeholder"
        )


def test_readme_five_minute_start_mentions_required_secrets() -> None:
    section = _readme_five_minute_section()
    for secret in _REQUIRED_SECRETS:
        assert secret in section, f"5-minute start must name {secret}"
    assert "change_me" in section
    assert ".env.production.min.example" in section
    assert "docker compose up" in section
    assert "填" in section or "Fill" in section or "replace" in section.lower()
