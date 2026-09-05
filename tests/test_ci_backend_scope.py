from __future__ import annotations

from pathlib import Path


def _ruff_check_paths(text: str) -> list[str]:
    start = text.find("python -m ruff check")
    assert start != -1
    end = text.find("\n      - name:", start)
    blob = text[start:] if end == -1 else text[start:end]
    tokens = blob.replace("\\", " ").split()
    assert tokens[:4] == ["python", "-m", "ruff", "check"]
    return tokens[4:]


def test_ci_ruff_gates_services_api_tree() -> None:
    yml = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    paths = _ruff_check_paths(yml)
    assert "services/api" in paths
    assert "services/mcp/app.py" in paths
    assert "tests/test_ci_workflow_quality.py" in paths
    assert "tests/test_ci_backend_scope.py" in paths
