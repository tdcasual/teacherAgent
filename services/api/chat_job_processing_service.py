from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .assignment.visibility import student_can_read_assignment
from .assignment_catalog_service import assignment_specificity
from .chat_job_processing.compute import _compute_reply_with_runtime_events
from .chat_job_processing.confirm import _persist_confirmation_pause
from .chat_job_processing.history import (
    _persist_history_by_role,
    _run_post_done_side_effects_by_role,
)
from .chat_job_processing.timeline import (
    _persist_execution_timeline,
    _request_payload_dict,
)
from .chat_job_state_machine import (
    is_terminal_chat_job_status,
    normalize_chat_job_status,
    transition_chat_job_status,
)
from .paths import TeacherIdentityError, require_teacher_id

_log = logging.getLogger(__name__)


def _default_teacher_workflow_preflight(
    _req: Any,
    effective_skill_id: str,
    last_user_text: str,
    attachment_context: str,
) -> Optional[str]:
    del effective_skill_id, last_user_text, attachment_context
    return None


def _default_resolve_teacher_workflow(
    _req: Any,
    effective_skill_id: str,
    last_user_text: str,
    attachment_context: str,
) -> Dict[str, Any]:
    del effective_skill_id, last_user_text, attachment_context
    return {}


def _default_subject_prompt_overlay(
    subject_id: Optional[str], role_hint: Optional[str] = None
) -> str:
    from .subject_pack_service import overlay_for_role

    return overlay_for_role(subject_id, role_hint)


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
    teacher_workflow_preflight: Callable[[Any, str, str, str], Optional[str]] = (
        _default_teacher_workflow_preflight
    )
    resolve_teacher_workflow: Callable[[Any, str, str, str], Dict[str, Any]] = (
        _default_resolve_teacher_workflow
    )
    subject_prompt_overlay: Callable[..., str] = _default_subject_prompt_overlay


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
    except Exception:  # policy: allowed-broad-except
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
    except Exception:  # policy: allowed-broad-except
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
    return any(token in content for token in cn_tokens) or any(
        token in lowered for token in ("pdf", "xlsx", "xls", "ocr")
    )


def _workflow_resolution_mode(reason: str) -> str:
    normalized = str(reason or "").strip()
    if normalized == "explicit":
        return "explicit"
    if "auto_rule" in normalized and not normalized.endswith("_default"):
        return "auto"
    if normalized.endswith("_default") or normalized == "role_default":
        return "default"
    return "fallback" if normalized else "unknown"


