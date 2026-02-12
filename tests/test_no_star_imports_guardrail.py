from __future__ import annotations

from pathlib import Path

ALLOWED = {
    "services/api/app_core.py",
    "services/api/teacher_memory_core.py",
}


def test_no_star_imports_outside_allowlist() -> None:
    offenders: list[str] = []
    for path in Path("services/api").rglob("*.py"):
        rel = str(path).replace("\\", "/")
        if rel in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "import *" in text:
            offenders.append(rel)
    assert offenders == [], f"star imports not allowed: {offenders}"
