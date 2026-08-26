from __future__ import annotations

from pathlib import Path

from mem0_config import PROJECT_ROOT, get_config

MACHINE_LOCAL_MARKER = "/Users/lvxiaoer"


def test_mem0_config_source_has_no_machine_local_default_path() -> None:
    text = Path("mem0_config.py").read_text(encoding="utf-8")
    assert MACHINE_LOCAL_MARKER not in text


def test_readme_has_no_machine_local_path_and_uses_python_313() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert MACHINE_LOCAL_MARKER not in text
    assert "python3.13" in text
    assert "3.13" in text
    assert "pyproject.toml" in text


def test_get_config_default_qdrant_path_is_repo_relative(monkeypatch) -> None:
    monkeypatch.delenv("QDRANT_PATH", raising=False)
    config = get_config()
    qdrant_path = config["vector_store"]["config"]["path"]
    assert MACHINE_LOCAL_MARKER not in qdrant_path
    assert Path(qdrant_path) == PROJECT_ROOT / ".qdrant"
