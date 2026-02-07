from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class ChatStartDeps:
    http_error: Callable[[int, str], Exception]
    get_chat_job_id_by_request: Callable[[str], Optional[str]]
    load_chat_job: Callable[[str], Dict[str, Any]]
    detect_role_hint: Callable[[Any], str]
    resolve_student_session_id: Callable[[Optional[str], Optional[str], Optional[str]], str]
    resolve_teacher_id: Callable[[Optional[str]], str]
    resolve_chat_lane_id: Callable[..., str]
    chat_last_user_text: Callable[[Any], str]
    chat_text_fingerprint: Callable[[str], str]
    chat_job_lock: Any
    chat_recent_job_locked: Callable[[str, str], Optional[str]]
    upsert_chat_request_index: Callable[[str, str], None]
    chat_lane_load_locked: Callable[[str], Dict[str, int]]
    chat_lane_max_queue: int
    chat_request_map_set_if_absent: Callable[[str, str], bool]
    new_job_id: Callable[[], str]
    now_iso: Callable[[], str]
    write_chat_job: Callable[[str, Dict[str, Any], bool], Dict[str, Any]]
    enqueue_chat_job: Callable[[str, Optional[str]], Dict[str, Any]]
    chat_register_recent_locked: Callable[[str, str, str], None]


def start_chat_orchestration(req: Any, *, deps: ChatStartDeps) -> Dict[str, Any]:
    request_id = str(req.request_id or "").strip()
    if not request_id:
        raise deps.http_error(400, "request_id is required")

    existing_job_id = deps.get_chat_job_id_by_request(request_id)
    if existing_job_id:
        try:
            job = deps.load_chat_job(existing_job_id)
        except Exception:
            job = {"job_id": existing_job_id, "status": "queued"}
        return {"ok": True, "job_id": existing_job_id, "status": job.get("status", "queued")}

    role_hint = deps.detect_role_hint(req)
    session_id = req.session_id
    if role_hint == "student" and req.student_id and not session_id:
        session_id = deps.resolve_student_session_id(req.student_id, req.assignment_id, req.assignment_date)
    if role_hint == "teacher" and not session_id:
        session_id = "main"
    teacher_id = deps.resolve_teacher_id(req.teacher_id) if role_hint == "teacher" else ""
    lane_id = deps.resolve_chat_lane_id(
        role_hint,
        session_id=session_id,
        student_id=req.student_id,
        teacher_id=teacher_id,
        request_id=request_id,
    )

    req_payload = {
        "messages": [{"role": m.role, "content": m.content} for m in req.messages],
        "role": req.role,
        "skill_id": req.skill_id,
        "teacher_id": teacher_id if role_hint == "teacher" else req.teacher_id,
        "student_id": req.student_id,
        "assignment_id": req.assignment_id,
        "assignment_date": req.assignment_date,
        "auto_generate_assignment": req.auto_generate_assignment,
    }
    last_user_text = deps.chat_last_user_text(req_payload.get("messages"))
    fingerprint = deps.chat_text_fingerprint(last_user_text)

    with deps.chat_job_lock:
        recent_job_id = deps.chat_recent_job_locked(lane_id, fingerprint)
    if recent_job_id:
        try:
            recent_job = deps.load_chat_job(recent_job_id)
        except Exception:
            recent_job = {"job_id": recent_job_id, "status": "queued"}
        status = str(recent_job.get("status") or "queued")
        if status in {"queued", "processing"}:
            deps.upsert_chat_request_index(request_id, recent_job_id)
            return {"ok": True, "job_id": recent_job_id, "status": status, "lane_id": lane_id, "debounced": True}

    with deps.chat_job_lock:
        lane_load = deps.chat_lane_load_locked(lane_id)
    if lane_load["total"] >= deps.chat_lane_max_queue:
        raise deps.http_error(429, f"当前会话排队过多（lane={lane_load['total']}），请稍后重试")

    job_id = deps.new_job_id()
    if not deps.chat_request_map_set_if_absent(request_id, job_id):
        existing = deps.get_chat_job_id_by_request(request_id)
        if existing:
            try:
                job = deps.load_chat_job(existing)
            except Exception:
                job = {"job_id": existing, "status": "queued"}
            return {"ok": True, "job_id": existing, "status": job.get("status", "queued")}
        raise deps.http_error(409, "request_id already claimed")

    record = {
        "job_id": job_id,
        "request_id": request_id,
        "session_id": session_id or "",
        "status": "queued",
        "step": "queued",
        "progress": 0,
        "role": role_hint or req.role or "unknown",
        "skill_id": req.skill_id or "",
        "teacher_id": teacher_id,
        "student_id": req.student_id or "",
        "assignment_id": req.assignment_id or "",
        "lane_id": lane_id,
        "created_at": deps.now_iso(),
        "request": req_payload,
    }
    deps.write_chat_job(job_id, record, True)
    deps.upsert_chat_request_index(request_id, job_id)
    queue_info = deps.enqueue_chat_job(job_id, lane_id)
    with deps.chat_job_lock:
        deps.chat_register_recent_locked(lane_id, fingerprint, job_id)
    deps.write_chat_job(
        job_id,
        {
            "lane_queue_position": queue_info.get("lane_queue_position", 0),
            "lane_queue_size": queue_info.get("lane_queue_size", 0),
            "lane_active": bool(queue_info.get("lane_active")),
        },
        False,
    )
    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "lane_id": lane_id,
        "lane_queue_position": queue_info.get("lane_queue_position", 0),
        "lane_queue_size": queue_info.get("lane_queue_size", 0),
        "lane_active": bool(queue_info.get("lane_active")),
    }
