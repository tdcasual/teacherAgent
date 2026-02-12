"""Maintainability guardrails for worker/skill wiring."""

from pathlib import Path

_WIRING_DIR = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "wiring"
)


def _read(name: str) -> str:
    return (_WIRING_DIR / name).read_text(encoding="utf-8")


def test_worker_wiring_app_core_budget() -> None:
    source = _read("worker_wiring.py")
    assert source.count("_ac._") <= 10, "worker_wiring private app_core refs exceeded budget (10)."
    assert source.count("_ac.") <= 36, "worker_wiring app_core refs exceeded budget (36)."


def test_skill_wiring_app_core_budget() -> None:
    source = _read("skill_wiring.py")
    assert source.count("_ac._") <= 0, "skill_wiring should not depend on app_core private symbols."
    assert source.count("_ac.") <= 2, "skill_wiring app_core refs exceeded budget (2)."
