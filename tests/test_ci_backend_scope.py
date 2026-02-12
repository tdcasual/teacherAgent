from __future__ import annotations

from pathlib import Path


def test_ci_includes_new_backend_quality_targets() -> None:
    yml = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "services/api/llm_routing.py" in yml
    assert "services/api/teacher_provider_registry_service.py" in yml
