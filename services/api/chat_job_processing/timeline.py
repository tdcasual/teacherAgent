from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List

from ..chat_execution_timeline_service import append_chat_execution_timeline

if TYPE_CHECKING:
    from ..chat_job_processing_service import ChatJobProcessDeps

_log = logging.getLogger(__name__)
_ASSISTANT_DELTA_COALESCE_WINDOW_SEC = 0.04
_ASSISTANT_DELTA_COALESCE_MAX_CHARS = 96


def _request_payload_dict(job: Dict[str, Any]) -> Dict[str, Any]:
    raw_request = job.get("request")
    return raw_request if isinstance(raw_request, dict) else {}


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


def _workflow_resolution_metrics_payload(
    job: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    request_payload = _request_payload_dict(job)
    return {
        "role": str(job.get("role") or request_payload.get("role") or "").strip() or None,
        "requested_skill_id": str(payload.get("requested_skill_id") or "").strip(),
        "effective_skill_id": str(payload.get("effective_skill_id") or "").strip(),
        "reason": str(payload.get("reason") or "").strip(),
        "confidence": payload.get("confidence"),
        "resolution_mode": str(payload.get("resolution_mode") or "").strip() or None,
        "auto_selected": (
            bool(payload.get("auto_selected"))
            if payload.get("auto_selected") is not None
            else False
        ),
        "requested_rewritten": (
            bool(payload.get("requested_rewritten"))
            if payload.get("requested_rewritten") is not None
            else False
        ),
    }


def _persist_execution_timeline(
    job_id: str, event: Dict[str, Any], deps: ChatJobProcessDeps
) -> None:
    try:
        job = deps.load_chat_job(job_id)
    except Exception:  # policy: allowed-broad-except
        job = {}
    timeline = append_chat_execution_timeline(job.get("execution_timeline"), event)
    deps.write_chat_job(job_id, {"execution_timeline": timeline})


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
    assistant_done_event = deps.append_chat_event(
        job_id, "assistant.done", {"text": str(reply_text or "")}
    )
    _persist_execution_timeline(job_id, assistant_done_event, deps)


class _BufferedRuntimeEventWriter:
    def __init__(
        self, *, job_id: str, deps: ChatJobProcessDeps, event_state: Dict[str, bool]
    ) -> None:
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
                except Exception:  # policy: allowed-broad-except
                    job = {}
                try:
                    self.deps.record_workflow_resolution(
                        _workflow_resolution_metrics_payload(job, payload)
                    )
                except Exception:  # policy: allowed-broad-except
                    _log.warning(
                        "workflow resolution metrics failed for job %s", self.job_id, exc_info=True
                    )
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
