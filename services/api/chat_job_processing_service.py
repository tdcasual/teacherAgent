from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .chat_execution_timeline_service import append_chat_execution_timeline
from .chat_job_state_machine import (
    is_terminal_chat_job_status,
    normalize_chat_job_status,
    transition_chat_job_status,
)

_log = logging.getLogger(__name__)
_ASSISTANT_DELTA_COALESCE_WINDOW_SEC = 0.04
_ASSISTANT_DELTA_COALESCE_MAX_CHARS = 96


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
    teacher_workflow_preflight: Callable[[Any, str, str, str], Optional[str]] = _default_teacher_workflow_preflight
    resolve_teacher_workflow: Callable[[Any, str, str, str], Dict[str, Any]] = _default_resolve_teacher_workflow


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
    return any(token in content for token in cn_tokens) or any(token in lowered for token in ("pdf", "xlsx", "xls", "ocr"))


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
        requested_skill_id
        and effective_skill_id
        and requested_skill_id != effective_skill_id
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


def _workflow_resolution_job_updates(payload: Dict[str, Any]) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    requested = str(payload.get("requested_skill_id") or "").strip()
    effective = str(payload.get("effective_skill_id") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if requested or "requested_skill_id" in payload:
        updates["skill_id_requested"] = requested
    if effective:
        updates["skill_id_effective"] = effective
    if reason:
        updates["skill_reason"] = reason
    confidence_raw = payload.get("confidence")
    if confidence_raw is not None:
        try:
            updates["skill_confidence"] = float(confidence_raw)
        except Exception:  # policy: allowed-broad-except
            _log.warning("numeric conversion failed", exc_info=True)
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        updates["skill_candidates"] = candidates
    resolution_mode = str(payload.get("resolution_mode") or "").strip()
    if resolution_mode:
        updates["skill_resolution_mode"] = resolution_mode
    if payload.get("auto_selected") is not None:
        updates["skill_auto_selected"] = bool(payload.get("auto_selected"))
    if payload.get("requested_rewritten") is not None:
        updates["skill_requested_rewritten"] = bool(payload.get("requested_rewritten"))
    return updates


def _workflow_outcome_job_updates(job: Dict[str, Any], *, outcome: str, outcome_reason: str | None = None) -> Dict[str, Any]:
    requested = str(job.get('skill_id_requested') or '').strip()
    effective = str(job.get('skill_id_effective') or '').strip()
    reason = str(job.get('skill_reason') or '').strip()
    if not requested and not effective and not reason:
        return {}
    final_reason = str(outcome_reason or '').strip() or str(outcome or '').strip() or 'unknown'
    return {
        'skill_outcome': str(outcome or '').strip() or 'unknown',
        'skill_outcome_reason': final_reason,
    }


def _workflow_resolution_metrics_payload(job: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    request_payload = job.get('request') if isinstance(job.get('request'), dict) else {}
    return {
        'role': str(job.get('role') or request_payload.get('role') or '').strip() or None,
        'requested_skill_id': str(payload.get('requested_skill_id') or '').strip(),
        'effective_skill_id': str(payload.get('effective_skill_id') or '').strip(),
        'reason': str(payload.get('reason') or '').strip(),
        'confidence': payload.get('confidence'),
        'resolution_mode': str(payload.get('resolution_mode') or '').strip() or None,
        'auto_selected': bool(payload.get('auto_selected')) if payload.get('auto_selected') is not None else False,
        'requested_rewritten': bool(payload.get('requested_rewritten')) if payload.get('requested_rewritten') is not None else False,
    }


def _workflow_outcome_metrics_payload(job: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    request_payload = job.get('request') if isinstance(job.get('request'), dict) else {}
    return {
        'role': str(job.get('role') or request_payload.get('role') or payload.get('role') or '').strip() or None,
        'requested_skill_id': str(payload.get('skill_id_requested') or job.get('skill_id_requested') or '').strip(),
        'effective_skill_id': str(payload.get('skill_id_effective') or job.get('skill_id_effective') or '').strip(),
        'reason': str(payload.get('skill_reason') or job.get('skill_reason') or '').strip(),
        'resolution_mode': str(payload.get('skill_resolution_mode') or job.get('skill_resolution_mode') or '').strip() or None,
        'outcome': str(payload.get('skill_outcome') or job.get('skill_outcome') or '').strip() or 'unknown',
        'outcome_reason': str(payload.get('skill_outcome_reason') or job.get('skill_outcome_reason') or '').strip() or 'unknown',
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
    resolution_payload = _normalize_workflow_resolution_payload(requested_skill_id, effective_skill_id, {})
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


def _persist_execution_timeline(job_id: str, event: Dict[str, Any], deps: ChatJobProcessDeps) -> None:
    try:
        job = deps.load_chat_job(job_id)
    except Exception:
        job = {}
    timeline = append_chat_execution_timeline(job.get('execution_timeline'), event)
    deps.write_chat_job(job_id, {'execution_timeline': timeline})


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
        deps.diag_log("teacher_chat.workflow_preflight_reply", {"reply_preview": workflow_preflight[:500]})
        return workflow_preflight
    preflight = deps.teacher_assignment_preflight(req)
    if preflight:
        deps.diag_log("teacher_chat.preflight_reply", {"reply_preview": preflight[:500]})
        return preflight
    return None




def _merge_teacher_extra_system(teacher_context: Optional[str], workflow_payload: Dict[str, Any]) -> Optional[str]:
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
    teacher_id = deps.resolve_teacher_id(teacher_id_override or req.teacher_id)
    teacher_context = deps.teacher_build_context(teacher_id, last_user_text, 6000, str(session_id or "main"))
    return (
        _merge_teacher_extra_system(teacher_context, workflow_payload or {}),
        teacher_id,
    )


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
    if not extra_parts:
        return None
    return "\n\n".join(extra_parts)


def _with_attachment_context(
    extra_system: Optional[str], attachment_context: str
) -> Optional[str]:
    attachment = str(attachment_context or "").strip()
    if not attachment:
        return extra_system
    attachment_block = f"【附件上下文】\n{attachment}"
    return f"{extra_system}\n\n{attachment_block}".strip() if extra_system else attachment_block


def _cap_extra_system(text: Optional[str], *, max_chars: int) -> Optional[str]:
    if text and len(text) > max_chars:
        return text[:max_chars] + "…"
    return text


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
    teacher_workflow = deps.resolve_teacher_workflow(
        req,
        effective_skill_id,
        last_user_text,
        attachment_context,
    ) or {}
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
    extra_system = _with_attachment_context(extra_system, attachment_context)
    return _cap_extra_system(
        extra_system,
        max_chars=deps.chat_extra_system_max_chars,
    ), effective_teacher_id


def _build_run_agent_kwargs(
    req: Any,
    *,
    extra_system: Optional[str],
    effective_teacher_id: Optional[str],
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]],
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
) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, Optional[str], str]]]:
    run_agent_kwargs = _build_run_agent_kwargs(
        req,
        extra_system=extra_system,
        effective_teacher_id=effective_teacher_id,
        event_sink=event_sink,
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
    )
    if blocked_reply:
        return blocked_reply

    assert result is not None
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
    record_workflow_resolution: Callable[[Dict[str, Any]], None] = (
        lambda _payload: None
    )
    record_workflow_outcome: Callable[[Dict[str, Any]], None] = (
        lambda _payload: None
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
        current_job: Dict[str, Any] = {}
        if resolved in {"done", "failed", "cancelled"}:
            try:
                current_job = self.deps.load_chat_job(self.job_id)
            except Exception:
                current_job = {}
            outcome_reason = str(payload.get('error') or payload.get('error_detail') or resolved).strip() or resolved
            payload.update(_workflow_outcome_job_updates({**current_job, **payload}, outcome=resolved, outcome_reason=outcome_reason))
            try:
                self.deps.record_workflow_outcome(_workflow_outcome_metrics_payload(current_job, payload))
            except Exception:  # policy: allowed-broad-except
                _log.warning("workflow outcome metrics failed for job %s", self.job_id, exc_info=True)
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
    assistant_done_event = deps.append_chat_event(job_id, "assistant.done", {"text": str(reply_text or "")})
    _persist_execution_timeline(job_id, assistant_done_event, deps)


class _BufferedRuntimeEventWriter:
    def __init__(self, *, job_id: str, deps: ChatJobProcessDeps, event_state: Dict[str, bool]) -> None:
        self.job_id = job_id
        self.deps = deps
        self.event_state = event_state
        self._delta_parts: List[str] = []
        self._delta_chars = 0
        self._last_flush_ts = float(self.deps.monotonic())

    def _append(self, event_type: str, payload: Dict[str, Any]) -> None:
        try:
            runtime_event = self.deps.append_chat_event(self.job_id, event_type, payload)
            if event_type != "assistant.delta":
                _persist_execution_timeline(self.job_id, runtime_event, self.deps)
            if event_type == "assistant.done":
                self.event_state["assistant_done"] = True
            elif event_type == "workflow.resolved":
                updates = _workflow_resolution_job_updates(payload)
                if updates:
                    self.deps.write_chat_job(self.job_id, updates)
                try:
                    job = self.deps.load_chat_job(self.job_id)
                except Exception:
                    job = {}
                try:
                    self.deps.record_workflow_resolution(_workflow_resolution_metrics_payload(job, payload))
                except Exception:  # policy: allowed-broad-except
                    _log.warning("workflow resolution metrics failed for job %s", self.job_id, exc_info=True)
        except Exception:  # policy: allowed-broad-except
            _log.warning(
                "failed to append runtime event %s for job %s",
                event_type,
                self.job_id,
                exc_info=True,
            )

    def _flush_delta(self) -> None:
        if not self._delta_parts:
            return
        text = "".join(self._delta_parts)
        self._delta_parts = []
        self._delta_chars = 0
        self._append("assistant.delta", {"delta": text})

    def emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        event_name = str(event_type or "")
        body = payload if isinstance(payload, dict) else {}
        if event_name == "assistant.delta":
            delta = str(body.get("delta") or "")
            if not delta:
                return
            self._delta_parts.append(delta)
            self._delta_chars += len(delta)
            now = float(self.deps.monotonic())
            should_flush = self._delta_chars >= _ASSISTANT_DELTA_COALESCE_MAX_CHARS
            if not should_flush:
                should_flush = (now - self._last_flush_ts) >= _ASSISTANT_DELTA_COALESCE_WINDOW_SEC
            if should_flush:
                self._flush_delta()
                self._last_flush_ts = now
            return

        self._flush_delta()
        self._append(event_name, body)
        self._last_flush_ts = float(self.deps.monotonic())

    def flush(self) -> None:
        self._flush_delta()


def _call_compute_chat_reply_sync(
    *,
    deps: ChatJobProcessDeps,
    req: Any,
    session_id: str,
    teacher_id_override: Optional[str],
    event_sink: Callable[[str, Dict[str, Any]], None],
) -> Tuple[str, Optional[str], str]:
    return deps.compute_chat_reply_sync(
        req,
        session_id=session_id,
        teacher_id_override=teacher_id_override,
        event_sink=event_sink,
    )


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
    except Exception as exc:  # policy: allowed-broad-except
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
    except Exception as exc:  # policy: allowed-broad-except
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
    except Exception as exc:  # policy: allowed-broad-except
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
    except Exception as exc:  # policy: allowed-broad-except
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
            source="chat_job_post_done",
            provenance={"layer": "session_context", "origin": "chat_job", "session_id": session_id},
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
    except Exception as exc:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "teacher.memory.auto_intent.failed",
            {"teacher_id": teacher_id, "session_id": session_id, "error": str(exc)[:200]},
        )
    try:
        auto_flush = deps.teacher_memory_auto_flush_from_session(
            teacher_id,
            session_id=session_id,
            source="chat_job_post_done",
            provenance={"layer": "session_summary", "origin": "chat_job", "session_id": session_id},
        )
        if auto_flush.get("created"):
            deps.diag_log(
                "teacher.memory.auto_flush.proposed",
                {
                    "teacher_id": teacher_id,
                    "session_id": session_id,
                    "proposal_id": auto_flush.get("proposal_id"),
                },
            )
    except Exception as exc:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "teacher.memory.auto_flush.failed",
            {"teacher_id": teacher_id, "session_id": session_id, "error": str(exc)[:200]},
        )
    try:
        deps.maybe_compact_teacher_session(teacher_id, session_id)
    except Exception as exc:  # policy: allowed-broad-except
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
    assignment_id = str(getattr(req, "assignment_id", "") or "").strip()
    request_id = str(job.get("request_id") or "")
    _run_student_turn_auto_propose(
        deps=deps,
        teacher_id=teacher_id,
        student_id=student_id,
        session_id=session_id,
        last_user_text=last_user_text,
        reply_text=reply_text,
        request_id=request_id,
    )
    if assignment_id:
        _run_student_assignment_evidence_auto_propose(
            deps=deps,
            teacher_id=teacher_id,
            student_id=student_id,
            assignment_id=assignment_id,
            request_id=request_id,
        )


