"""Maintainability guardrails for simplified teacher frontend structure."""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APP_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "App.tsx"
_LAYOUT_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "layout" / "TeacherAppLayout.tsx"
_SETTINGS_PANEL_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "settings" / "TeacherSettingsPanel.tsx"
_MODEL_SETTINGS_PAGE_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "settings" / "ModelSettingsPage.tsx"
_TOPBAR_PATH = (
    _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "layout" / "TeacherTopbar.tsx"
)
_TOPBAR_OVERFLOW_PATH = _TOPBAR_PATH.with_name("TeacherTopbarOverflowMenu.tsx")
_TOPBAR_ADMIN_MENU_PATH = _TOPBAR_PATH.with_name("TeacherTopbarAdminMenu.tsx")
_ADMIN_SCHOOL_PANEL_PATH = (
    _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "admin" / "AdminSchoolPanel.tsx"
)
_TEACHER_ADMIN_PANEL_PATH = _TOPBAR_PATH.with_name("TeacherAdminPanel.tsx")
_CHROME_PATH = _ROOT / "frontend" / "apps" / "teacher" / "src" / "teacherAppChrome.tsx"
_MARKDOWN_PATH = _ROOT / "frontend" / "apps" / "shared" / "markdown.ts"
_STUDENT_APP_PATH = _ROOT / "frontend" / "apps" / "student" / "src" / "App.tsx"
_ROUTING_DIR = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "routing"
_PERSONA_DIR = _ROOT / "frontend" / "apps" / "teacher" / "src" / "features" / "persona"
_KATEX_CSS = "katex/dist/katex.min.css"


def _has_static_css_import(source: str, css_path: str) -> bool:
    return bool(re.search(rf"import\s+['\"]{re.escape(css_path)}['\"]", source))


def _has_dynamic_css_import(source: str, css_path: str) -> bool:
    return bool(re.search(rf"import\(\s*['\"]{re.escape(css_path)}['\"]\s*\)", source))


def test_teacher_app_line_budget() -> None:
    line_count = len(_APP_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count < 770


def test_teacher_app_layout_is_extracted() -> None:
    assert _LAYOUT_PATH.exists()
    source = _APP_PATH.read_text(encoding="utf-8")
    layout = _LAYOUT_PATH.read_text(encoding="utf-8")
    assert "TeacherAppLayout" in source
    assert "teacher-layout" not in source
    assert "TeacherTopbar" not in source
    assert "teacher-layout" in layout
    assert "teacher-mobile-shell-v2" in layout


def test_teacher_topbar_line_budget() -> None:
    line_count = len(_TOPBAR_PATH.read_text(encoding="utf-8").splitlines())
    assert line_count < 400, (
        f"TeacherTopbar.tsx is {line_count} lines (limit 400). "
        "Keep menu/overflow sections extracted."
    )


def test_admin_school_panel_is_extracted_wide_and_budgeted() -> None:
    assert _ADMIN_SCHOOL_PANEL_PATH.exists()
    source = _ADMIN_SCHOOL_PANEL_PATH.read_text(encoding="utf-8")
    drawer = _TEACHER_ADMIN_PANEL_PATH.read_text(encoding="utf-8")
    layout = _LAYOUT_PATH.read_text(encoding="utf-8")
    line_count = len(source.splitlines())
    assert line_count < 500, (
        f"AdminSchoolPanel.tsx is {line_count} lines (limit 500). "
        "Keep school admin UI out of the 344px teacher drawer."
    )
    assert "720px" in source
    assert "AdminSchoolPanel" in layout
    assert "AdminSchoolPanel" not in drawer
    assert "w-[min(344px" in drawer


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


def test_teacher_layout_lazy_loads_workbench() -> None:
    layout = _LAYOUT_PATH.read_text(encoding="utf-8")
    assert "lazy(" in layout
    assert "import('../workbench/TeacherWorkbench')" in layout
    assert "import TeacherWorkbench from '../workbench/TeacherWorkbench'" not in layout


def test_teacher_layout_lazy_loads_settings() -> None:
    layout = _LAYOUT_PATH.read_text(encoding="utf-8")
    settings = _SETTINGS_PANEL_PATH.read_text(encoding="utf-8")
    lazy_settings_panel = "import('../settings/TeacherSettingsPanel')" in layout
    lazy_model_settings = "import('./ModelSettingsPage')" in settings and "lazy(" in settings
    assert lazy_settings_panel or lazy_model_settings
    if lazy_settings_panel:
        assert "import TeacherSettingsPanel from '../settings/TeacherSettingsPanel'" not in layout


def test_katex_css_loads_with_markdown_renderer_not_chrome() -> None:
    markdown = _MARKDOWN_PATH.read_text(encoding="utf-8")
    chrome = _CHROME_PATH.read_text(encoding="utf-8")
    student_app = _STUDENT_APP_PATH.read_text(encoding="utf-8")
    assert _has_dynamic_css_import(markdown, _KATEX_CSS)
    assert not _has_static_css_import(chrome, _KATEX_CSS)
    assert not _has_static_css_import(student_app, _KATEX_CSS)
    assert not _has_static_css_import(markdown, _KATEX_CSS)
