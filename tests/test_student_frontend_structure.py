"""Maintainability guardrails for student frontend structure."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SELECTORS_PATH = (
    _ROOT
    / "frontend"
    / "apps"
    / "student"
    / "src"
    / "features"
    / "chat"
    / "studentUiSelectors.ts"
)
_SESSION_MANAGER_PATH = (
    _ROOT
    / "frontend"
    / "apps"
    / "student"
    / "src"
    / "hooks"
    / "useSessionManager.ts"
)
_STUDENT_APP_PATH = (
    _ROOT
    / "frontend"
    / "apps"
    / "student"
    / "src"
    / "App.tsx"
)


def test_student_selector_layer_exists() -> None:
    assert _SELECTORS_PATH.exists(), (
        "Student UI selector layer should exist at "
        "features/chat/studentUiSelectors.ts."
    )


def test_session_manager_consumes_selector_layer() -> None:
    source = _SESSION_MANAGER_PATH.read_text(encoding="utf-8")
    assert "selectVisibleSessions" in source
    assert "selectGroupedSessions" in source
    assert "selectArchiveDialogMeta" in source
    assert "sessionGroupFromIso" not in source, (
        "Grouping logic should live in selector layer, not useSessionManager."
    )


def test_student_app_composer_hint_uses_selector_layer() -> None:
    source = _STUDENT_APP_PATH.read_text(encoding="utf-8")
    assert "selectComposerHint" in source
