from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

_log = logging.getLogger(__name__)


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
    append_student_session_message: Callable[..., None]
    update_student_session_index: Callable[..., None]
    append_teacher_session_message: Callable[..., None]
    update_teacher_session_index: Callable[..., None]
    parse_date_str: Callable[[Optional[str]], str]


def start_chat_orchestration(req: Any, *, deps: ChatStartDeps) -> Dict[str, Any]:
    request_id = str(req.request_id or "").strip()
    if not request_id:
        raise deps.http_error(400, "request_id is required")

    legacy_agent_id = str(getattr(req, "agent_id", "") or "").strip()
    if legacy_agent_id:
        raise deps.http_error(400, "agent_id is no longer supported; use skill_id")

    existing_job_id = deps.get_chat_job_id_by_request(request_id)
    if existing_job_id:
        try:
            job = deps.load_chat_job(existing_job_id)
        except Exception:
            _log.warning("load_chat_job failed for %s, fabricating queued stub", existing_job_id, exc_info=True)
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
    fingerprint_seed = "|".join(
        [
            str(req_payload.get("skill_id") or "").strip(),
            str(req_payload.get("assignment_id") or "").strip(),
            str(last_user_text or ""),
        ]
    )
    fingerprint = deps.chat_text_fingerprint(fingerprint_seed)

    with deps.chat_job_lock:
        recent_job_id = deps.chat_recent_job_locked(lane_id, fingerprint)
    if recent_job_id:
        try:
            recent_job = deps.load_chat_job(recent_job_id)
        except Exception:
            _log.warning("load_chat_job failed for dedup %s, fabricating queued stub", recent_job_id, exc_info=True)
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
                _log.warning("load_chat_job failed for race %s, fabricating queued stub", existing, exc_info=True)
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

    if last_user_text:
        try:
            if role_hint == "student" and req.student_id and session_id:
                deps.append_student_session_message(
                    req.student_id,
                    session_id,
                    "user",
                    last_user_text,
                    meta={"request_id": request_id, "source": "start_prewrite"},
                )
                deps.update_student_session_index(
                    req.student_id,
                    session_id,
                    req.assignment_id,
                    deps.parse_date_str(req.assignment_date),
                    preview=last_user_text,
                    message_increment=1,
                )
                deps.write_chat_job(job_id, {"user_turn_persisted": True}, False)
            elif role_hint == "teacher" and session_id:
                deps.append_teacher_session_message(
                    teacher_id,
                    session_id,
                    "user",
                    last_user_text,
                    meta={"request_id": request_id, "source": "start_prewrite"},
                )
                deps.update_teacher_session_index(
                    teacher_id,
                    session_id,
                    preview=last_user_text,
                    message_increment=1,
                )
                deps.write_chat_job(job_id, {"user_turn_persisted": True}, False)
        except Exception as exc:
            detail = str(exc)[:200]
            deps.write_chat_job(
                job_id,
                {"status": "failed", "error": "history_prewrite_failed", "error_detail": detail},
                False,
            )
            return {
                "ok": True,
                "job_id": job_id,
                "status": "failed",
                "lane_id": lane_id,
            }

    try:
        queue_info = deps.enqueue_chat_job(job_id, lane_id)
    except Exception as exc:
        detail = str(exc)[:200]
        _log.error("enqueue_chat_job failed for %s: %s", job_id, detail, exc_info=True)
        deps.write_chat_job(
            job_id,
            {"status": "failed", "error": "enqueue_failed", "error_detail": detail},
            False,
        )
        return {
            "ok": True,
            "job_id": job_id,
            "status": "failed",
            "lane_id": lane_id,
        }
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
