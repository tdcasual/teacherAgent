from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

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
    resolve_chat_attachment_context: Callable[..., Dict[str, Any]]
    append_chat_event: Callable[[str, str, Dict[str, Any]], Dict[str, Any]] = (
        lambda _job_id, _event_type, _payload: {}
    )


@dataclass(frozen=True)
class _StartContext:
    role_hint: str
    session_id: Optional[str]
    teacher_id: str
    lane_id: str
    req_payload: Dict[str, Any]
    last_user_text: str
    fingerprint: str
    attachment_warnings: List[str]


def _extract_attachment_ids(req: Any) -> List[str]:
    raw_items = getattr(req, "attachments", None) or []
    if not isinstance(raw_items, list):
        return []
    ids: List[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if isinstance(item, dict):
            raw_id = item.get("attachment_id")
        else:
            raw_id = getattr(item, "attachment_id", "")
        value = str(raw_id or "").strip().lower()
        if not value or value in seen:
            continue
        ids.append(value)
        seen.add(value)
    return ids


def _load_job_or_stub(job_id: str, *, mode: str, deps: ChatStartDeps) -> Dict[str, Any]:
    try:
        return deps.load_chat_job(job_id)
    except Exception:
        if mode == "dedup":
            _log.warning(
                "load_chat_job failed for dedup %s, fabricating queued stub",
                job_id,
                exc_info=True,
            )
        elif mode == "race":
            _log.warning(
                "load_chat_job failed for race %s, fabricating queued stub",
                job_id,
                exc_info=True,
            )
        else:
            _log.warning(
                "load_chat_job failed for %s, fabricating queued stub",
                job_id,
                exc_info=True,
            )
        return {"job_id": job_id, "status": "queued"}


def _validate_start_request(req: Any, deps: ChatStartDeps) -> str:
    request_id = str(req.request_id or "").strip()
    if not request_id:
        raise deps.http_error(400, "request_id is required")
    legacy_agent_id = str(getattr(req, "agent_id", "") or "").strip()
    if legacy_agent_id:
        raise deps.http_error(400, "agent_id is no longer supported; use skill_id")
    return request_id


def _resolve_start_context(req: Any, request_id: str, deps: ChatStartDeps) -> _StartContext:
    role_hint = deps.detect_role_hint(req)
    session_id = req.session_id
    if role_hint == "student" and req.student_id and not session_id:
        session_id = deps.resolve_student_session_id(
            req.student_id, req.assignment_id, req.assignment_date
        )
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
        "persona_id": req.persona_id,
        "teacher_id": teacher_id if role_hint == "teacher" else req.teacher_id,
        "student_id": req.student_id,
        "assignment_id": req.assignment_id,
        "assignment_date": req.assignment_date,
        "auto_generate_assignment": req.auto_generate_assignment,
    }
    attachment_ids = _extract_attachment_ids(req)
    attachment_payload = deps.resolve_chat_attachment_context(
        role=role_hint,
        teacher_id=teacher_id if role_hint == "teacher" else req.teacher_id,
        student_id=req.student_id,
        session_id=session_id,
        attachment_ids=attachment_ids,
    )
    attachment_context = str(attachment_payload.get("attachment_context") or "").strip()
    attachment_warnings = [
        str(item).strip()
        for item in (attachment_payload.get("warnings") or [])
        if str(item).strip()
    ]
    req_payload["attachments"] = [{"attachment_id": aid} for aid in attachment_ids]
    req_payload["attachment_context"] = attachment_context
    last_user_text = deps.chat_last_user_text(req_payload.get("messages"))
    fingerprint_seed = "|".join(
        [
            str(req_payload.get("skill_id") or "").strip(),
            str(req_payload.get("persona_id") or "").strip(),
            str(req_payload.get("assignment_id") or "").strip(),
            str(last_user_text or ""),
            ",".join(attachment_ids),
        ]
    )
    fingerprint = deps.chat_text_fingerprint(fingerprint_seed)
    return _StartContext(
        role_hint=role_hint,
        session_id=session_id,
        teacher_id=teacher_id,
        lane_id=lane_id,
        req_payload=req_payload,
        last_user_text=last_user_text,
        fingerprint=fingerprint,
        attachment_warnings=attachment_warnings,
    )


def _lookup_existing_request(request_id: str, deps: ChatStartDeps) -> Optional[Dict[str, Any]]:
    existing_job_id = deps.get_chat_job_id_by_request(request_id)
    if not existing_job_id:
        return None
    job = _load_job_or_stub(existing_job_id, mode="existing", deps=deps)
    return {
        "ok": True,
        "job_id": existing_job_id,
        "status": job.get("status", "queued"),
    }


def _lookup_recent_dedup(
    request_id: str, context: _StartContext, deps: ChatStartDeps
) -> Optional[Dict[str, Any]]:
    with deps.chat_job_lock:
        recent_job_id = deps.chat_recent_job_locked(context.lane_id, context.fingerprint)
    if not recent_job_id:
        return None
    recent_job = _load_job_or_stub(recent_job_id, mode="dedup", deps=deps)
    status = str(recent_job.get("status") or "queued")
    if status in {"queued", "processing"}:
        deps.upsert_chat_request_index(request_id, recent_job_id)
        return {
            "ok": True,
            "job_id": recent_job_id,
            "status": status,
            "lane_id": context.lane_id,
            "debounced": True,
        }
    return None