def _coerce_workflow_resolution_float(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(raw)
    except Exception:  # policy: allowed-broad-except
        _log.warning("numeric conversion failed", exc_info=True)
        return None


def _coerce_workflow_resolution_int(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:  # policy: allowed-broad-except
        _log.warning("numeric conversion failed", exc_info=True)
        return None


def _normalize_workflow_resolution_hits(raw: Any) -> Optional[List[str]]:
    if not isinstance(raw, list):
        return None
    hits = [str(hit or "").strip() for hit in raw if str(hit or "").strip()]
    return hits[:6] if hits else None


def _normalize_workflow_resolution_candidate(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    skill_id = str(item.get("skill_id") or "").strip()
    if not skill_id:
        return None

    candidate: Dict[str, Any] = {"skill_id": skill_id}
    score = _coerce_workflow_resolution_int(item.get("score"))
    if score is not None:
        candidate["score"] = score
    hits = _normalize_workflow_resolution_hits(item.get("hits"))
    if hits:
        candidate["hits"] = hits
    return candidate


def _normalize_workflow_resolution_candidates(raw: Any) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(raw, list):
        return None
    return [
        candidate
        for candidate in (_normalize_workflow_resolution_candidate(item) for item in raw[:3])
        if candidate is not None
    ]


def _resolve_requested_rewritten(
    requested_skill_id: str,
    effective_skill_id: str,
    requested_rewritten: Any,
) -> bool:
    if requested_rewritten is not None:
        return bool(requested_rewritten)
    return bool(
        requested_skill_id and effective_skill_id and requested_skill_id != effective_skill_id
    )


def _normalize_workflow_resolution_payload(
    requested_skill_id: str,
    effective_skill_id: str,
    resolve_payload: Dict[str, Any],
) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {
        "requested_skill_id": str(requested_skill_id or "").strip(),
        "effective_skill_id": str(effective_skill_id or "").strip(),
    }

    reason = str(resolve_payload.get("reason") or "").strip()
    if reason:
        normalized["reason"] = reason

    confidence = _coerce_workflow_resolution_float(resolve_payload.get("confidence"))
    if confidence is not None:
        normalized["confidence"] = confidence

    candidates = _normalize_workflow_resolution_candidates(resolve_payload.get("candidates"))
    if candidates is not None:
        normalized["candidates"] = candidates

    resolution_mode = str(resolve_payload.get("resolution_mode") or "").strip()
    if not resolution_mode:
        resolution_mode = _workflow_resolution_mode(reason)
    normalized["resolution_mode"] = resolution_mode

    auto_selected = resolve_payload.get("auto_selected")
    if auto_selected is None:
        auto_selected = resolution_mode == "auto"
    normalized["auto_selected"] = bool(auto_selected)

    normalized["requested_rewritten"] = _resolve_requested_rewritten(
        normalized["requested_skill_id"],
        normalized["effective_skill_id"],
        resolve_payload.get("requested_rewritten"),
    )

    return normalized


def _workflow_outcome_job_updates(
    job: Dict[str, Any], *, outcome: str, outcome_reason: str | None = None
) -> Dict[str, Any]:
    requested = str(job.get("skill_id_requested") or "").strip()
    effective = str(job.get("skill_id_effective") or "").strip()
    reason = str(job.get("skill_reason") or "").strip()
    if not requested and not effective and not reason:
        return {}
    final_reason = str(outcome_reason or "").strip() or str(outcome or "").strip() or "unknown"
    return {
        "skill_outcome": str(outcome or "").strip() or "unknown",
        "skill_outcome_reason": final_reason,
    }


def _workflow_outcome_metrics_payload(
    job: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    request_payload = _request_payload_dict(job)
    return {
        "role": str(
            job.get("role") or request_payload.get("role") or payload.get("role") or ""
        ).strip()
        or None,
        "requested_skill_id": str(
            payload.get("skill_id_requested") or job.get("skill_id_requested") or ""
        ).strip(),
        "effective_skill_id": str(
            payload.get("skill_id_effective") or job.get("skill_id_effective") or ""
        ).strip(),
        "reason": str(payload.get("skill_reason") or job.get("skill_reason") or "").strip(),
        "resolution_mode": str(
            payload.get("skill_resolution_mode") or job.get("skill_resolution_mode") or ""
        ).strip()
        or None,
        "outcome": str(payload.get("skill_outcome") or job.get("skill_outcome") or "").strip()
        or "unknown",
        "outcome_reason": str(
            payload.get("skill_outcome_reason") or job.get("skill_outcome_reason") or ""
        ).strip()
        or "unknown",
    }


def _resolve_effective_skill_id(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    role_hint: Optional[str],
    requested_skill_id: str,
    last_user_text: str,
) -> tuple[str, Dict[str, Any]]:
    effective_skill_id = requested_skill_id
    resolution_payload = _normalize_workflow_resolution_payload(
        requested_skill_id, effective_skill_id, {}
    )
    try:
        resolve_payload = (
            deps.resolve_effective_skill(role_hint, requested_skill_id, last_user_text) or {}
        )
        resolved = str(resolve_payload.get("effective_skill_id") or "").strip()
        if resolved and resolved != requested_skill_id:
            req.skill_id = resolved
        effective_skill_id = str(getattr(req, "skill_id", "") or "").strip()
        resolution_payload = _normalize_workflow_resolution_payload(
            requested_skill_id,
            effective_skill_id,
            resolve_payload,
        )
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
    except Exception as exc:  # policy: allowed-broad-except
        _log.warning("numeric conversion failed", exc_info=True)
        deps.diag_log(
            "skill.resolve.failed",
            {
                "role": role_hint or "unknown",
                "requested_skill_id": requested_skill_id,
                "error": str(exc)[:200],
            },
        )
    return effective_skill_id, resolution_payload


def _emit_workflow_resolution_event(
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]],
    payload: Dict[str, Any],
) -> None:
    if not callable(event_sink):
        return
    effective = str(payload.get("effective_skill_id") or "").strip()
    if not effective:
        return
    event_sink("workflow.resolved", payload)


def _teacher_preflight_reply(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    last_user_text: str,
    requested_skill_id: str,
    effective_skill_id: str,
    attachment_context: str,
    workflow_payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    workflow_payload = workflow_payload if isinstance(workflow_payload, dict) else {}
    deps.diag_log(
        "teacher_chat.in",
        {
            "last_user": last_user_text[:500],
            "skill_id": effective_skill_id,
            "skill_id_requested": requested_skill_id,
            "skill_id_effective": effective_skill_id,
            "workflow_id": str(workflow_payload.get("workflow_id") or ""),
        },
    )
    workflow_preflight = deps.teacher_workflow_preflight(
        req,
        effective_skill_id,
        last_user_text,
        attachment_context,
    )
    if workflow_preflight:
        deps.diag_log(
            "teacher_chat.workflow_preflight_reply", {"reply_preview": workflow_preflight[:500]}
        )
        return workflow_preflight
    preflight = deps.teacher_assignment_preflight(req)
    if preflight:
        deps.diag_log("teacher_chat.preflight_reply", {"reply_preview": preflight[:500]})
        return preflight
    return None


def _merge_teacher_extra_system(
    teacher_context: Optional[str], workflow_payload: Dict[str, Any]
) -> Optional[str]:
    workflow_label = str(workflow_payload.get("workflow_label") or "").strip()
    workflow_extra = str(workflow_payload.get("extra_system") or "").strip()
    blocks: List[str] = []
    if workflow_extra:
        heading = f"【教学 workflow：{workflow_label}】" if workflow_label else "【教学 workflow】"
        blocks.append(f"{heading}\n{workflow_extra}".strip())
    if teacher_context:
        blocks.append(str(teacher_context).strip())
    return "\n\n".join([block for block in blocks if block]).strip() or None


def _teacher_extra_system(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    last_user_text: str,
    session_id: str,
    teacher_id_override: Optional[str],
    workflow_payload: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[str]]:
    try:
        teacher_id = require_teacher_id(teacher_id_override or getattr(req, "teacher_id", None))
    except TeacherIdentityError:
        return None, None
    teacher_context = deps.teacher_build_context(
        teacher_id, last_user_text, 6000, str(session_id or "main")
    )
    return (
        _merge_teacher_extra_system(teacher_context, workflow_payload or {}),
        teacher_id,
    )


def _student_can_attach_assignment(
    detail: Optional[Dict[str, Any]], *, student_id: Optional[str], class_name: Optional[str]
) -> bool:
    if not isinstance(detail, dict):
        return False
    meta = detail.get("meta") if isinstance(detail.get("meta"), dict) else detail
    if not student_can_read_assignment(meta):
        return False
    return int(assignment_specificity(meta or {}, student_id, class_name)) > 0


def _student_extra_system(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    last_user_text: str,
    last_assistant_text: str,
) -> Optional[str]:
    assignment_detail = None
    extra_parts: List[str] = []
    study_mode = deps.detect_student_study_trigger(last_user_text) or (
        ("【诊断问题】" in last_assistant_text) or ("【训练问题】" in last_assistant_text)
    )
    profile: Dict[str, Any] = {}

    if req.student_id:
        profile_path = _resolve_student_profile_path(deps.data_dir, str(req.student_id or ""))
        if profile_path is not None:
            profile = deps.load_profile_file(profile_path)
        extra_parts.append(deps.build_verified_student_context(req.student_id, profile))

    class_name = str(profile.get("class_name") or "").strip() or None
    if req.assignment_id:
        folder = _resolve_assignment_dir(deps.data_dir, str(req.assignment_id or ""))
        if folder and folder.exists():
            assignment_detail = deps.build_assignment_detail_cached(folder, include_text=False)
    if assignment_detail and not _student_can_attach_assignment(
        assignment_detail, student_id=req.student_id, class_name=class_name
    ):
        assignment_detail = None

    if assignment_detail and study_mode:
        extra_parts.append(deps.build_assignment_context(assignment_detail, study_mode=True))
    if not extra_parts:
        return None
    return "\n\n".join(extra_parts)


def _with_attachment_context(extra_system: Optional[str], attachment_context: str) -> Optional[str]:
    attachment = str(attachment_context or "").strip()
    if not attachment:
        return extra_system
    attachment_block = f"【附件上下文】\n{attachment}"
    return f"{extra_system}\n\n{attachment_block}".strip() if extra_system else attachment_block


def _cap_extra_system(text: Optional[str], *, max_chars: int) -> Optional[str]:
    if text and len(text) > max_chars:
        return text[:max_chars] + "…"
    return text


def _join_extra_system(*blocks: Optional[str]) -> Optional[str]:
    parts = [str(block).strip() for block in blocks if str(block or "").strip()]
    return "\n\n".join(parts) or None


def _subject_id_from_assignment_detail(detail: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(detail, dict):
        return None
    meta = detail.get("meta") if isinstance(detail.get("meta"), dict) else {}
    from .subject_pack_service import pack_id_from_meta

    token = pack_id_from_meta(meta)
    return token or None


def _resolve_chat_subject_id(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    role_hint: Optional[str],
) -> Optional[str]:
    del role_hint
    assignment_id = str(getattr(req, "assignment_id", "") or "").strip()
    if not assignment_id:
        return None
    folder = _resolve_assignment_dir(deps.data_dir, assignment_id)
    if folder and folder.exists():
        detail = deps.build_assignment_detail_cached(folder, include_text=False)
        return _subject_id_from_assignment_detail(detail)
    return None


def _missing_student_attachment_reply(
    role_hint: Optional[str],
    attachment_context: str,
    last_user_text: str,
) -> Optional[str]:
    if role_hint != "student" or attachment_context:
        return None
    if not _looks_like_attachment_reference(last_user_text):
        return None
    return (
        "我现在没有可读取的附件上下文。请在当前会话重新上传或重新选择文件后再提问。"
        "学生端支持 PDF、图片 OCR、XLSX、XLS、Markdown 读取。"
    )


def _resolve_teacher_workflow_payload(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    role_hint: Optional[str],
    effective_skill_id: str,
    last_user_text: str,
    attachment_context: str,
    workflow_resolution: Dict[str, Any],
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]],
) -> Dict[str, Any]:
    if role_hint != "teacher":
        return {}
    teacher_workflow = (
        deps.resolve_teacher_workflow(
            req,
            effective_skill_id,
            last_user_text,
            attachment_context,
        )
        or {}
    )
    _emit_workflow_resolution_event(event_sink, workflow_resolution)
    if teacher_workflow:
        deps.diag_log(
            "teacher.workflow.orchestrated",
            {
                "workflow_id": str(teacher_workflow.get("workflow_id") or ""),
                "workflow_label": str(teacher_workflow.get("workflow_label") or ""),
                "skill_id": effective_skill_id,
            },
        )
    return teacher_workflow


def _build_chat_extra_system(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    role_hint: Optional[str],
    last_user_text: str,
    last_assistant_text: str,
    session_id: str,
    teacher_id_override: Optional[str],
    attachment_context: str,
    teacher_workflow: Dict[str, Any],
) -> Tuple[Optional[str], Optional[str]]:
    extra_system: Optional[str] = None
    effective_teacher_id: Optional[str] = None
    if role_hint == "teacher":
        extra_system, effective_teacher_id = _teacher_extra_system(
            req,
            deps=deps,
            last_user_text=last_user_text,
            session_id=session_id,
            teacher_id_override=teacher_id_override,
            workflow_payload=teacher_workflow,
        )
    elif role_hint == "student":
        extra_system = _student_extra_system(
            req,
            deps=deps,
            last_user_text=last_user_text,
            last_assistant_text=last_assistant_text,
        )
    overlay = str(
        deps.subject_prompt_overlay(
            _resolve_chat_subject_id(req, deps=deps, role_hint=role_hint),
            role_hint,
        )
        or ""
    ).strip()
    extra_system = _join_extra_system(overlay, extra_system)
    extra_system = _with_attachment_context(extra_system, attachment_context)
    return (
        _cap_extra_system(
            extra_system,
            max_chars=deps.chat_extra_system_max_chars,
        ),
        effective_teacher_id,
    )


def _build_run_agent_kwargs(
    req: Any,
    *,
    extra_system: Optional[str],
    effective_teacher_id: Optional[str],
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]],
    job_id: Optional[str] = None,
    lane_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    initial_convo: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    run_agent_kwargs: Dict[str, Any] = {
        "extra_system": extra_system,
        "skill_id": req.skill_id,
        "teacher_id": effective_teacher_id or req.teacher_id,
        "event_sink": event_sink,
    }
    analysis_target = getattr(req, "analysis_target", None)
    if analysis_target is not None:
        run_agent_kwargs["analysis_target"] = analysis_target
    if job_id:
        run_agent_kwargs["job_id"] = job_id
    if lane_id:
        run_agent_kwargs["lane_id"] = lane_id
    if actor_id:
        run_agent_kwargs["actor_id"] = actor_id
    if initial_convo is not None:
        run_agent_kwargs["initial_convo"] = initial_convo
    return run_agent_kwargs


def _run_agent_for_chat(
    *,
    req: Any,
    deps: ComputeChatReplyDeps,
    messages: List[Dict[str, Any]],
    role_hint: Optional[str],
    last_user_text: str,
    extra_system: Optional[str],
    effective_teacher_id: Optional[str],
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]],
    job_id: Optional[str] = None,
    lane_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    initial_convo: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, Optional[str], str]]]:
    run_agent_kwargs = _build_run_agent_kwargs(
        req,
        extra_system=extra_system,
        effective_teacher_id=effective_teacher_id,
        event_sink=event_sink,
        job_id=job_id,
        lane_id=lane_id,
        actor_id=actor_id,
        initial_convo=initial_convo,
    )
    if role_hint != "student":
        return deps.run_agent(messages, role_hint, **run_agent_kwargs), None
    with deps.student_inflight(req.student_id) as allowed:
        if not allowed:
            return None, ("正在生成上一条回复，请稍候再试。", role_hint, last_user_text)
        return deps.run_agent(messages, role_hint, **run_agent_kwargs), None


