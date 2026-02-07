from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ComputeChatReplyDeps:
    detect_role: Callable[[str], Optional[str]]
    diag_log: Callable[[str, Dict[str, Any]], None]
    teacher_assignment_preflight: Callable[[Any], Optional[str]]
    resolve_teacher_id: Callable[[Optional[str]], str]
    teacher_build_context: Callable[[str, Optional[str], int, str], str]
    detect_student_study_trigger: Callable[[str], bool]
    load_profile_file: Callable[[Any], Dict[str, Any]]
    data_dir: Any
    build_verified_student_context: Callable[[str, Dict[str, Any]], str]
    build_assignment_detail_cached: Callable[[Any], Dict[str, Any]]
    find_assignment_for_date: Callable[..., Optional[Dict[str, Any]]]
    parse_date_str: Callable[[Optional[str]], str]
    build_assignment_context: Callable[..., str]
    chat_extra_system_max_chars: int
    trim_messages: Callable[[List[Dict[str, Any]], Optional[str]], List[Dict[str, Any]]]
    student_inflight: Callable[[Optional[str]], Any]
    run_agent: Callable[..., Dict[str, Any]]
    normalize_math_delimiters: Callable[[str], str]
    resolve_effective_skill: Callable[[Optional[str], Optional[str], str], Dict[str, Any]]


def detect_role_hint(req: Any, *, detect_role: Callable[[str], Optional[str]]) -> Optional[str]:
    role_hint = req.role
    if not role_hint or role_hint == "unknown":
        for msg in reversed(req.messages):
            if msg.role == "user":
                detected = detect_role(msg.content)
                if detected:
                    role_hint = detected
                    break
    return role_hint


def compute_chat_reply_sync(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    session_id: str = "main",
    teacher_id_override: Optional[str] = None,
) -> Tuple[str, Optional[str], str]:
    role_hint = detect_role_hint(req, detect_role=deps.detect_role)
    req_agent_id = str(getattr(req, "agent_id", "") or "")
    last_user_text = next((m.content for m in reversed(req.messages) if m.role == "user"), "") or ""
    requested_skill_id = str(getattr(req, "skill_id", "") or "").strip()
    effective_skill_id = requested_skill_id

    resolve_payload: Dict[str, Any] = {}
    try:
        resolve_payload = deps.resolve_effective_skill(role_hint, requested_skill_id, last_user_text) or {}
        resolved = str(resolve_payload.get("effective_skill_id") or "").strip()
        if resolved and resolved != requested_skill_id:
            req.skill_id = resolved
        effective_skill_id = str(getattr(req, "skill_id", "") or "").strip()
        deps.diag_log(
            "skill.resolve",
            {
                "role": role_hint or "unknown",
                "requested_skill_id": requested_skill_id,
                "effective_skill_id": effective_skill_id,
                "reason": str(resolve_payload.get("reason") or ""),
                "confidence": resolve_payload.get("confidence"),
                "matched_rule": str(resolve_payload.get("matched_rule") or ""),
                "candidates": resolve_payload.get("candidates") or [],
                "best_score": int(resolve_payload.get("best_score") or 0),
                "second_score": int(resolve_payload.get("second_score") or 0),
                "threshold_blocked": bool(resolve_payload.get("threshold_blocked")),
                "load_errors": int(resolve_payload.get("load_errors") or 0),
            },
        )
    except Exception as exc:
        deps.diag_log(
            "skill.resolve.failed",
            {
                "role": role_hint or "unknown",
                "requested_skill_id": requested_skill_id,
                "error": str(exc)[:200],
            },
        )

    if role_hint == "teacher":
        deps.diag_log(
            "teacher_chat.in",
            {
                "last_user": last_user_text[:500],
                "agent_id": req_agent_id,
                "skill_id": effective_skill_id,
                "skill_id_requested": requested_skill_id,
                "skill_id_effective": effective_skill_id,
            },
        )
        preflight = deps.teacher_assignment_preflight(req)
        if preflight:
            deps.diag_log("teacher_chat.preflight_reply", {"reply_preview": preflight[:500]})
            return preflight, role_hint, last_user_text

    extra_system = None
    last_assistant_text = next((m.content for m in reversed(req.messages) if m.role == "assistant"), "") or ""

    effective_teacher_id: Optional[str] = None
    if role_hint == "teacher":
        effective_teacher_id = deps.resolve_teacher_id(teacher_id_override or req.teacher_id)
        extra_system = deps.teacher_build_context(effective_teacher_id, last_user_text, 6000, str(session_id or "main"))

    if role_hint == "student":
        assignment_detail = None
        extra_parts: List[str] = []
        study_mode = deps.detect_student_study_trigger(last_user_text) or (
            ("【诊断问题】" in last_assistant_text) or ("【训练问题】" in last_assistant_text)
        )
        profile = {}
        if req.student_id:
            profile = deps.load_profile_file(deps.data_dir / "student_profiles" / f"{req.student_id}.json")
            extra_parts.append(deps.build_verified_student_context(req.student_id, profile))
        if req.assignment_id:
            folder = deps.data_dir / "assignments" / req.assignment_id
            if folder.exists():
                assignment_detail = deps.build_assignment_detail_cached(folder, include_text=False)
        elif req.student_id:
            date_str = deps.parse_date_str(req.assignment_date)
            class_name = profile.get("class_name")
            found = deps.find_assignment_for_date(date_str, student_id=req.student_id, class_name=class_name)
            if found:
                assignment_detail = deps.build_assignment_detail_cached(found["folder"], include_text=False)
        if assignment_detail and study_mode:
            extra_parts.append(deps.build_assignment_context(assignment_detail, study_mode=True))
        if extra_parts:
            extra_system = "\n\n".join(extra_parts)
            if len(extra_system) > deps.chat_extra_system_max_chars:
                extra_system = extra_system[: deps.chat_extra_system_max_chars] + "…"

    messages = deps.trim_messages([{"role": m.role, "content": m.content} for m in req.messages], role_hint=role_hint)
    if role_hint == "student":
        with deps.student_inflight(req.student_id) as allowed:
            if not allowed:
                return "正在生成上一条回复，请稍候再试。", role_hint, last_user_text
            result = deps.run_agent(
                messages,
                role_hint,
                extra_system=extra_system,
                agent_id=req_agent_id,
                skill_id=req.skill_id,
                teacher_id=effective_teacher_id or req.teacher_id,
            )
    else:
        result = deps.run_agent(
            messages,
            role_hint,
            extra_system=extra_system,
            agent_id=req_agent_id,
            skill_id=req.skill_id,
            teacher_id=effective_teacher_id or req.teacher_id,
        )

    reply_text = deps.normalize_math_delimiters(result.get("reply", ""))
    result["reply"] = reply_text
    return reply_text, role_hint, last_user_text


