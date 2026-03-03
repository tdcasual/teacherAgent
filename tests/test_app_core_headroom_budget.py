from __future__ import annotations

from pathlib import Path


def test_app_core_line_budget_has_headroom() -> None:
    lines = len(Path("services/api/app_core.py").read_text(encoding="utf-8").splitlines())
    assert lines <= 260, f"app_core.py still too large: {lines}"
