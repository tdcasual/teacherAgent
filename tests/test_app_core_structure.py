"""Maintainability guardrails for app_core module boundaries."""

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APP_CORE_PATH = (
    _ROOT
    / "services"
    / "api"
    / "app_core.py"
)
_BUDGET_PATH = _ROOT / "config" / "backend_quality_budget.json"
_REMOVED_COMPAT_FILES = [
    _ROOT / "services" / "api" / "context_application_facade.py",
    _ROOT / "services" / "api" / "context_runtime_facade.py",
    _ROOT / "services" / "api" / "context_io_facade.py",
    _ROOT / "services" / "api" / "app_core_service_imports.py",
]


def _app_core_line_budget() -> int:
    payload = json.loads(_BUDGET_PATH.read_text(encoding="utf-8"))
    return int(payload["app_core_max_lines"])


def test_app_core_line_budget() -> None:
    lines = _APP_CORE_PATH.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    budget = _app_core_line_budget()
    assert line_count <= budget, (
        f"app_core.py is {line_count} lines (limit {budget}). "
        "Move domain wrapper functions to context application modules."
    )


def test_legacy_compat_modules_removed() -> None:
    for path in _REMOVED_COMPAT_FILES:
        assert not path.exists(), f"legacy compat file should be removed: {path}"


def test_app_core_has_no_star_imports() -> None:
    app_source = _APP_CORE_PATH.read_text(encoding="utf-8")
    assert "import *" not in app_source


def test_app_core_reexports_core_services_module() -> None:
    app_source = _APP_CORE_PATH.read_text(encoding="utf-8")
    assert "from . import core_services as _core_services_module" in app_source
    assert "_reexport_public(_core_services_module)" in app_source
    assert "context_application_facade" not in app_source
    assert "context_runtime_facade" not in app_source
    assert "context_io_facade" not in app_source
    assert "app_core_service_imports" not in app_source
