"""Maintainability guardrails for chat wiring."""

from pathlib import Path

_CHAT_WIRING_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "wiring"
    / "chat_wiring.py"
)


def test_chat_wiring_app_core_private_refs_budget() -> None:
    source = _CHAT_WIRING_PATH.read_text(encoding="utf-8")
    private_ref_count = source.count("_ac._")
    assert private_ref_count <= 20, (
        f"chat_wiring.py has {private_ref_count} app_core private refs (limit 20). "
        "Prefer direct module deps over app_core private access."
    )


def test_chat_wiring_app_core_ref_budget() -> None:
    source = _CHAT_WIRING_PATH.read_text(encoding="utf-8")
    ref_count = source.count("_ac.")
    assert ref_count <= 110, (
        f"chat_wiring.py has {ref_count} app_core refs (limit 110). "
        "Keep wiring layers narrow and avoid app_core fan-out drift."
    )
