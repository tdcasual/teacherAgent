from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(frozen=True)
class TeacherContextDeps:
    ensure_teacher_workspace: Callable[[str], Any]
    teacher_read_text: Callable[..., str]
    teacher_workspace_file: Callable[[str, str], Any]
    teacher_memory_context_text: Callable[[str, int], str]
    include_session_summary: bool
    session_summary_max_chars: int
    teacher_session_summary_text: Callable[[str, str, int], str]
    teacher_memory_log_event: Callable[[str, str, Dict[str, Any]], None]


def build_teacher_context(
    teacher_id: str,
    *,
    deps: TeacherContextDeps,
    query: Optional[str] = None,
    max_chars: int = 6000,
    session_id: str = "main",
) -> str:
    deps.ensure_teacher_workspace(teacher_id)
    parts = []
    user_text = deps.teacher_read_text(
        deps.teacher_workspace_file(teacher_id, "USER.md"),
        max_chars=2000,
    ).strip()
    mem_text = deps.teacher_memory_context_text(teacher_id, 4000).strip()
    if user_text:
        parts.append("【Teacher Profile】\n" + user_text)
    if mem_text:
        parts.append("【Long-Term Memory】\n" + mem_text)
    if deps.include_session_summary:
        summary = deps.teacher_session_summary_text(
            teacher_id,
            str(session_id or "main"),
            deps.session_summary_max_chars,
        )
        if summary:
            parts.append("【Session Summary】\n" + summary)
    out = "\n\n".join(parts).strip()
    if max_chars and len(out) > max_chars:
        out = out[:max_chars] + "…"
    deps.teacher_memory_log_event(
        teacher_id,
        "context_injected",
        {
            "query_preview": str(query or "")[:80],
            "chars": len(out),
            "session_id": str(session_id or "main"),
        },
    )
    return out
