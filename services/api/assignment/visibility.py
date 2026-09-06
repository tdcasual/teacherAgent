from __future__ import annotations

from typing import Any, Dict, Optional

_STUDENT_READABLE = frozenset({"published", "archived"})
_STUDENT_TODAY = frozenset({"published"})


def assignment_owner_id(meta: Optional[Dict[str, Any]]) -> str:
    return str((meta or {}).get("teacher_id") or "").strip()


def effective_visibility_status(meta: Optional[Dict[str, Any]]) -> str:
    return str((meta or {}).get("visibility_status") or "").strip().lower()


def snapshot_student_ids(meta: Optional[Dict[str, Any]]) -> list[str]:
    raw = (meta or {}).get("expected_students")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


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


_STUDENT_META_OMIT = frozenset({"expected_students", "student_ids"})


def public_student_assignment_detail(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    meta = out.get("meta")
    if isinstance(meta, dict):
        out["meta"] = {key: value for key, value in meta.items() if key not in _STUDENT_META_OMIT}
    return out