@dataclass(frozen=True)
class ChatJobProcessDeps:
    chat_job_claim_path: Callable[[str], Any]
    try_acquire_lockfile: Callable[[Any, int], bool]
    chat_job_claim_ttl_sec: int
    load_chat_job: Callable[[str], Dict[str, Any]]
    write_chat_job: Callable[[str, Dict[str, Any]], None]
    chat_request_model: Any
    compute_chat_reply_sync: Callable[..., Tuple[str, Optional[str], str]]
    monotonic: Callable[[], float]
    build_interaction_note: Callable[[str, str, Optional[str]], str]
    profile_update_async: bool
    enqueue_profile_update: Callable[[Dict[str, Any]], None]
    student_profile_update: Callable[[Dict[str, Any]], Any]
    resolve_student_session_id: Callable[[str, Optional[str], Optional[str]], str]
    append_student_session_message: Callable[..., None]
    update_student_session_index: Callable[..., None]
    parse_date_str: Callable[[Optional[str]], str]
    resolve_teacher_id: Callable[[Optional[str]], str]
    ensure_teacher_workspace: Callable[[str], Any]
    append_teacher_session_message: Callable[..., None]
    update_teacher_session_index: Callable[..., None]
    teacher_memory_auto_propose_from_turn: Callable[..., Dict[str, Any]]
    teacher_memory_auto_flush_from_session: Callable[..., Dict[str, Any]]
    maybe_compact_teacher_session: Callable[[str, str], None]
    diag_log: Callable[[str, Dict[str, Any]], None]
    release_lockfile: Callable[[Any], None]


