"""Teacher session compaction helpers extracted from teacher_memory_core.py.

Contains session compaction state, rate limiting, transcript building,
summary generation, and session record I/O.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import (
    TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC,
    TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS,
    SESSION_INDEX_MAX_ITEMS,
)
from .paths import safe_fs_id
from .session_store import (
    _session_index_lock,
    load_teacher_sessions_index,
    save_teacher_sessions_index,
)
from .paths import teacher_sessions_index_path

import logging

__all__ = [
    "_teacher_compact_key",
    "_teacher_compact_allowed",
    "_teacher_compact_reset_ts",
    "_teacher_compact_transcript",
    "_teacher_compact_summary",
    "_write_teacher_session_records",
    "_mark_teacher_session_compacted",
]

# Module-level mutable state (reset by runtime_state.py)
_TEACHER_SESSION_COMPACT_TS: Dict[str, float] = {}
_TEACHER_SESSION_COMPACT_LOCK = threading.Lock()
_COMPACT_TS_MAX_SIZE = 500
_log = logging.getLogger(__name__)


def reset_compact_state() -> None:
    """Reset compaction rate-limit state. Called by runtime_state on tenant init."""
    global _TEACHER_SESSION_COMPACT_TS, _TEACHER_SESSION_COMPACT_LOCK
    _TEACHER_SESSION_COMPACT_TS = {}
    _TEACHER_SESSION_COMPACT_LOCK = threading.Lock()


def _teacher_compact_key(teacher_id: str, session_id: str) -> str:
    return f"{safe_fs_id(teacher_id, prefix='teacher')}:{safe_fs_id(session_id, prefix='session')}"


def _teacher_compact_allowed(teacher_id: str, session_id: str) -> bool:
    key = _teacher_compact_key(teacher_id, session_id)
    if TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC <= 0:
        return True
    now = time.time()
    with _TEACHER_SESSION_COMPACT_LOCK:
        last = float(_TEACHER_SESSION_COMPACT_TS.get(key, 0.0) or 0.0)
        if now - last < TEACHER_SESSION_COMPACT_MIN_INTERVAL_SEC:
            return False
        _TEACHER_SESSION_COMPACT_TS[key] = now
        # Evict oldest entries when dict grows too large
        if len(_TEACHER_SESSION_COMPACT_TS) > _COMPACT_TS_MAX_SIZE:
            oldest = sorted(_TEACHER_SESSION_COMPACT_TS, key=_TEACHER_SESSION_COMPACT_TS.get)
            for k in oldest[: len(oldest) // 2]:
                del _TEACHER_SESSION_COMPACT_TS[k]
    return True


def _teacher_compact_reset_ts(teacher_id: str, session_id: str) -> None:
    """Call on compaction failure to allow immediate retry."""
    key = _teacher_compact_key(teacher_id, session_id)
    with _TEACHER_SESSION_COMPACT_LOCK:
        _TEACHER_SESSION_COMPACT_TS.pop(key, None)


def _teacher_compact_transcript(records: List[Dict[str, Any]], max_chars: int) -> str:
    parts: List[str] = []
    used = 0
    for rec in records:
        role = str(rec.get("role") or "").strip()
        if role not in {"user", "assistant"}:
            continue
        raw = str(rec.get("content") or "")
        content = re.sub(r"\s+", " ", raw).strip()
        if not content:
            continue
        tag = "老师" if role == "user" else "助理"
        line = f"{tag}: {content}"
        if used + len(line) > max_chars:
            remain = max(0, max_chars - used)
            if remain > 24:
                parts.append(line[:remain])
            break
        parts.append(line)
        used += len(line) + 1
    return "\n".join(parts).strip()


def _teacher_compact_summary(records: List[Dict[str, Any]], previous_summary: str) -> str:
    transcript = _teacher_compact_transcript(records, TEACHER_SESSION_COMPACT_MAX_SOURCE_CHARS)
    snippets: List[str] = []
    for line in transcript.splitlines():
        if not line.strip():
            continue
        snippets.append(f"- {line[:180]}")
        if len(snippets) >= 14:
            break
    parts: List[str] = []
    if previous_summary:
        parts.append("### 历史摘要")
        parts.append(previous_summary[:1800])
    parts.append("### 本轮新增摘要")
    if not snippets:
        snippets = ["- （无可摘要内容）"]
    parts.extend(snippets)
    return "\n".join(parts).strip()


def _write_teacher_session_records(path: Path, records: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        try:
            for rec in records:
                os.write(fd, (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        tmp.replace(path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


def _mark_teacher_session_compacted(
    teacher_id: str,
    session_id: str,
    compacted_messages: int,
    new_message_count: Optional[int] = None,
) -> None:
    path = teacher_sessions_index_path(teacher_id)
    with _session_index_lock(path):
        items = load_teacher_sessions_index(teacher_id)
        now = datetime.now().isoformat(timespec="seconds")
        found: Optional[Dict[str, Any]] = None
        for item in items:
            if item.get("session_id") == session_id:
                found = item
                break
        if found is None:
            found = {"session_id": session_id, "message_count": 0}
            items.append(found)
        found["updated_at"] = now
        found["compacted_at"] = now
        try:
            found["compaction_runs"] = int(found.get("compaction_runs") or 0) + 1
        except Exception as exc:
            _log.warning("_mark_teacher_session_compacted: bad compaction_runs, resetting: %s", exc)
            found["compaction_runs"] = 1
        try:
            found["compacted_messages"] = int(found.get("compacted_messages") or 0) + int(compacted_messages or 0)
        except Exception as exc:
            _log.warning("_mark_teacher_session_compacted: bad compacted_messages: %s", exc)
            found["compacted_messages"] = int(compacted_messages or 0)
        if new_message_count is not None:
            try:
                found["message_count"] = max(0, int(new_message_count))
            except Exception as exc:
                _log.warning("_mark_teacher_session_compacted: bad new_message_count: %s", exc)
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        save_teacher_sessions_index(teacher_id, items[:SESSION_INDEX_MAX_ITEMS])
