from pathlib import Path


def test_ruff_per_file_ignores_for_compat_facades() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.ruff.lint.per-file-ignores]" in text
    assert '"services/api/app_core.py"' in text
    assert '"services/api/teacher_memory_core.py"' in text
    assert "F405" in text
