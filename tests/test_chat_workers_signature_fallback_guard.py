"""Guardrails for removing signature-driven compatibility fallbacks in chat/workers."""

from __future__ import annotations

from pathlib import Path

TARGET_FILES = {
    "services/api/chat_runtime_service.py",
    "services/api/tool_dispatch_service.py",
    "services/api/agent_service.py",
    "services/api/chat_job_processing_service.py",
    "services/api/workers/chat_worker_service.py",
    "services/api/workers/upload_worker_service.py",
    "services/api/workers/exam_worker_service.py",
    "services/api/workers/profile_update_worker_service.py",
}

# Strict guard: all target files must stay free from signature/fallback compatibility shims.
ALLOWED_OFFENDERS: set[str] = set()

BANNED_SNIPPETS = (
    "inspect.signature(",
    "_is_signature_mismatch_type_error(",
    "_type_error_originates_inside_callable(",
    "_supports_limit_cursor_keywords(",
    "_event_wait_supports_timeout(",
    "_run_agent_supports_event_sink(",
    "Signature introspection failed; keep legacy",
    "compatibility fallback",
)


def _has_banned_pattern(text: str) -> bool:
    return any(snippet in text for snippet in BANNED_SNIPPETS)


def test_no_new_signature_fallback_spread_in_chat_workers() -> None:
    offenders: set[str] = set()
    for rel in sorted(TARGET_FILES):
        text = Path(rel).read_text(encoding="utf-8", errors="ignore")
        if _has_banned_pattern(text):
            offenders.add(rel)

    unexpected = sorted(offenders - ALLOWED_OFFENDERS)
    assert unexpected == [], f"unexpected signature/fallback compatibility patterns: {unexpected}"
