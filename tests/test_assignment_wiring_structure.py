"""Maintainability guardrails for assignment wiring."""

from pathlib import Path

_ASSIGNMENT_WIRING_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "wiring"
    / "assignment_wiring.py"
)


def test_assignment_wiring_app_core_private_refs_budget() -> None:
    source = _ASSIGNMENT_WIRING_PATH.read_text(encoding="utf-8")
    private_ref_count = source.count("_ac._")
    assert private_ref_count <= 10, (
        f"assignment_wiring.py has {private_ref_count} app_core private refs (limit 10). "
        "Prefer direct service impl imports + local deps builders over _ac._internal symbols."
    )


def test_assignment_wiring_app_core_ref_budget() -> None:
    source = _ASSIGNMENT_WIRING_PATH.read_text(encoding="utf-8")
    ref_count = source.count("_ac.")
    assert ref_count <= 130, (
        f"assignment_wiring.py has {ref_count} app_core refs (limit 130). "
        "Keep wiring focused and reduce app_core symbol fan-out."
    )
