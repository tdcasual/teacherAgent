from __future__ import annotations

import re
from pathlib import Path


def test_coverage_references_existing_sources_only() -> None:
    root = Path(__file__).resolve().parent.parent
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")

    referenced: list[str] = []
    for rel in re.findall(r'"(services/api/[^"]+\.py)"', text):
        referenced.append(rel)

    missing = [rel for rel in referenced if not (root / rel).exists()]
    assert missing == [], f"coverage references missing files: {missing}"


def test_coverage_does_not_omit_rq_worker() -> None:
    root = Path(__file__).resolve().parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "services/api/workers/rq_worker.py" not in text
