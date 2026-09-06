from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

_log = logging.getLogger(__name__)

DRAFT_VISIBILITY_STATUS = "draft"


def generated_assignment_completion_policy(discussion_marker: str = "") -> Dict[str, Any]:
    return {
        "requires_discussion": False,
        "discussion_marker": discussion_marker,
        "requires_submission": True,
        "min_graded_total": 1,
        "best_attempt": "score_earned_then_correct_then_graded_total",
        "version": 2,
    }


def assignment_generate_script(app_root: Path) -> Path:
    return app_root / "skills" / "student-coach" / "scripts" / "select_practice.py"


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
    visibility_status: Optional[str] = None,
    teacher_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    completion_policy: Optional[Dict[str, Any]] = None,
) -> None:
    extra: Dict[str, Any] = {}
    if visibility_status:
        extra["visibility_status"] = visibility_status
    if teacher_id:
        extra["teacher_id"] = teacher_id
    if subject_id:
        extra["subject_id"] = subject_id
    if completion_policy is not None:
        extra["completion_policy"] = completion_policy
    try:
        postprocess_assignment_meta(assignment_id, due_at=due_at or None, **extra)
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        diag_log(
            "assignment.meta.postprocess_failed",
            {"assignment_id": assignment_id, "error": str(exc)[:200]},
        )
