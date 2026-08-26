from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SERVICE_PATH = _ROOT / "services" / "api" / "chat_job_processing_service.py"
_PACKAGE_DIR = _ROOT / "services" / "api" / "chat_job_processing"
_TIMELINE_PATH = _PACKAGE_DIR / "timeline.py"
_FACADE_LINE_LIMIT = 1100
_EXTRACTED_DEFS = (
    "_persist_execution_timeline",
    "_BufferedRuntimeEventWriter",
    "_compute_reply_with_runtime_events",
)


def _top_level_def_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
    return names


def test_chat_job_processing_package_timeline_modules_exist() -> None:
    assert (_PACKAGE_DIR / "__init__.py").is_file()
    assert _TIMELINE_PATH.is_file()
    timeline_names = _top_level_def_names(_TIMELINE_PATH)
    assert "_persist_execution_timeline" in timeline_names
    assert "_BufferedRuntimeEventWriter" in timeline_names


def test_chat_job_processing_facade_line_budget() -> None:
    lines = _SERVICE_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) < _FACADE_LINE_LIMIT, (
        f"chat_job_processing_service.py is {len(lines)} lines "
        f"(limit {_FACADE_LINE_LIMIT}). Extract timeline/pipeline helpers."
    )


def test_timeline_helpers_are_not_defined_on_facade() -> None:
    facade_names = _top_level_def_names(_SERVICE_PATH)
    defined = [name for name in _EXTRACTED_DEFS if name in facade_names]
    assert not defined, (
        "timeline helpers must live in services/api/chat_job_processing/, "
        f"not as definitions on the facade: {defined}"
    )


def test_public_chat_job_processing_api_stays_on_facade() -> None:
    from services.api.chat_job_processing_service import (
        compute_chat_reply_sync,
        process_chat_job,
    )

    assert callable(process_chat_job)
    assert callable(compute_chat_reply_sync)