def compute_chat_reply_sync(
    req: Any,
    *,
    deps: ComputeChatReplyDeps,
    session_id: str = "main",
    teacher_id_override: Optional[str] = None,
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    extra_out: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    lane_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    initial_convo: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Optional[str], str]:
    role_hint = detect_role_hint(req, detect_role=deps.detect_role)
    last_user_text = next((m.content for m in reversed(req.messages) if m.role == "user"), "") or ""
    requested_skill_id = str(getattr(req, "skill_id", "") or "").strip()
    attachment_context = str(getattr(req, "attachment_context", "") or "").strip()

    missing_attachment_reply = _missing_student_attachment_reply(
        role_hint,
        attachment_context,
        last_user_text,
    )
    if missing_attachment_reply:
        return missing_attachment_reply, role_hint, last_user_text

    effective_skill_id, workflow_resolution = _resolve_effective_skill_id(
        req,
        deps=deps,
        role_hint=role_hint,
        requested_skill_id=requested_skill_id,
        last_user_text=last_user_text,
    )

    teacher_workflow = _resolve_teacher_workflow_payload(
        req,
        deps=deps,
        role_hint=role_hint,
        effective_skill_id=effective_skill_id,
        last_user_text=last_user_text,
        attachment_context=attachment_context,
        workflow_resolution=workflow_resolution,
        event_sink=event_sink,
    )

    if role_hint == "teacher":
        preflight = _teacher_preflight_reply(
            req,
            deps=deps,
            last_user_text=last_user_text,
            requested_skill_id=requested_skill_id,
            effective_skill_id=effective_skill_id,
            attachment_context=attachment_context,
            workflow_payload=teacher_workflow,
        )
        if preflight:
            return preflight, role_hint, last_user_text

    extra_system: Optional[str] = None
    last_assistant_text = (
        next((m.content for m in reversed(req.messages) if m.role == "assistant"), "") or ""
    )
    extra_system, effective_teacher_id = _build_chat_extra_system(
        req,
        deps=deps,
        role_hint=role_hint,
        last_user_text=last_user_text,
        last_assistant_text=last_assistant_text,
        session_id=session_id,
        teacher_id_override=teacher_id_override,
        attachment_context=attachment_context,
        teacher_workflow=teacher_workflow,
    )

    messages = deps.trim_messages(
        [{"role": m.role, "content": m.content} for m in req.messages], role_hint=role_hint
    )
    result, blocked_reply = _run_agent_for_chat(
        req=req,
        deps=deps,
        messages=messages,
        role_hint=role_hint,
        last_user_text=last_user_text,
        extra_system=extra_system,
        effective_teacher_id=effective_teacher_id,
        event_sink=event_sink,
        job_id=job_id,
        lane_id=lane_id,
        actor_id=actor_id
        or (
            str(getattr(req, "student_id", "") or "").strip()
            if role_hint == "student"
            else effective_teacher_id
        ),
        initial_convo=initial_convo,
    )
    if blocked_reply:
        return blocked_reply

    assert result is not None
    if str(result.get("pause") or "") == "confirmation_required":
        if extra_out is not None:
            extra_out.update(result)
        return "", role_hint, last_user_text
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
    student_memory_auto_propose_from_turn: Callable[..., Dict[str, Any]]
    compute_assignment_progress: Callable[[str, bool], Dict[str, Any]]
    student_memory_auto_propose_from_assignment_evidence: Callable[..., Dict[str, Any]]
    diag_log: Callable[[str, Dict[str, Any]], None]
    release_lockfile: Callable[[Any], None]
    append_chat_event: Callable[[str, str, Dict[str, Any]], Dict[str, Any]] = (
        lambda _job_id, _event_type, _payload: {}
    )
    record_workflow_resolution: Callable[[Dict[str, Any]], None] = lambda _payload: None
    record_workflow_outcome: Callable[[Dict[str, Any]], None] = lambda _payload: None


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
        current_job: Dict[str, Any] = {}
        if resolved in {"done", "failed", "cancelled"}:
            try:
                current_job = self.deps.load_chat_job(self.job_id)
            except Exception:
                current_job = {}
            outcome_reason = (
                str(payload.get("error") or payload.get("error_detail") or resolved).strip()
                or resolved
            )
            payload.update(
                _workflow_outcome_job_updates(
                    {**current_job, **payload}, outcome=resolved, outcome_reason=outcome_reason
                )
            )
            try:
                self.deps.record_workflow_outcome(
                    _workflow_outcome_metrics_payload(current_job, payload)
                )
            except Exception:  # policy: allowed-broad-except
                _log.warning(
                    "workflow outcome metrics failed for job %s", self.job_id, exc_info=True
                )
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
                status_event = self.deps.append_chat_event(
                    self.job_id,
                    event_type,
                    {
                        "status": resolved,
                        "step": payload.get("step"),
                        "reply": payload.get("reply"),
                        "error": payload.get("error"),
                        "error_detail": payload.get("error_detail"),
                        "skill_id_requested": payload.get("skill_id_requested"),
                        "skill_id_effective": payload.get("skill_id_effective"),
                        "skill_reason": payload.get("skill_reason"),
                        "skill_confidence": payload.get("skill_confidence"),
                        "skill_candidates": payload.get("skill_candidates"),
                    },
                )
                _persist_execution_timeline(self.job_id, status_event, self.deps)
            except Exception:  # policy: allowed-broad-except
                _log.warning(
                    "failed to append status event %s for job %s",
                    event_type,
                    self.job_id,
                    exc_info=True,
                )
        self.current_status = resolved
        return True


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
    except Exception as exc:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        status_writer.transition(
            "failed",
            {"error": "invalid_request", "error_detail": str(exc)[:200]},
        )
        return None


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

        reply_text, role_hint, last_user_text, duration_ms, pause = (
            _compute_reply_with_runtime_events(
                job_id=job_id,
                job=job,
                req=req,
                deps=deps,
            )
        )
        if pause:
            _persist_confirmation_pause(job_id=job_id, pause=pause, deps=deps)
            return
        user_turn_persisted = bool(job.get("user_turn_persisted"))
        (
            persisted_ok,
            teacher_id,
            teacher_session_id,
            student_session_id,
        ) = _persist_history_by_role(
            job_id=job_id,
            job=job,
            req=req,
            role_hint=role_hint,
            reply_text=reply_text,
            last_user_text=last_user_text,
            user_turn_persisted=user_turn_persisted,
            deps=deps,
            status_writer=status_writer,
        )
        if not persisted_ok:
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
        _run_post_done_side_effects_by_role(
            req=req,
            job=job,
            role_hint=role_hint,
            teacher_id=teacher_id,
            teacher_session_id=teacher_session_id,
            student_session_id=student_session_id,
            last_user_text=last_user_text,
            reply_text=reply_text,
            deps=deps,
        )
    finally:
        deps.release_lockfile(claim_path)
