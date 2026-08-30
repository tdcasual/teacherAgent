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


def test_get_config_default_collection_is_school_mem(monkeypatch) -> None:
    monkeypatch.delenv("MEM0_COLLECTION", raising=False)
    monkeypatch.delenv("TENANT_ID", raising=False)
    config = get_config()
    assert config["vector_store"]["config"]["collection_name"] == "school_mem"


def test_get_config_collection_uses_env_override(monkeypatch) -> None:
    monkeypatch.setenv("MEM0_COLLECTION", "custom_mem")
    config = get_config()
    assert config["vector_store"]["config"]["collection_name"] == "custom_mem"


def test_mem0_config_default_is_not_physics_or_tenant_collection() -> None:
    text = Path("mem0_config.py").read_text(encoding="utf-8")
    assert 'os.getenv("MEM0_COLLECTION", "school_mem")' in text
    assert 'os.getenv("MEM0_COLLECTION", "physics_mem")' not in text
    assert "tenant_${" not in text
    assert "tenant_{" not in text


def test_mem0_config_does_not_auto_migrate_qdrant_collections() -> None:
    source = Path("mem0_config.py").read_text(encoding="utf-8")
    adapter = Path("services/api/mem0_adapter.py").read_text(encoding="utf-8")
    combined = source + "\n" + adapter
    assert "recreate_collection" not in combined
    assert "rename_collection" not in combined
    assert "migrate_collection" not in combined


def test_ops_docs_note_leftover_physics_mem_is_unused() -> None:
    env_example = Path(".env.production.min.example").read_text(encoding="utf-8")
    governance = Path("docs/reference/memory-governance.md").read_text(encoding="utf-8")
    assert "MEM0_COLLECTION=school_mem" in env_example
    assert "physics_mem" in env_example
    assert "school_mem" in governance
    assert "physics_mem" in governance
