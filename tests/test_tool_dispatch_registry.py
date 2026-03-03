from __future__ import annotations

from pathlib import Path


def test_tool_dispatch_uses_registry_map_not_if_chain() -> None:
    text = Path("services/api/tool_dispatch_service.py").read_text(encoding="utf-8")
    assert text.count('if name == "') <= 3
