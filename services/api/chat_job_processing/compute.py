from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .confirm import _prepare_confirm_resume_convo
from .timeline import _BufferedRuntimeEventWriter, _emit_assistant_reply_events

if TYPE_CHECKING:
    from ..chat_job_processing_service import ChatJobProcessDeps


def _call_compute_chat_reply_sync(
    *,
    deps: ChatJobProcessDeps,
    req: Any,
    session_id: str,
    teacher_id_override: Optional[str],
    event_sink: Callable[[str, Dict[str, Any]], None],
    extra_out: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    lane_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    initial_convo: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, Optional[str], str]:
    return deps.compute_chat_reply_sync(
        req,
        session_id=session_id,
        teacher_id_override=teacher_id_override,
        event_sink=event_sink,
        extra_out=extra_out,
        job_id=job_id,
        lane_id=lane_id,
        actor_id=actor_id,
        initial_convo=initial_convo,
    )


def _compute_reply_with_runtime_events(
    *,
    job_id: str,
    job: Dict[str, Any],
    req: Any,
    deps: ChatJobProcessDeps,
) -> Tuple[str, Optional[str], str, int, Optional[Dict[str, Any]]]:
    t0 = deps.monotonic()
    event_state = {"assistant_done": False}
    runtime_event_writer = _BufferedRuntimeEventWriter(
        job_id=job_id,
        deps=deps,
        event_state=event_state,
    )

    def _event_sink(event_type: str, payload: Dict[str, Any]) -> None:
        runtime_event_writer.emit(event_type, payload)

    extra_out: Dict[str, Any] = {}
    initial_convo = _prepare_confirm_resume_convo(job)
    if initial_convo is not None:
        deps.write_chat_job(
            job_id,
            {
                "confirm_pending": None,
                "confirm_resume_result": None,
            },
        )
    try:
        reply_text, role_hint, last_user_text = _call_compute_chat_reply_sync(
            deps=deps,
            req=req,
            session_id=str(job.get("session_id") or "main"),
            teacher_id_override=str(job.get("teacher_id") or "").strip() or None,
            event_sink=_event_sink,
            extra_out=extra_out,
            job_id=job_id,
            lane_id=str(job.get("lane_id") or "").strip() or None,
            actor_id=str(job.get("teacher_id") or "").strip() or None,
            initial_convo=initial_convo,
        )
    finally:
        runtime_event_writer.flush()

    pause = extra_out if str(extra_out.get("pause") or "") == "confirmation_required" else None
    if pause:
        duration_ms = int((deps.monotonic() - t0) * 1000)
        return reply_text, role_hint, last_user_text, duration_ms, pause

    if not event_state["assistant_done"]:
        _emit_assistant_reply_events(job_id=job_id, reply_text=reply_text, deps=deps)

    duration_ms = int((deps.monotonic() - t0) * 1000)
    return reply_text, role_hint, last_user_text, duration_ms, None