def _run_student_turn_auto_propose(
    *,
    deps: ChatJobProcessDeps,
    teacher_id: str,
    student_id: str,
    session_id: str,
    last_user_text: str,
    reply_text: str,
    request_id: str,
) -> None:
    try:
        auto = deps.student_memory_auto_propose_from_turn(
            teacher_id=teacher_id or None,
            student_id=student_id,
            session_id=str(session_id or ""),
            user_text=last_user_text,
            assistant_text=reply_text,
            request_id=request_id,
            source="chat_job_post_done",
            provenance={"layer": "session_context", "origin": "chat_job", "session_id": str(session_id or "")},
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
    except Exception as exc:  # policy: allowed-broad-except
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


def _extract_student_assignment_evidence(
    progress: Dict[str, Any],
    *,
    student_id: str,
) -> Optional[Dict[str, Any]]:
    if not isinstance(progress, dict) or not bool(progress.get("ok")):
        return None
    student_items = progress.get("students")
    if not isinstance(student_items, list):
        return None
    student_payload = next(
        (
            item
            for item in student_items
            if isinstance(item, dict) and str(item.get("student_id") or "").strip() == student_id
        ),
        None,
    )
    if not isinstance(student_payload, dict):
        return None
    evidence = student_payload.get("evidence")
    return evidence if isinstance(evidence, dict) else None


def _run_student_assignment_evidence_auto_propose(
    *,
    deps: ChatJobProcessDeps,
    teacher_id: str,
    student_id: str,
    assignment_id: str,
    request_id: str,
) -> None:
    try:
        progress = deps.compute_assignment_progress(assignment_id, True)
        evidence = _extract_student_assignment_evidence(progress, student_id=student_id)
        if evidence is None:
            return
        auto_evidence = deps.student_memory_auto_propose_from_assignment_evidence(
            teacher_id=teacher_id or None,
            student_id=student_id,
            assignment_id=assignment_id,
            evidence=evidence,
            request_id=request_id or None,
            source="chat_job_post_done",
            provenance={"layer": "tool_data", "origin": "assignment_progress", "assignment_id": assignment_id},
        )
        if auto_evidence.get("created"):
            deps.diag_log(
                "student.memory.assignment_evidence.proposed",
                {
                    "teacher_id": str(auto_evidence.get("teacher_id") or teacher_id),
                    "student_id": student_id,
                    "assignment_id": assignment_id,
                    "proposal_id": auto_evidence.get("proposal_id"),
                    "memory_type": auto_evidence.get("memory_type"),
                },
            )
    except Exception as exc:  # policy: allowed-broad-except
        _log.warning("operation failed", exc_info=True)
        deps.diag_log(
            "student.memory.assignment_evidence.failed",
            {
                "teacher_id": teacher_id,
                "student_id": student_id,
                "assignment_id": assignment_id,
                "error": str(exc)[:200],
            },
        )


def _compute_reply_with_runtime_events(
    *,
    job_id: str,
    job: Dict[str, Any],
    req: Any,
    deps: ChatJobProcessDeps,
) -> Tuple[str, Optional[str], str, int]:
    t0 = deps.monotonic()
    event_state = {"assistant_done": False}
    runtime_event_writer = _BufferedRuntimeEventWriter(
        job_id=job_id,
        deps=deps,
        event_state=event_state,
    )

    def _event_sink(event_type: str, payload: Dict[str, Any]) -> None:
        runtime_event_writer.emit(event_type, payload)

    try:
        reply_text, role_hint, last_user_text = _call_compute_chat_reply_sync(
            deps=deps,
            req=req,
            session_id=str(job.get("session_id") or "main"),
            teacher_id_override=str(job.get("teacher_id") or "").strip() or None,
            event_sink=_event_sink,
        )
    finally:
        runtime_event_writer.flush()

    if not event_state["assistant_done"]:
        _emit_assistant_reply_events(job_id=job_id, reply_text=reply_text, deps=deps)

    duration_ms = int((deps.monotonic() - t0) * 1000)
    return reply_text, role_hint, last_user_text, duration_ms


def _persist_history_by_role(
    *,
    job_id: str,
    job: Dict[str, Any],
    req: Any,
    role_hint: Optional[str],
    reply_text: str,
    last_user_text: str,
    user_turn_persisted: bool,
    deps: ChatJobProcessDeps,
    status_writer: _ChatJobStatusWriter,
) -> Tuple[bool, str, str, str]:
    teacher_id = ""
    teacher_session_id = ""
    student_session_id = str(job.get("session_id") or "")

    if role_hint == "teacher":
        persisted_ok, teacher_id, teacher_session_id = _persist_teacher_history(
            job_id,
            job,
            req,
            reply_text=reply_text,
            last_user_text=last_user_text,
            user_turn_persisted=user_turn_persisted,
            deps=deps,
            status_writer=status_writer,
        )
        return persisted_ok, teacher_id, teacher_session_id, student_session_id

    if role_hint == "student" and req.student_id:
        _update_student_profile_safe(
            req, last_user_text=last_user_text, reply_text=reply_text, deps=deps
        )
        student_session_id = student_session_id or deps.resolve_student_session_id(
            req.student_id,
            req.assignment_id,
            req.assignment_date,
        )
        persisted_ok = _persist_student_history(
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
            return False, teacher_id, teacher_session_id, student_session_id

    return True, teacher_id, teacher_session_id, student_session_id


def _run_post_done_side_effects_by_role(
    *,
    req: Any,
    job: Dict[str, Any],
    role_hint: Optional[str],
    teacher_id: str,
    teacher_session_id: str,
    student_session_id: str,
    last_user_text: str,
    reply_text: str,
    deps: ChatJobProcessDeps,
) -> None:
    if role_hint == "teacher":
        _run_teacher_post_done_side_effects(
            teacher_id,
            teacher_session_id,
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

        reply_text, role_hint, last_user_text, duration_ms = _compute_reply_with_runtime_events(
            job_id=job_id,
            job=job,
            req=req,
            deps=deps,
        )
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
