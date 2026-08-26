from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

if TYPE_CHECKING:
    from ..chat_job_processing_service import ChatJobProcessDeps, _ChatJobStatusWriter

_log = logging.getLogger(__name__)


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
            provenance={
                "layer": "session_context",
                "origin": "chat_job",
                "session_id": str(session_id or ""),
            },
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
            provenance={
                "layer": "tool_data",
                "origin": "assignment_progress",
                "assignment_id": assignment_id,
            },
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
