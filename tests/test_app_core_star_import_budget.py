from __future__ import annotations

from pathlib import Path


def test_app_core_star_import_count_budget() -> None:
    text = Path("services/api/app_core.py").read_text(encoding="utf-8")
    count = text.count("import *")
    assert count <= 16
