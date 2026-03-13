from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List

_log = logging.getLogger(__name__)



@dataclass(frozen=True)
class TeacherSessionCompactionDeps:
    compact_enabled: bool
    compact_main_only: bool
    compact_max_messages: int
    compact_keep_tail: int
    chat_max_messages_teacher: int
    teacher_compact_allowed: Callable[[str, str], bool]
    teacher_session_file: Callable[[str, str], Any]
    teacher_compact_summary: Callable[[List[Dict[str, Any]], str], str]
    write_teacher_session_records: Callable[[Any, List[Dict[str, Any]]], None]
    mark_teacher_session_compacted: Callable[[str, str, int, int], None]
    diag_log: Callable[[str, Dict[str, Any]], None]


def _load_session_records(path: Any) -> tuple[List[str], List[Dict[str, Any]]]:
    raw_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    records: List[Dict[str, Any]] = []
    for line in raw_lines:
        text = (line or "").strip()
        if not text:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            _log.debug("JSON parse failed", exc_info=True)
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return raw_lines, records


def _dialog_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        record
        for record in records
        if str(record.get("role") or "") in {"user", "assistant"} and not bool(record.get("synthetic"))
    ]


def _resolve_keep_tail(dialog_count: int, deps: TeacherSessionCompactionDeps) -> int:
    keep_tail = min(max(1, deps.compact_keep_tail), dialog_count)
    return min(keep_tail, max(1, deps.chat_max_messages_teacher - 1))


def _find_previous_summary(records: List[Dict[str, Any]]) -> str:
    for record in reversed(records):
        if record.get("kind") == "session_summary":
            return str(record.get("content") or "").strip()
    return ""


def _build_summary_record(
    summary_text: str,
    *,
    compacted_messages: int,
    keep_tail: int,
) -> Dict[str, Any]:
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "role": "assistant",
        "content": f"【会话压缩摘要】\n{summary_text}",
        "kind": "session_summary",
        "synthetic": True,
        "compacted_messages": compacted_messages,
        "keep_tail": keep_tail,
    }


def maybe_compact_teacher_session(
    teacher_id: str,
    session_id: str,
    *,
    deps: TeacherSessionCompactionDeps,
) -> Dict[str, Any]:
    if not deps.compact_enabled:
        return {"ok": False, "reason": "disabled"}
    if deps.compact_main_only and str(session_id) != "main":
        return {"ok": False, "reason": "main_only"}
    if not deps.teacher_compact_allowed(teacher_id, session_id):
        return {"ok": False, "reason": "cooldown"}

    path = deps.teacher_session_file(teacher_id, session_id)
    if not path.exists():
        return {"ok": False, "reason": "session_not_found"}

    raw_lines, records = _load_session_records(path)
    if not raw_lines:
        return {"ok": False, "reason": "empty"}
    dialog = _dialog_records(records)
    if len(dialog) <= deps.compact_max_messages:
        return {"ok": False, "reason": "below_threshold", "messages": len(dialog)}

    keep_tail = _resolve_keep_tail(len(dialog), deps)
    head = dialog[:-keep_tail]
    tail = dialog[-keep_tail:]
    if not head:
        return {"ok": False, "reason": "nothing_to_compact"}

    summary_text = deps.teacher_compact_summary(head, _find_previous_summary(records))
    summary_record = _build_summary_record(
        summary_text,
        compacted_messages=len(head),
        keep_tail=keep_tail,
    )
    new_records = [summary_record] + tail
    deps.write_teacher_session_records(path, new_records)
    deps.mark_teacher_session_compacted(
        teacher_id,
        session_id,
        len(head),
        len(new_records),
    )
    deps.diag_log(
        "teacher.session.compacted",
        {
            "teacher_id": teacher_id,
            "session_id": session_id,
            "compacted_messages": len(head),
            "tail_messages": len(tail),
        },
    )
    return {
        "ok": True,
        "teacher_id": teacher_id,
        "session_id": session_id,
        "compacted_messages": len(head),
        "tail_messages": len(tail),
    }
