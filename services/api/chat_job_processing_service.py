from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .chat_job_state_machine import (
    is_terminal_chat_job_status,
    normalize_chat_job_status,
    transition_chat_job_status,
)

_log = logging.getLogger(__name__)


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
    build_assignment_detail_cached: Callable[..., Dict[str, Any]]
    find_assignment_for_date: Callable[..., Optional[Dict[str, Any]]]
    parse_date_str: Callable[[Optional[str]], str]
    build_assignment_context: Callable[..., str]
    chat_extra_system_max_chars: int
    trim_messages: Callable[..., List[Dict[str, Any]]]
    student_inflight: Callable[[Optional[str]], Any]
    run_agent: Callable[..., Dict[str, Any]]
    normalize_math_delimiters: Callable[[str], str]
    resolve_effective_skill: Callable[[Optional[str], Optional[str], str], Dict[str, Any]]
    resolve_student_persona_runtime: Callable[[str, str], Dict[str, Any]]


def _resolve_assignment_dir(data_dir: Any, assignment_id: str) -> Optional[Any]:
    try:
        root = (data_dir / "assignments").resolve()
        aid = str(assignment_id or "").strip()
        if not aid:
            return None
        target = (root / aid).resolve()
        if target != root and root not in target.parents:
            return None
        return target
    except Exception:
        _log.warning("operation failed", exc_info=True)
        return None


def _resolve_student_profile_path(data_dir: Any, student_id: str) -> Optional[Any]:
    try:
        root = (data_dir / "student_profiles").resolve()
        sid = str(student_id or "").strip()
        if not sid:
            return None
        target = (root / f"{sid}.json").resolve()
        if target != root and root not in target.parents:
            return None
        return target
    except Exception:
        _log.warning("operation failed", exc_info=True)
        return None


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


def _looks_like_attachment_reference(text: str) -> bool:
    content = str(text or "").strip()
    if not content:
        return False
    cn_tokens = (
        "附件",
        "这个文件",
        "该文件",
        "文件中",
        "表格",
        "成绩单",
        "文档",
        "读取",
        "解析",
    )
    lowered = content.lower()
    return any(token in content for token in cn_tokens) or any(token in lowered for token in ("pdf", "xlsx", "xls", "ocr"))


