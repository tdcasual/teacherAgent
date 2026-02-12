"""Maintainability guardrails for misc wiring."""

from pathlib import Path

_MISC_WIRING_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "wiring"
    / "misc_wiring.py"
)


def test_misc_wiring_app_core_private_refs_budget() -> None:
    source = _MISC_WIRING_PATH.read_text(encoding="utf-8")
    private_ref_count = source.count("_ac._")
    assert private_ref_count <= 6, (
        f"misc_wiring.py has {private_ref_count} app_core private refs (limit 6). "
        "Prefer direct service imports and dedicated deps builders."
    )


def test_misc_wiring_app_core_ref_budget() -> None:
    source = _MISC_WIRING_PATH.read_text(encoding="utf-8")
    ref_count = source.count("_ac.")
    assert ref_count <= 85, (
        f"misc_wiring.py has {ref_count} app_core refs (limit 85). "
        "Keep misc wiring fan-out within budget."
    )
