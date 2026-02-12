from __future__ import annotations

from typing import Any, Callable, Dict, Optional


def resolve_chat_lane_id(
    role_hint: Optional[str],
    *,
    safe_fs_id: Callable[..., str],
    resolve_teacher_id: Callable[[Optional[str]], str],
    session_id: Optional[str] = None,
    student_id: Optional[str] = None,
    teacher_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> str:
    role = str(role_hint or "unknown").strip().lower() or "unknown"
    sid = safe_fs_id(session_id or "main", prefix="session")
    if role == "student":
        student = safe_fs_id(student_id or "student", prefix="student")
        return f"student:{student}:{sid}"
    if role == "teacher":
        teacher = resolve_teacher_id(teacher_id)
        return f"teacher:{teacher}:{sid}"
    rid = safe_fs_id(request_id or "req", prefix="req")
    return f"unknown:{sid}:{rid}"


def resolve_chat_lane_id_from_job(
    job: Dict[str, Any],
    *,
    safe_fs_id: Callable[..., str],
    resolve_teacher_id: Callable[[Optional[str]], str],
) -> str:
    lane_id = str(job.get("lane_id") or "").strip()
    if lane_id:
        return lane_id
    request_raw = job.get("request")
    request: Dict[str, Any] = request_raw if isinstance(request_raw, dict) else {}
    role = str(job.get("role") or request.get("role") or "unknown")
    session_id = str(job.get("session_id") or "").strip() or None
    student_id = str(job.get("student_id") or request.get("student_id") or "").strip() or None
    teacher_id = str(job.get("teacher_id") or request.get("teacher_id") or "").strip() or None
    request_id = str(job.get("request_id") or "").strip() or None
    return resolve_chat_lane_id(
        role,
        safe_fs_id=safe_fs_id,
        resolve_teacher_id=resolve_teacher_id,
        session_id=session_id,
        student_id=student_id,
        teacher_id=teacher_id,
        request_id=request_id,
    )