def compute_chat_reply_sync(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    session_id: str = "main",
    teacher_id_override: Optional[str] = None,
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Tuple[str, Optional[str], str]:
    role_hint = detect_role_hint(req, detect_role=deps.detect_role)
    last_user_text = next((m.content for m in reversed(req.messages) if m.role == "user"), "") or ""
    requested_skill_id = str(getattr(req, "skill_id", "") or "").strip()
    effective_skill_id = requested_skill_id
    attachment_context = str(getattr(req, "attachment_context", "") or "").strip()

    if role_hint == "student" and not attachment_context and _looks_like_attachment_reference(last_user_text):
        return (
            "我现在没有可读取的附件上下文。请在当前会话重新上传或重新选择文件后再提问。"
            "学生端支持 PDF、图片 OCR、XLSX、XLS、Markdown 读取。",
            role_hint,
            last_user_text,
        )

    resolve_payload: Dict[str, Any] = {}
    try:
        resolve_payload = (
            deps.resolve_effective_skill(role_hint, requested_skill_id, last_user_text) or {}
        )
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
        _log.warning("numeric conversion failed", exc_info=True)
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
    persona_first_notice = False
    persona_notice_name = ""
    last_assistant_text = (
        next((m.content for m in reversed(req.messages) if m.role == "assistant"), "") or ""
    )

    effective_teacher_id: Optional[str] = None
    if role_hint == "teacher":
        effective_teacher_id = deps.resolve_teacher_id(teacher_id_override or req.teacher_id)
        extra_system = deps.teacher_build_context(
            effective_teacher_id, last_user_text, 6000, str(session_id or "main")
        )

    if role_hint == "student":
        assignment_detail = None
        extra_parts: List[str] = []
        study_mode = deps.detect_student_study_trigger(last_user_text) or (
            ("【诊断问题】" in last_assistant_text) or ("【训练问题】" in last_assistant_text)
        )
        profile = {}
        if req.student_id:
            profile_path = _resolve_student_profile_path(deps.data_dir, str(req.student_id or ""))
            if profile_path is not None:
                profile = deps.load_profile_file(profile_path)
            extra_parts.append(deps.build_verified_student_context(req.student_id, profile))
        if req.assignment_id:
            folder = _resolve_assignment_dir(deps.data_dir, str(req.assignment_id or ""))
            if folder and folder.exists():
                assignment_detail = deps.build_assignment_detail_cached(folder, include_text=False)
        elif req.student_id:
            date_str = deps.parse_date_str(req.assignment_date)
            class_name = profile.get("class_name")
            found = deps.find_assignment_for_date(
                date_str, student_id=req.student_id, class_name=class_name
            )
            if found:
                assignment_detail = deps.build_assignment_detail_cached(
                    found["folder"], include_text=False
                )
        if assignment_detail and study_mode:
            extra_parts.append(deps.build_assignment_context(assignment_detail, study_mode=True))
        persona_id = str(getattr(req, "persona_id", "") or "").strip()
        if req.student_id and persona_id:
            persona_runtime = deps.resolve_student_persona_runtime(req.student_id, persona_id) or {}
            if bool(persona_runtime.get("ok")):
                persona_prompt = str(persona_runtime.get("persona_prompt") or "").strip()
                if persona_prompt:
                    extra_parts.append(persona_prompt)
                persona_first_notice = bool(persona_runtime.get("first_notice"))
                persona_notice_name = str(persona_runtime.get("persona_name") or persona_id).strip() or persona_id
                deps.diag_log(
                    "student.persona.applied",
                    {
                        "student_id": req.student_id,
                        "persona_id": persona_id,
                        "first_notice": persona_first_notice,
                    },
                )
            else:
                deps.diag_log(
                    "student.persona.unavailable",
                    {
                        "student_id": req.student_id,
                        "persona_id": persona_id,
                        "error": str(persona_runtime.get("error") or ""),
                    },
                )
        if extra_parts:
            extra_system = "\n\n".join(extra_parts)
    if attachment_context:
        attachment_block = f"【附件上下文】\n{attachment_context}"
        extra_system = (
            f"{extra_system}\n\n{attachment_block}".strip()
            if extra_system
            else attachment_block
        )
    if extra_system and len(extra_system) > deps.chat_extra_system_max_chars:
        extra_system = extra_system[: deps.chat_extra_system_max_chars] + "…"

    messages = deps.trim_messages(
        [{"role": m.role, "content": m.content} for m in req.messages], role_hint=role_hint
    )
    def _run_agent_with_optional_events() -> Dict[str, Any]:
        try:
            return deps.run_agent(
                messages,
                role_hint,
                extra_system=extra_system,
                skill_id=req.skill_id,
                teacher_id=effective_teacher_id or req.teacher_id,
                event_sink=event_sink,
            )
        except TypeError:
            return deps.run_agent(
                messages,
                role_hint,
                extra_system=extra_system,
                skill_id=req.skill_id,
                teacher_id=effective_teacher_id or req.teacher_id,
            )

    if role_hint == "student":
        with deps.student_inflight(req.student_id) as allowed:
            if not allowed:
                return "正在生成上一条回复，请稍候再试。", role_hint, last_user_text
            result = _run_agent_with_optional_events()
    else:
        result = _run_agent_with_optional_events()

    reply_text = deps.normalize_math_delimiters(result.get("reply", ""))
    if role_hint == "student" and persona_first_notice and persona_notice_name:
        reply_text = f"提示：你当前使用的是「{persona_notice_name}」虚拟风格卡，仅用于表达风格。\n\n{reply_text}"
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
    build_interaction_note: Callable[..., str]
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
    append_chat_event: Callable[[str, str, Dict[str, Any]], Dict[str, Any]] = (
        lambda _job_id, _event_type, _payload: {}
    )
    student_memory_auto_propose_from_turn: Callable[..., Dict[str, Any]] = (
        lambda **_kwargs: {"ok": False, "created": False, "reason": "disabled"}
    )


class _ChatJobStatusWriter:
    def __init__(
        self,
        *,
        job_id: str,
        deps: ChatJobProcessDeps,
        current_status: str,
    ) -> None:
        self.job_id = job_id
        self.deps = deps
        self.current_status = current_status

    def transition(self, next_status: str, updates: Dict[str, Any]) -> bool:
        try:
            resolved = transition_chat_job_status(self.current_status, next_status)
        except ValueError:
            self.deps.write_chat_job(
                self.job_id,
                {
                    "status": "failed",
                    "error": "invalid_status_transition",
                    "error_detail": f"{self.current_status}->{normalize_chat_job_status(next_status)}",
                },
            )
            self.current_status = "failed"
            return False

        payload = dict(updates or {})
        payload["status"] = resolved
        self.deps.write_chat_job(self.job_id, payload)
        event_type = ""
        if resolved == "processing":
            event_type = "job.processing"
        elif resolved == "done":
            event_type = "job.done"
        elif resolved in {"failed", "cancelled"}:
            event_type = f"job.{resolved}"
        if event_type:
            try:
                self.deps.append_chat_event(
                    self.job_id,
                    event_type,
                    {
                        "status": resolved,
                        "step": payload.get("step"),
                        "reply": payload.get("reply"),
                        "error": payload.get("error"),
                        "error_detail": payload.get("error_detail"),
                    },
                )
            except Exception:
                _log.warning(
                    "failed to append status event %s for job %s",
                    event_type,
                    self.job_id,
                    exc_info=True,
                )
        self.current_status = resolved
        return True


def _iter_reply_chunks(text: str) -> List[str]:
    content = str(text or "")
    if not content:
        return []
    step = 24
    return [content[idx : idx + step] for idx in range(0, len(content), step)]


def _emit_assistant_reply_events(
    *,
    job_id: str,
    reply_text: str,
    deps: ChatJobProcessDeps,
) -> None:
    for chunk in _iter_reply_chunks(reply_text):
        deps.append_chat_event(job_id, "assistant.delta", {"delta": chunk})
    deps.append_chat_event(job_id, "assistant.done", {"text": str(reply_text or "")})


def _call_compute_chat_reply_sync(
    *,
    deps: ChatJobProcessDeps,
    req: Any,
    session_id: str,
    teacher_id_override: Optional[str],
    event_sink: Callable[[str, Dict[str, Any]], None],
) -> Tuple[str, Optional[str], str]:
    supports_event_sink = True
    try:
        params = inspect.signature(deps.compute_chat_reply_sync).parameters
        supports_event_sink = "event_sink" in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        )
    except Exception:
        supports_event_sink = True

    kwargs: Dict[str, Any] = {
        "session_id": session_id,
        "teacher_id_override": teacher_id_override,
    }
    if supports_event_sink:
        kwargs["event_sink"] = event_sink
    return deps.compute_chat_reply_sync(req, **kwargs)


