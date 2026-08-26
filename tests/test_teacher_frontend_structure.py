"""Maintainability guardrails for simplified teacher frontend structure."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APP_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "App.tsx"
_SETTINGS_PANEL_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "settings" / "TeacherSettingsPanel.tsx"
_MODEL_SETTINGS_PAGE_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "settings" / "ModelSettingsPage.tsx"
_TOPBAR_PATH = (
    _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "layout" / "TeacherTopbar.tsx"
)
_TOPBAR_OVERFLOW_PATH = _TOPBAR_PATH.with_name("TeacherTopbarOverflowMenu.tsx")
_TOPBAR_ADMIN_MENU_PATH = _TOPBAR_PATH.with_name("TeacherTopbarAdminMenu.tsx")
_ROUTING_DIR = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "routing"
_PERSONA_DIR = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "persona"


def test_teacher_app_line_budget() -> None:
    line_count = len(_APP_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count < 900


def test_teacher_topbar_line_budget() -> None:
    line_count = len(_TOPBAR_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count < 400, (
        f"TeacherTopbar.tsx is {line_count} lines (limit 400). "
        "Keep menu/overflow sections extracted."
    )


def test_teacher_topbar_menu_overflow_modules_exist() -> None:
    assert _TOPBAR_OVERFLOW_PATH.exists()
    assert _TOPBAR_ADMIN_MENU_PATH.exists()
    source = _TOPBAR_PATH.read_text(encoding="utf-8")
    assert "TeacherTopbarOverflowMenu" in source
    assert "TeacherTopbarAdminMenu" in source


def test_teacher_app_no_persona_or_routing_imports() -> None:
    source = _APP_PATH.read_text(encoding="utf-8")
    assert "features/routing" not in source
    assert "features/persona" not in source
    assert "TeacherPersonaManager" not in source


def test_model_settings_page_exists_and_is_used() -> None:
    assert _MODEL_SETTINGS_PAGE_PATH.exists()
    source = _SETTINGS_PANEL_PATH.read_text(encoding="utf-8")
    assert "ModelSettingsPage" in source


def test_removed_feature_directories_are_gone() -> None:
    assert not _ROUTING_DIR.exists()
    assert not _PERSONA_DIR.exists()


def test_teacher_css_has_no_routing_tokens() -> None:
    css = (
        _ROOT
        / "frontend"
        / "apps"
        / "teacher"
        / "src"
        / "tailwind.css"
    ).read_text(encoding="utf-8")
    assert ".routing-" not in css
