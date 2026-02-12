"""Maintainability guardrails for exam wiring."""

from pathlib import Path

_EXAM_WIRING_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "wiring"
    / "exam_wiring.py"
)


def test_exam_wiring_app_core_private_refs_budget() -> None:
    source = _EXAM_WIRING_PATH.read_text(encoding="utf-8")
    private_ref_count = source.count("_ac._")
    assert private_ref_count <= 8, (
        f"exam_wiring.py has {private_ref_count} app_core private refs (limit 8). "
        "Use direct service imports when wiring exam domain dependencies."
    )


def test_exam_wiring_app_core_ref_budget() -> None:
    source = _EXAM_WIRING_PATH.read_text(encoding="utf-8")
    ref_count = source.count("_ac.")
    assert ref_count <= 90, (
        f"exam_wiring.py has {ref_count} app_core refs (limit 90). "
        "Keep exam wiring fan-out narrow."
    )