def _build_chat_request_for_job(
    job: Dict[str, Any],
    *,
    deps: ChatJobProcessDeps,
    status_writer: _ChatJobStatusWriter,
) -> Optional[Any]:
    req_payload = job.get("request") or {}
    if not isinstance(req_payload, dict):
        req_payload = {}
    messages_payload = req_payload.get("messages") or []
    if not isinstance(messages_payload, list) or not messages_payload:
        status_writer.transition("failed", {"error": "missing_messages"})
        return None
    try:
        return deps.chat_request_model(**req_payload)
    except Exception as exc:
        _log.warning("operation failed", exc_info=True)
        status_writer.transition(
            "failed",
            {"error": "invalid_request", "error_detail": str(exc)[:200]},
        )
        return None


def _persist_teacher_history(
    job_id: str,
    job: Dict[str, Any],
    req: Any,
    *,
    reply_text: str,
    last_user_text: str,
    user_turn_persisted: bool,
    deps: ChatJobProcessDeps,
    status_writer: _ChatJobStatusWriter,
) -> tuple[bool, str, str]:
    teacher_id = str(job.get("teacher_id") or "").strip() or deps.resolve_teacher_id(req.teacher_id)
    session_id = str(job.get("session_id") or "").strip() or "main"
    try:
        if not user_turn_persisted:
            deps.append_teacher_session_message(
                teacher_id,
                session_id,
                "user",
                last_user_text,
                meta={
                    "request_id": job.get("request_id") or "",
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
                "skill_id": req.skill_id or "",
                "skill_id_requested": str(job.get("skill_id") or ""),
                "skill_id_effective": req.skill_id or "",
            },
        )
        deps.update_teacher_session_index(
            teacher_id,
            session_id,
            preview=last_user_text or reply_text,
            message_increment=1 if user_turn_persisted else 2,
        )
        return True, teacher_id, session_id
    except Exception as exc:
        _log.warning("operation failed", exc_info=True)
        detail = str(exc)[:200]
        deps.diag_log(
            "teacher.history.append_failed",
            {"teacher_id": str(job.get("teacher_id") or ""), "error": detail},
        )
        status_writer.transition(
            "failed", {"error": "history_persist_failed", "error_detail": detail}
        )
        return False, teacher_id, session_id


