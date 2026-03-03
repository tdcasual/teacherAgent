from __future__ import annotations

from pathlib import Path


def test_skill_loader_uses_single_source_dir_only() -> None:
    text = Path("services/api/skills/loader.py").read_text(encoding="utf-8")
    assert ".claude" not in text
