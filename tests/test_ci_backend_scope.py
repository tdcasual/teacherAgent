from __future__ import annotations

from pathlib import Path

_MYPY_GATE_PATH = Path("config/mypy_gate_files.txt")


def _load_mypy_gate_files() -> list[str]:
    files: list[str] = []
    for raw in _MYPY_GATE_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        files.append(line)
    return files


def test_ci_includes_new_backend_quality_targets() -> None:
    gated = set(_load_mypy_gate_files())
    assert "services/api/teacher_model_config_service.py" in gated
    assert "services/api/teacher_provider_registry_service.py" in gated