def _update_student_profile_safe(
    req: Any, *, last_user_text: str, reply_text: str, deps: ChatJobProcessDeps
) -> None:
    try:
        note = deps.build_interaction_note(
            last_user_text, reply_text, assignment_id=req.assignment_id
        )
        payload = {"student_id": req.student_id, "interaction_note": note}
        if deps.profile_update_async:
            deps.enqueue_profile_update(payload)
        else:
            deps.student_profile_update(payload)
    except Exception as exc:
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "student.profile.update_failed",
            {"student_id": req.student_id, "error": str(exc)[:200]},
        )


def _persist_student_history(
    job_id: str,
    job: Dict[str, Any],
    req: Any,
    *,
    reply_text: str,
    last_user_text: str,
    user_turn_persisted: bool,
    deps: ChatJobProcessDeps,
    status_writer: _ChatJobStatusWriter,
) -> bool:
    try:
        session_id = str(job.get("session_id") or "") or deps.resolve_student_session_id(
            req.student_id, req.assignment_id, req.assignment_date
        )
        if not user_turn_persisted:
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
            message_increment=1 if user_turn_persisted else 2,
        )
        return True
    except Exception as exc:
        _log.warning("operation failed", exc_info=True)
        detail = str(exc)[:200]
        deps.diag_log(
            "student.history.append_failed", {"student_id": req.student_id, "error": detail}
        )
        status_writer.transition(
            "failed", {"error": "history_persist_failed", "error_detail": detail}
        )
        return False


def _run_teacher_post_done_side_effects(
    teacher_id: str,
    session_id: str,
    *,
    last_user_text: str,
    reply_text: str,
    deps: ChatJobProcessDeps,
) -> None:
    try:
        deps.ensure_teacher_workspace(teacher_id)
    except Exception as exc:
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "teacher.workspace.ensure_failed",
            {"teacher_id": teacher_id, "session_id": session_id, "error": str(exc)[:200]},
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
        _log.warning("operation failed", exc_info=True)
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
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "teacher.memory.auto_flush.failed",
            {"teacher_id": teacher_id, "session_id": session_id, "error": str(exc)[:200]},
        )
    try:
        deps.maybe_compact_teacher_session(teacher_id, session_id)
    except Exception as exc:
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "teacher.session.compact_failed",
            {"teacher_id": teacher_id, "session_id": session_id, "error": str(exc)[:200]},
        )


def _run_student_post_done_side_effects(
    *,
    req: Any,
    job: Dict[str, Any],
    session_id: str,
    last_user_text: str,
    reply_text: str,
    deps: ChatJobProcessDeps,
) -> None:
    student_id = str(getattr(req, "student_id", "") or "").strip()
    if not student_id:
        return
    teacher_id = str(getattr(req, "teacher_id", "") or "").strip()
    try:
        auto = deps.student_memory_auto_propose_from_turn(
            teacher_id=teacher_id or None,
            student_id=student_id,
            session_id=str(session_id or ""),
            user_text=last_user_text,
            assistant_text=reply_text,
            request_id=str(job.get("request_id") or ""),
        )
        if auto.get("created"):
            deps.diag_log(
                "student.memory.auto.proposed",
                {
                    "teacher_id": str(auto.get("teacher_id") or teacher_id),
                    "student_id": student_id,
                    "session_id": str(session_id or ""),
                    "proposal_id": auto.get("proposal_id"),
                    "memory_type": auto.get("memory_type"),
                },
            )
    except Exception as exc:
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "student.memory.auto.failed",
            {
                "teacher_id": teacher_id,
                "student_id": student_id,
                "session_id": str(session_id or ""),
                "error": str(exc)[:200],
            },
        )


