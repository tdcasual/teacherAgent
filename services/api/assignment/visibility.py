from __future__ import annotations

from typing import Any, Dict, Optional

_STUDENT_READABLE = frozenset({"published", "archived"})
_STUDENT_TODAY = frozenset({"published"})


def assignment_owner_id(meta: Optional[Dict[str, Any]]) -> str:
    return str((meta or {}).get("teacher_id") or "").strip()


def effective_visibility_status(meta: Optional[Dict[str, Any]]) -> str:
    return str((meta or {}).get("visibility_status") or "").strip().lower()


def student_can_read_assignment(
    meta: Optional[Dict[str, Any]],
    *,
    for_today: bool = False,
) -> bool:
    if not assignment_owner_id(meta):
        return False
    vis = effective_visibility_status(meta)
    allowed = _STUDENT_TODAY if for_today else _STUDENT_READABLE
    return vis in allowed
