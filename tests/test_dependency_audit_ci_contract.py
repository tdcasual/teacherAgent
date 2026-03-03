from __future__ import annotations

from pathlib import Path


def test_ci_contains_dependency_audit_steps() -> None:
    text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "scripts/quality/check_frontend_prod_audit.sh" in text
    assert "scripts/quality/check_backend_dep_audit.sh" in text
