from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional


_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherContextTextDeps:
    teacher_session_file: Callable[[str, str], Any]
    teacher_workspace_file: Callable[[str, str], Any]
    teacher_read_text: Callable[..., str]
    teacher_memory_active_applied_records: Callable[[str, Optional[str], int], List[Dict[str, Any]]]
    teacher_memory_rank_score: Callable[[Dict[str, Any]], float]
    teacher_memory_context_max_entries: int
    log: Any = _log


def teacher_session_summary_text(
    teacher_id: str,
    session_id: str,
    max_chars: int,
    *,
    teacher_session_file: Callable[[str, str], Any],
    log: Any = _log,
) -> str:
    if max_chars <= 0:
        return ""
    try:
        path = teacher_session_file(teacher_id, session_id)
    except Exception:
        log.debug("Failed to resolve session file path for teacher=%s session=%s", teacher_id, session_id)
        return ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for _idx, line in zip(range(5), handle):
                line = str(line or "").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    log.debug("Skipping non-JSON line in session file %s", path)
                    continue
                if isinstance(obj, dict) and obj.get("kind") == "session_summary":
                    summary = str(obj.get("content") or "").strip()
                    return (summary[:max_chars] + "…") if max_chars and len(summary) > max_chars else summary
                break
    except Exception:
        log.warning("Failed to read session file %s for summary", path, exc_info=True)
        return ""
    return ""


def build_teacher_session_summary_reader(
    *,
    teacher_session_file: Callable[[str, str], Any],
    log: Any = _log,
) -> Callable[[str, str, int], str]:
    def _reader(teacher_id: str, session_id: str, max_chars: int) -> str:
        return teacher_session_summary_text(
            teacher_id,
            session_id,
            max_chars,
            teacher_session_file=teacher_session_file,
            log=log,
        )

    return _reader


def build_teacher_memory_context_reader(
    *,
    teacher_memory_active_applied_records: Callable[[str, Optional[str], int], List[Dict[str, Any]]],
    teacher_read_text: Callable[..., str],
    teacher_workspace_file: Callable[[str, str], Any],
    teacher_memory_rank_score: Callable[[Dict[str, Any]], float],
    teacher_memory_context_max_entries: int,
) -> Callable[[str, int], str]:
    def _reader(teacher_id: str, max_chars: int = 4000) -> str:
        return teacher_memory_context_text(
            teacher_id,
            max_chars=max_chars,
            teacher_memory_active_applied_records=teacher_memory_active_applied_records,
            teacher_read_text=teacher_read_text,
            teacher_workspace_file=teacher_workspace_file,
            teacher_memory_rank_score=teacher_memory_rank_score,
            teacher_memory_context_max_entries=teacher_memory_context_max_entries,
        )

    return _reader


def teacher_memory_context_text(
    teacher_id: str,
    max_chars: int = 4000,
    *,
    teacher_memory_active_applied_records: Callable[[str, Optional[str], int], List[Dict[str, Any]]],
    teacher_read_text: Callable[..., str],
    teacher_workspace_file: Callable[[str, str], Any],
    teacher_memory_rank_score: Callable[[Dict[str, Any]], float],
    teacher_memory_context_max_entries: int,
) -> str:
    if max_chars <= 0:
        return ""
    active = teacher_memory_active_applied_records(
        teacher_id,
        target="MEMORY",
        limit=teacher_memory_context_max_entries,
    )
    if not active:
        return teacher_read_text(teacher_workspace_file(teacher_id, "MEMORY.md"), max_chars=max_chars).strip()

    lines: List[str] = []
    used = 0
    for rec in active:
        item_text = str(rec.get("content") or "").strip()
        if not item_text:
            continue
        brief = re.sub(r"\s+", " ", item_text).strip()[:240]
        score = int(round(teacher_memory_rank_score(rec)))
        source = str(rec.get("source") or "manual")
        line = f"- [{source}|{score}] {brief}"
        if used + len(line) > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines).strip()


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
