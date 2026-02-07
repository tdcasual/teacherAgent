from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


class SessionHistoryApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = int(status_code)
        self.detail = detail


@dataclass(frozen=True)
class SessionHistoryApiDeps:
    load_student_sessions_index: Callable[[str], List[Dict[str, Any]]]
    load_teacher_sessions_index: Callable[[str], List[Dict[str, Any]]]
    paginate_session_items: Callable[[List[Dict[str, Any]], int, int], Tuple[List[Dict[str, Any]], Optional[int], int]]
    load_student_session_view_state: Callable[[str], Dict[str, Any]]
    load_teacher_session_view_state: Callable[[str], Dict[str, Any]]
    normalize_session_view_state_payload: Callable[[Dict[str, Any]], Dict[str, Any]]
    compare_iso_ts: Callable[[Optional[str], Optional[str]], int]
    now_iso_millis: Callable[[], str]
    save_student_session_view_state: Callable[[str, Dict[str, Any]], None]
    save_teacher_session_view_state: Callable[[str, Dict[str, Any]], None]
    student_session_file: Callable[[str, str], Any]
    teacher_session_file: Callable[[str, str], Any]
    load_session_messages: Callable[..., Dict[str, Any]]
    resolve_teacher_id: Callable[[Optional[str]], str]


def student_history_sessions(student_id: str, limit: int, cursor: int, *, deps: SessionHistoryApiDeps) -> Dict[str, Any]:
    student_id = (student_id or "").strip()
    if not student_id:
        raise SessionHistoryApiError(status_code=400, detail="student_id is required")
    items = deps.load_student_sessions_index(student_id)
    page, next_cursor, total = deps.paginate_session_items(items, cursor, limit)
    return {
        "ok": True,
        "student_id": student_id,
        "sessions": page,
        "next_cursor": next_cursor,
        "total": total,
    }


def student_session_view_state(student_id: str, *, deps: SessionHistoryApiDeps) -> Dict[str, Any]:
    student_id = (student_id or "").strip()
    if not student_id:
        raise SessionHistoryApiError(status_code=400, detail="student_id is required")
    state = deps.load_student_session_view_state(student_id)
    return {"ok": True, "student_id": student_id, "state": state}


def update_student_session_view_state(req: Dict[str, Any], *, deps: SessionHistoryApiDeps) -> Dict[str, Any]:
    student_id = str((req or {}).get("student_id") or "").strip()
    if not student_id:
        raise SessionHistoryApiError(status_code=400, detail="student_id is required")
    incoming = deps.normalize_session_view_state_payload((req or {}).get("state") or {})
    current = deps.load_student_session_view_state(student_id)
    if deps.compare_iso_ts(current.get("updated_at"), incoming.get("updated_at")) > 0:
        return {"ok": True, "student_id": student_id, "state": current, "stale": True}
    if not incoming.get("updated_at"):
        incoming["updated_at"] = deps.now_iso_millis()
    deps.save_student_session_view_state(student_id, incoming)
    saved = deps.load_student_session_view_state(student_id)
    return {"ok": True, "student_id": student_id, "state": saved, "stale": False}


def student_history_session(
    student_id: str,
    session_id: str,
    cursor: int,
    limit: int,
    direction: str,
    *,
    deps: SessionHistoryApiDeps,
) -> Dict[str, Any]:
    student_id = (student_id or "").strip()
    session_id = (session_id or "").strip()
    if not student_id or not session_id:
        raise SessionHistoryApiError(status_code=400, detail="student_id and session_id are required")
    path = deps.student_session_file(student_id, session_id)
    page = deps.load_session_messages(path, cursor=cursor, limit=limit, direction=direction)
    messages = page.get("messages") or []
    next_cursor = page.get("next_cursor")
    return {"ok": True, "student_id": student_id, "session_id": session_id, "messages": messages, "next_cursor": next_cursor}


def teacher_history_sessions(teacher_id: Optional[str], limit: int, cursor: int, *, deps: SessionHistoryApiDeps) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    items = deps.load_teacher_sessions_index(teacher_id_final)
    page, next_cursor, total = deps.paginate_session_items(items, cursor, limit)
    return {
        "ok": True,
        "teacher_id": teacher_id_final,
        "sessions": page,
        "next_cursor": next_cursor,
        "total": total,
    }


def teacher_session_view_state(teacher_id: Optional[str], *, deps: SessionHistoryApiDeps) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    state = deps.load_teacher_session_view_state(teacher_id_final)
    return {"ok": True, "teacher_id": teacher_id_final, "state": state}


def update_teacher_session_view_state(req: Dict[str, Any], *, deps: SessionHistoryApiDeps) -> Dict[str, Any]:
    teacher_id = str((req or {}).get("teacher_id") or "").strip()
    teacher_id_final = deps.resolve_teacher_id(teacher_id or None)
    incoming = deps.normalize_session_view_state_payload((req or {}).get("state") or {})
    current = deps.load_teacher_session_view_state(teacher_id_final)
    if deps.compare_iso_ts(current.get("updated_at"), incoming.get("updated_at")) > 0:
        return {"ok": True, "teacher_id": teacher_id_final, "state": current, "stale": True}
    if not incoming.get("updated_at"):
        incoming["updated_at"] = deps.now_iso_millis()
    deps.save_teacher_session_view_state(teacher_id_final, incoming)
    saved = deps.load_teacher_session_view_state(teacher_id_final)
    return {"ok": True, "teacher_id": teacher_id_final, "state": saved, "stale": False}


def teacher_history_session(
    session_id: str,
    teacher_id: Optional[str],
    cursor: int,
    limit: int,
    direction: str,
    *,
    deps: SessionHistoryApiDeps,
) -> Dict[str, Any]:
    teacher_id_final = deps.resolve_teacher_id(teacher_id)
    session_id = (session_id or "").strip()
    if not session_id:
        raise SessionHistoryApiError(status_code=400, detail="session_id is required")
    path = deps.teacher_session_file(teacher_id_final, session_id)
    page = deps.load_session_messages(path, cursor=cursor, limit=limit, direction=direction)
    messages = page.get("messages") or []
    next_cursor = page.get("next_cursor")
    return {"ok": True, "teacher_id": teacher_id_final, "session_id": session_id, "messages": messages, "next_cursor": next_cursor}
