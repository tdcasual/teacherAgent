"""Maintainability guardrails for app_core compatibility facade."""

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_APP_CORE_PATH = (
    _ROOT
    / "services"
    / "api"
    / "app_core.py"
)
_APP_CORE_IO_FACADE_PATH = (
    _ROOT
    / "services"
    / "api"
    / "context_io_facade.py"
)
_BUDGET_PATH = _ROOT / "config" / "backend_quality_budget.json"


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


def test_app_core_io_wrappers_extracted() -> None:
    assert _APP_CORE_IO_FACADE_PATH.exists(), (
        "IO/upload wrappers should be extracted to services/api/context_io_facade.py."
    )
    app_source = _APP_CORE_PATH.read_text(encoding="utf-8")
    assert "from .context_io_facade import *" not in app_source
    assert "_reexport_public(_context_io_facade_module)" in app_source
    assert "def process_upload_job(" not in app_source
    assert "def process_exam_upload_job(" not in app_source
    assert "def extract_text_from_pdf(" not in app_source


def test_app_core_avoids_duplicate_explicit_reexport_blocks() -> None:
    app_source = _APP_CORE_PATH.read_text(encoding="utf-8")
    # Keep compatibility exports centralized via module-level re-export helper,
    # and avoid duplicate explicit import lists that bloat app_core.
    assert "from .teacher_memory_core import (\n" not in app_source
    assert "from .context_application_facade import (\n" not in app_source
    assert "from .context_runtime_facade import (\n" not in app_source
    assert "from .context_application_facade import *" not in app_source
    assert "from .context_runtime_facade import *" not in app_source
    assert "_reexport_public(_context_application_facade_module)" in app_source
    assert "_reexport_public(_context_runtime_facade_module)" in app_source
