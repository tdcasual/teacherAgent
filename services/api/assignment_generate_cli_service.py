from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

_log = logging.getLogger(__name__)


def assignment_generate_script(app_root: Path) -> Path:
    return app_root / "skills" / "physics-student-coach" / "scripts" / "select_practice.py"


def append_assignment_generate_options(
    cmd: list[str],
    options: Iterable[tuple[str, Any]],
) -> None:
    for flag, value in options:
        if value:
            cmd += [flag, str(value)]


def append_assignment_generate_flag(cmd: list[str], *, flag: str, enabled: bool) -> None:
    if enabled:
        cmd += [flag]


def try_postprocess_assignment_meta(
    *,
    assignment_id: str,
    due_at: Optional[str],
    postprocess_assignment_meta: Callable[..., Any],
    diag_log: Callable[[str, Optional[Dict[str, Any]]], None],
) -> None:
    try:
        postprocess_assignment_meta(assignment_id, due_at=due_at or None)
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        diag_log(
            "assignment.meta.postprocess_failed",
            {"assignment_id": assignment_id, "error": str(exc)[:200]},
        )