def process_chat_job(job_id: str, *, deps: ChatJobProcessDeps) -> None:
    claim_path = deps.chat_job_claim_path(job_id)
    if not deps.try_acquire_lockfile(claim_path, deps.chat_job_claim_ttl_sec):
        return
    try:
        job = deps.load_chat_job(job_id)
        status = str(job.get("status") or "")
        if status in {"done", "failed", "cancelled"}:
            return

        req_payload = job.get("request") or {}
        if not isinstance(req_payload, dict):
            req_payload = {}
        messages_payload = req_payload.get("messages") or []
        if not isinstance(messages_payload, list) or not messages_payload:
            deps.write_chat_job(job_id, {"status": "failed", "error": "missing_messages"})
            return

        try:
            req = deps.chat_request_model(**req_payload)
        except Exception as exc:
            deps.write_chat_job(job_id, {"status": "failed", "error": "invalid_request", "error_detail": str(exc)[:200]})
            return

        deps.write_chat_job(job_id, {"status": "processing", "step": "agent", "error": ""})
        t0 = deps.monotonic()
        reply_text, role_hint, last_user_text = deps.compute_chat_reply_sync(
            req,
            session_id=str(job.get("session_id") or "main"),
            teacher_id_override=str(job.get("teacher_id") or "").strip() or None,
        )
        duration_ms = int((deps.monotonic() - t0) * 1000)
        deps.write_chat_job(
            job_id,
            {
                "status": "done",
                "step": "done",
                "duration_ms": duration_ms,
                "reply": reply_text,
                "role": role_hint,
                "skill_id_requested": str(job.get("skill_id") or ""),
                "skill_id_effective": str(getattr(req, "skill_id", "") or ""),
            },
        )

        if role_hint == "student" and req.student_id:
            try:
                note = deps.build_interaction_note(last_user_text, reply_text, assignment_id=req.assignment_id)
                payload = {"student_id": req.student_id, "interaction_note": note}
                if deps.profile_update_async:
                    deps.enqueue_profile_update(payload)
                else:
                    deps.student_profile_update(payload)
            except Exception as exc:
                deps.diag_log("student.profile.update_failed", {"student_id": req.student_id, "error": str(exc)[:200]})

            try:
                session_id = str(job.get("session_id") or "") or deps.resolve_student_session_id(
                    req.student_id, req.assignment_id, req.assignment_date
                )
                deps.append_student_session_message(
                    req.student_id,
                    session_id,
                    "user",
                    last_user_text,
                    meta={"request_id": job.get("request_id") or ""},
                )
                deps.append_student_session_message(
                    req.student_id,
                    session_id,
                    "assistant",
                    reply_text,
                    meta={"job_id": job_id, "request_id": job.get("request_id") or ""},
                )
                deps.update_student_session_index(
                    req.student_id,
                    session_id,
                    req.assignment_id,
                    deps.parse_date_str(req.assignment_date),
                    preview=last_user_text or reply_text,
                    message_increment=2,
                )
            except Exception as exc:
                deps.diag_log("student.history.append_failed", {"student_id": req.student_id, "error": str(exc)[:200]})

        if role_hint == "teacher":
            try:
                teacher_id = str(job.get("teacher_id") or "").strip() or deps.resolve_teacher_id(req.teacher_id)
                session_id = str(job.get("session_id") or "").strip() or "main"
                deps.ensure_teacher_workspace(teacher_id)
                deps.append_teacher_session_message(
                    teacher_id,
                    session_id,
                    "user",
                    last_user_text,
                    meta={
                        "request_id": job.get("request_id") or "",
                        "agent_id": req_agent_id,
                        "skill_id": req.skill_id or "",
                        "skill_id_requested": str(job.get("skill_id") or ""),
                        "skill_id_effective": req.skill_id or "",
                    },
                )
                deps.append_teacher_session_message(
                    teacher_id,
                    session_id,
                    "assistant",
                    reply_text,
                    meta={
                        "job_id": job_id,
                        "request_id": job.get("request_id") or "",
                        "agent_id": req_agent_id,
                        "skill_id": req.skill_id or "",
                        "skill_id_requested": str(job.get("skill_id") or ""),
                        "skill_id_effective": req.skill_id or "",
                    },
                )
                deps.update_teacher_session_index(
                    teacher_id,
                    session_id,
                    preview=last_user_text or reply_text,
                    message_increment=2,
                )
                try:
                    auto_intent = deps.teacher_memory_auto_propose_from_turn(
                        teacher_id,
                        session_id=session_id,
                        user_text=last_user_text,
                        assistant_text=reply_text,
                    )
                    if auto_intent.get("created"):
                        deps.diag_log(
                            "teacher.memory.auto_intent.proposed",
                            {
                                "teacher_id": teacher_id,
                                "session_id": session_id,
                                "proposal_id": auto_intent.get("proposal_id"),
                                "target": auto_intent.get("target"),
                            },
                        )
                except Exception as exc:
                    deps.diag_log(
                        "teacher.memory.auto_intent.failed",
                        {"teacher_id": teacher_id, "session_id": session_id, "error": str(exc)[:200]},
                    )
                try:
                    auto_flush = deps.teacher_memory_auto_flush_from_session(teacher_id, session_id=session_id)
                    if auto_flush.get("created"):
                        deps.diag_log(
                            "teacher.memory.auto_flush.proposed",
                            {
                                "teacher_id": teacher_id,
                                "session_id": session_id,
                                "proposal_id": auto_flush.get("proposal_id"),
                            },
                        )
                except Exception as exc:
                    deps.diag_log(
                        "teacher.memory.auto_flush.failed",
                        {"teacher_id": teacher_id, "session_id": session_id, "error": str(exc)[:200]},
                    )
                deps.maybe_compact_teacher_session(teacher_id, session_id)
            except Exception as exc:
                deps.diag_log(
                    "teacher.history.append_failed",
                    {"teacher_id": str(job.get("teacher_id") or ""), "error": str(exc)[:200]},
                )
    finally:
        deps.release_lockfile(claim_path)
