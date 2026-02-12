"""Maintainability guardrails for teacher frontend structure."""

from pathlib import Path

_TEACHER_APP_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "App.tsx"
)
_TEACHER_SESSION_RAIL_PATH = (
    Path(__file__).resolve().parent.parent
    / "frontend"
    / "apps"
    / "teacher"
    / "src"
    / "features"
    / "chat"
    / "TeacherSessionRail.tsx"
)


def test_teacher_app_line_budget() -> None:
    lines = _TEACHER_APP_PATH.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    assert line_count < 800, (
        f"teacher App.tsx is {line_count} lines (limit 800). "
        "Extract sidebar/ui-panel derivations into focused hooks."
    )


def test_teacher_session_rail_extracted() -> None:
    assert _TEACHER_SESSION_RAIL_PATH.exists(), (
        "Teacher session rail should be extracted into "
        "features/chat/TeacherSessionRail.tsx."
    )
    app_source = _TEACHER_APP_PATH.read_text(encoding="utf-8")
    assert "TeacherSessionRail" in app_source
    assert "<TeacherSessionRail" in app_source
    assert "<SessionSidebar" not in app_source, (
        "App.tsx should not render SessionSidebar directly."
    )
