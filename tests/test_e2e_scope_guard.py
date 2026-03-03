from __future__ import annotations

from pathlib import Path


def test_removed_e2e_specs_absent() -> None:
    root = Path(__file__).resolve().parent.parent
    assert not (root / "frontend/e2e/student-persona-cards.spec.ts").exists()
    assert not (root / "frontend/e2e/teacher-routing-provider.spec.ts").exists()
