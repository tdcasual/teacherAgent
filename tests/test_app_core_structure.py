"""Maintainability guardrails for app_core compatibility facade."""

from pathlib import Path

_APP_CORE_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "app_core.py"
)
_APP_CORE_IO_FACADE_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "api"
    / "context_io_facade.py"
)


def test_app_core_line_budget() -> None:
    lines = _APP_CORE_PATH.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    assert line_count < 900, (
        f"app_core.py is {line_count} lines (limit 900). "
        "Move domain wrapper functions to context application modules."
    )


def test_app_core_io_wrappers_extracted() -> None:
    assert _APP_CORE_IO_FACADE_PATH.exists(), (
        "IO/upload wrappers should be extracted to services/api/context_io_facade.py."
    )
    app_source = _APP_CORE_PATH.read_text(encoding="utf-8")
    assert "from .context_io_facade import *" in app_source
    assert "def process_upload_job(" not in app_source
    assert "def process_exam_upload_job(" not in app_source
    assert "def extract_text_from_pdf(" not in app_source


def test_app_core_avoids_duplicate_explicit_reexport_blocks() -> None:
    app_source = _APP_CORE_PATH.read_text(encoding="utf-8")
    # Keep star-based compatibility exports, but avoid duplicate explicit import lists
    # that bloat app_core without adding behavior.
    assert "from .teacher_memory_core import (\n" not in app_source
    assert "from .context_application_facade import (\n" not in app_source
    assert "from .context_runtime_facade import (\n" not in app_source
