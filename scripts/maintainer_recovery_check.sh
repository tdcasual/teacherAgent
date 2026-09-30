#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
python - <<'PY'
from pathlib import Path
handoff = Path("docs/how-to/maintainer-handoff.md").read_text(encoding="utf-8")
for needle in ("AUTH_REQUIRED", "unset", "PYTEST_CURRENT_TEST", "BEGIN IMMEDIATE", "orphan"):
    assert needle in handoff, f"handoff missing {needle}"
compose = Path("docker-compose.yml").read_text(encoding="utf-8")
assert "${PUBLISH_HOST:-127.0.0.1}:8000:8000" in compose
ci = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
assert "--cov-fail-under=85" in ci
assert "maintainer_recovery_check.sh" in ci
print("maintainer_recovery_check ok")
PY
