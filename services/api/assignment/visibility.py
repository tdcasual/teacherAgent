from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

_log = logging.getLogger(__name__)

MISSING_OWNER_EVENT = "assignment.meta.missing_owner"
_STUDENT_READABLE = frozenset({"published", "archived"})
_STUDENT_TODAY = frozenset({"published"})
_LOGGED_MISSING_VISIBILITY: set[str] = set()


def assignment_owner_id(meta: Optional[Dict[str, Any]]) -> str:
    return str((meta or {}).get("teacher_id") or "").strip()


def log_missing_visibility_owner(*, assignment_id: str = "", teacher_id: str = "") -> None:
    key = str(assignment_id or "").strip() or str(teacher_id or "").strip()
    if key and key in _LOGGED_MISSING_VISIBILITY:
        return
    if key:
        _LOGGED_MISSING_VISIBILITY.add(key)
    payload = {"assignment_id": assignment_id, "teacher_id": teacher_id}
    _log.info("%s %s", MISSING_OWNER_EVENT, payload)
    try:
        from ..wiring import CURRENT_CORE

        core = CURRENT_CORE.get(None)
        diag = getattr(core, "diag_log", None) if core is not None else None
        if callable(diag):
            diag(MISSING_OWNER_EVENT, payload)
    except Exception:  # policy: allowed-broad-except
        _log.debug("failed to diag_log %s", MISSING_OWNER_EVENT, exc_info=True)


def effective_visibility_status(
    meta: Optional[Dict[str, Any]],
    *,
    assignment_id: str = "",
    diag_log: Optional[Callable[..., None]] = None,
) -> str:
    raw = str((meta or {}).get("visibility_status") or "").strip().lower()
    if raw:
        return raw
    owner = assignment_owner_id(meta)
    if not owner:
        return ""
    if diag_log is not None:
        diag_log(assignment_id=assignment_id, teacher_id=owner)
    else:
        log_missing_visibility_owner(assignment_id=assignment_id, teacher_id=owner)
    return "published"


def student_can_read_assignment(
    meta: Optional[Dict[str, Any]],
    *,
    for_today: bool = False,
    assignment_id: str = "",
    diag_log: Optional[Callable[..., None]] = None,
) -> bool:
    if not assignment_owner_id(meta):
        return False
    vis = effective_visibility_status(meta, assignment_id=assignment_id, diag_log=diag_log)
    allowed = _STUDENT_TODAY if for_today else _STUDENT_READABLE
    return vis in allowed
