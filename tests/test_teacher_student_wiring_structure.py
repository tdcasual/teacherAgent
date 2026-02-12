"""Maintainability guardrails for teacher/student wiring."""

from pathlib import Path

_WIRING_DIR = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "wiring"
)


def _read(name: str) -> str:
    return (_WIRING_DIR / name).read_text(encoding="utf-8")


def test_teacher_wiring_app_core_budget() -> None:
    source = _read("teacher_wiring.py")
    assert source.count("_ac._") <= 0, "teacher_wiring should not depend on app_core private symbols."
    assert source.count("_ac.") <= 24, "teacher_wiring app_core references exceeded budget (24)."


def test_student_wiring_app_core_budget() -> None:
    source = _read("student_wiring.py")
    assert source.count("_ac._") <= 0, "student_wiring should not depend on app_core private symbols."
    assert source.count("_ac.") <= 24, "student_wiring app_core references exceeded budget (24)."