def process_chat_job(job_id: str, *, deps: ChatJobProcessDeps) -> None:
    claim_path = deps.chat_job_claim_path(job_id)
    if not deps.try_acquire_lockfile(claim_path, deps.chat_job_claim_ttl_sec):
        return
    try:
        job = deps.load_chat_job(job_id)
        status = normalize_chat_job_status(job.get("status"))
        if is_terminal_chat_job_status(status):
            return

        status_writer = _ChatJobStatusWriter(job_id=job_id, deps=deps, current_status=status)
        req = _build_chat_request_for_job(job, deps=deps, status_writer=status_writer)
        if req is None:
            return

        if not status_writer.transition("processing", {"step": "agent", "error": ""}):
            return

        t0 = deps.monotonic()
        event_state = {"assistant_done": False}

        def _event_sink(event_type: str, payload: Dict[str, Any]) -> None:
            try:
                deps.append_chat_event(job_id, event_type, payload)
                if str(event_type) == "assistant.done":
                    event_state["assistant_done"] = True
            except Exception:
                _log.warning(
                    "failed to append runtime event %s for job %s",
                    event_type,
                    job_id,
                    exc_info=True,
                )

        reply_text, role_hint, last_user_text = _call_compute_chat_reply_sync(
            deps=deps,
            req=req,
            session_id=str(job.get("session_id") or "main"),
            teacher_id_override=str(job.get("teacher_id") or "").strip() or None,
            event_sink=_event_sink,
        )
        if not event_state["assistant_done"]:
            _emit_assistant_reply_events(job_id=job_id, reply_text=reply_text, deps=deps)
        duration_ms = int((deps.monotonic() - t0) * 1000)
        user_turn_persisted = bool(job.get("user_turn_persisted"))

        teacher_id = ""
        session_id = ""
        if role_hint == "teacher":
            (
                persisted_ok,
                teacher_id,
                session_id,
            ) = _persist_teacher_history(
                job_id,
                job,
                req,
                reply_text=reply_text,
                last_user_text=last_user_text,
                user_turn_persisted=user_turn_persisted,
                deps=deps,
                status_writer=status_writer,
            )
            if not persisted_ok:
                return

        if role_hint == "student" and req.student_id:
            _update_student_profile_safe(
                req, last_user_text=last_user_text, reply_text=reply_text, deps=deps
            )
            student_session_id = str(job.get("session_id") or "") or deps.resolve_student_session_id(
                req.student_id,
                req.assignment_id,
                req.assignment_date,
            )
            if not _persist_student_history(
                job_id,
                job,
                req,
                reply_text=reply_text,
                last_user_text=last_user_text,
                user_turn_persisted=user_turn_persisted,
                deps=deps,
                status_writer=status_writer,
            ):
                return

        if not status_writer.transition(
            "done",
            {
                "step": "done",
                "duration_ms": duration_ms,
                "reply": reply_text,
                "role": role_hint,
                "skill_id_requested": str(job.get("skill_id") or ""),
                "skill_id_effective": str(getattr(req, "skill_id", "") or ""),
            },
        ):
            return

        if role_hint == "teacher":
            _run_teacher_post_done_side_effects(
                teacher_id,
                session_id,
                last_user_text=last_user_text,
                reply_text=reply_text,
                deps=deps,
            )
        if role_hint == "student" and req.student_id:
            _run_student_post_done_side_effects(
                req=req,
                job=job,
                session_id=student_session_id,
                last_user_text=last_user_text,
                reply_text=reply_text,
                deps=deps,
            )
    finally:
        deps.release_lockfile(claim_path)
