from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple

from fastapi import HTTPException

from ..api_models import ChatRequest, ChatResponse, ChatStartRequest
from ..chat_support_service import extract_diagnostic_signals
import logging
_log = logging.getLogger(__name__)



@dataclass
class ChatHandlerDeps:
    compute_chat_reply_sync: Callable[[ChatRequest], Tuple[str, Optional[str], str]]
    detect_math_delimiters: Callable[[str], bool]
    detect_latex_tokens: Callable[[str], bool]
    diag_log: Callable[[str, dict], None]
    build_interaction_note: Callable[..., str]
    enqueue_profile_update: Callable[[dict], None]
    student_profile_update: Callable[[dict], dict]
    profile_update_async: bool
    run_in_threadpool: Callable[..., Any]
    get_chat_status: Callable[[str], Any]
    start_chat_api: Callable[[ChatStartRequest], Any]


def _is_awaitable(value: Any) -> bool:
    return inspect.isawaitable(value)


async def chat(req: ChatRequest, *, deps: ChatHandlerDeps) -> ChatResponse:
    reply_text, role_hint, last_user_text = await deps.run_in_threadpool(deps.compute_chat_reply_sync, req)
    if role_hint == "student" and req.student_id and reply_text != "正在生成上一条回复，请稍候再试。":
        try:
            has_math = deps.detect_math_delimiters(reply_text)
            has_latex = deps.detect_latex_tokens(reply_text)
            deps.diag_log(
                "student_chat.out",
                {
                    "student_id": req.student_id,
                    "assignment_id": req.assignment_id,
                    "has_math_delim": has_math,
                    "has_latex_tokens": has_latex,
                    "reply_preview": reply_text[:500],
                },
            )
            note = deps.build_interaction_note(last_user_text, reply_text, assignment_id=req.assignment_id)
            payload: dict = {"student_id": req.student_id, "interaction_note": note}
            # Layer 1: rule-based diagnostic signal extraction.
            signals = extract_diagnostic_signals(reply_text)
            if signals.weak_kp:
                payload["weak_kp"] = ",".join(signals.weak_kp)
            if signals.strong_kp:
                payload["strong_kp"] = ",".join(signals.strong_kp)
            if signals.next_focus:
                payload["next_focus"] = signals.next_focus
            if deps.profile_update_async:
                deps.enqueue_profile_update(payload)
            else:
                await deps.run_in_threadpool(deps.student_profile_update, payload)
        except Exception as exc:
            _log.debug("operation failed", exc_info=True)
            deps.diag_log("student.profile.update_failed", {"student_id": req.student_id, "error": str(exc)[:200]})
    return ChatResponse(reply=reply_text, role=role_hint)


async def chat_start(req: ChatStartRequest, *, deps: ChatHandlerDeps) -> Any:
    result = deps.start_chat_api(req)
    if _is_awaitable(result):
        return await result
    return result


async def chat_status(job_id: str, *, deps: ChatHandlerDeps) -> Any:
    try:
        result = deps.get_chat_status(job_id)
        if _is_awaitable(result):
            return await result
        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="job not found")