def _ensure_lane_capacity(context: _StartContext, deps: ChatStartDeps) -> None:
    with deps.chat_job_lock:
        lane_load = deps.chat_lane_load_locked(context.lane_id)
    if lane_load["total"] >= deps.chat_lane_max_queue:
        raise deps.http_error(429, f"当前会话排队过多（lane={lane_load['total']}），请稍后重试")


def _claim_request_id_or_return_existing(
    request_id: str, job_id: str, deps: ChatStartDeps
) -> Optional[Dict[str, Any]]:
    if deps.chat_request_map_set_if_absent(request_id, job_id):
        return None
    existing = deps.get_chat_job_id_by_request(request_id)
    if existing:
        job = _load_job_or_stub(existing, mode="race", deps=deps)
        return {"ok": True, "job_id": existing, "status": job.get("status", "queued")}
    raise deps.http_error(409, "request_id already claimed")


def _build_job_record(
    job_id: str, request_id: str, req: Any, context: _StartContext, deps: ChatStartDeps
) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "request_id": request_id,
        "session_id": context.session_id or "",
        "status": "queued",
        "step": "queued",
        "progress": 0,
        "role": context.role_hint or req.role or "unknown",
        "skill_id": req.skill_id or "",
        "persona_id": req.persona_id or "",
        "teacher_id": context.teacher_id,
        "student_id": req.student_id or "",
        "assignment_id": req.assignment_id or "",
        "lane_id": context.lane_id,
        "created_at": deps.now_iso(),
        "request": context.req_payload,
    }


def _persist_user_turn_prewrite(
    job_id: str, request_id: str, req: Any, context: _StartContext, deps: ChatStartDeps
) -> Optional[Dict[str, Any]]:
    if not context.last_user_text:
        return None
    try:
        if context.role_hint == "student" and req.student_id and context.session_id:
            deps.append_student_session_message(
                req.student_id,
                context.session_id,
                "user",
                context.last_user_text,
                meta={"request_id": request_id, "source": "start_prewrite"},
            )
            deps.update_student_session_index(
                req.student_id,
                context.session_id,
                req.assignment_id,
                deps.parse_date_str(req.assignment_date),
                preview=context.last_user_text,
                message_increment=1,
            )
            deps.write_chat_job(job_id, {"user_turn_persisted": True}, False)
        elif context.role_hint == "teacher" and context.session_id:
            deps.append_teacher_session_message(
                context.teacher_id,
                context.session_id,
                "user",
                context.last_user_text,
                meta={"request_id": request_id, "source": "start_prewrite"},
            )
            deps.update_teacher_session_index(
                context.teacher_id,
                context.session_id,
                preview=context.last_user_text,
                message_increment=1,
            )
            deps.write_chat_job(job_id, {"user_turn_persisted": True}, False)
    except Exception as exc:
        _log.debug("operation failed", exc_info=True)
        detail = str(exc)[:200]
        deps.write_chat_job(
            job_id,
            {"status": "failed", "error": "history_prewrite_failed", "error_detail": detail},
            False,
        )
        return {"ok": True, "job_id": job_id, "status": "failed", "lane_id": context.lane_id}
    return None


def _enqueue_and_finalize_start(
    job_id: str, context: _StartContext, deps: ChatStartDeps
) -> Dict[str, Any]:
    try:
        queue_info = deps.enqueue_chat_job(job_id, context.lane_id)
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
            "lane_id": context.lane_id,
        }

    with deps.chat_job_lock:
        deps.chat_register_recent_locked(context.lane_id, context.fingerprint, job_id)
    deps.write_chat_job(
        job_id,
        {
            "lane_queue_position": queue_info.get("lane_queue_position", 0),
            "lane_queue_size": queue_info.get("lane_queue_size", 0),
            "lane_active": bool(queue_info.get("lane_active")),
        },
        False,
    )
    try:
        deps.append_chat_event(
            job_id,
            "job.queued",
            {
                "status": "queued",
                "lane_id": context.lane_id,
                "lane_queue_position": queue_info.get("lane_queue_position", 0),
                "lane_queue_size": queue_info.get("lane_queue_size", 0),
                "lane_active": bool(queue_info.get("lane_active")),
            },
        )
    except Exception:
        _log.warning("failed to append queued event for chat job %s", job_id, exc_info=True)
    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "lane_id": context.lane_id,
        "lane_queue_position": queue_info.get("lane_queue_position", 0),
        "lane_queue_size": queue_info.get("lane_queue_size", 0),
        "lane_active": bool(queue_info.get("lane_active")),
        "warnings": context.attachment_warnings,
    }


def start_chat_orchestration(req: Any, *, deps: ChatStartDeps) -> Dict[str, Any]:
    request_id = _validate_start_request(req, deps)

    existing_response = _lookup_existing_request(request_id, deps)
    if existing_response is not None:
        return existing_response

    context = _resolve_start_context(req, request_id, deps)
    recent_response = _lookup_recent_dedup(request_id, context, deps)
    if recent_response is not None:
        return recent_response

    _ensure_lane_capacity(context, deps)

    job_id = deps.new_job_id()
    claim_result = _claim_request_id_or_return_existing(request_id, job_id, deps)
    if claim_result is not None:
        return claim_result

    record = _build_job_record(job_id, request_id, req, context, deps)
    deps.write_chat_job(job_id, record, True)
    deps.upsert_chat_request_index(request_id, job_id)

    prewrite_result = _persist_user_turn_prewrite(job_id, request_id, req, context, deps)
    if prewrite_result is not None:
        return prewrite_result

    return _enqueue_and_finalize_start(job_id, context, deps)
