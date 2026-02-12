from __future__ import annotations

import json
import logging
import os
import threading
import weakref
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import SESSION_INDEX_MAX_ITEMS
from .job_repository import _atomic_write_json
from .paths import (
    student_session_file,
    student_session_view_state_path,
    student_sessions_base_dir,
    student_sessions_index_path,
    teacher_session_file,
    teacher_session_view_state_path,
    teacher_sessions_base_dir,
    teacher_sessions_index_path,
)
from .session_view_state import (
    compare_iso_ts as _compare_iso_ts_impl,
    default_session_view_state as _default_session_view_state_impl,
    load_session_view_state as _load_session_view_state_impl,
    normalize_session_view_state_payload as _normalize_session_view_state_payload_impl,
    save_session_view_state as _save_session_view_state_impl,
)


# ---------------------------------------------------------------------------
# Module-level mutable state for per-path reentrant locks
# ---------------------------------------------------------------------------

_SESSION_INDEX_LOCKS: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
_SESSION_INDEX_LOCKS_LOCK = threading.Lock()
_log = logging.getLogger(__name__)


def reset_session_locks() -> None:
    """Reset per-path lock state. Called by runtime_state on tenant init."""
    global _SESSION_INDEX_LOCKS, _SESSION_INDEX_LOCKS_LOCK
    _SESSION_INDEX_LOCKS = weakref.WeakValueDictionary()
    _SESSION_INDEX_LOCKS_LOCK = threading.Lock()

_RESERVED_META_KEYS = {"ts", "role", "content"}


# ---------------------------------------------------------------------------
# Per-path reentrant lock
# ---------------------------------------------------------------------------

def _session_index_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _SESSION_INDEX_LOCKS_LOCK:
        lock = _SESSION_INDEX_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _SESSION_INDEX_LOCKS[key] = lock
        return lock


# ---------------------------------------------------------------------------
# Delegate helpers
# ---------------------------------------------------------------------------

def _compare_iso_ts(a: Any, b: Any) -> int:
    return _compare_iso_ts_impl(a, b)

def _default_session_view_state() -> Dict[str, Any]:
    return _default_session_view_state_impl()

def _normalize_session_view_state_payload(raw: Any) -> Dict[str, Any]:
    return _normalize_session_view_state_payload_impl(raw)


# ---------------------------------------------------------------------------
# Student session view state
# ---------------------------------------------------------------------------

def load_student_session_view_state(student_id: str) -> Dict[str, Any]:
    path = student_session_view_state_path(student_id)
    return _load_session_view_state_impl(path)

def save_student_session_view_state(student_id: str, state: Dict[str, Any]) -> None:
    path = student_session_view_state_path(student_id)
    _save_session_view_state_impl(path, state)


# ---------------------------------------------------------------------------
# Teacher session view state
# ---------------------------------------------------------------------------

def load_teacher_session_view_state(teacher_id: str) -> Dict[str, Any]:
    path = teacher_session_view_state_path(teacher_id)
    return _load_session_view_state_impl(path)

def save_teacher_session_view_state(teacher_id: str, state: Dict[str, Any]) -> None:
    path = teacher_session_view_state_path(teacher_id)
    _save_session_view_state_impl(path, state)


# ---------------------------------------------------------------------------
# Student sessions index
# ---------------------------------------------------------------------------

def load_student_sessions_index(student_id: str) -> List[Dict[str, Any]]:
    path = student_sessions_index_path(student_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, ValueError) as exc:
        _log.warning("corrupt student session index %s: %s", path, exc)
        return []
    return data if isinstance(data, list) else []

def save_student_sessions_index(student_id: str, items: List[Dict[str, Any]]) -> None:
    path = student_sessions_index_path(student_id)
    _atomic_write_json(path, items)

def update_student_session_index(
    student_id: str,
    session_id: str,
    assignment_id: Optional[str],
    date_str: Optional[str],
    preview: str,
    message_increment: int = 0,
) -> None:
    path = student_sessions_index_path(student_id)
    with _session_index_lock(path):
        items = load_student_sessions_index(student_id)
        now = datetime.now().isoformat(timespec="seconds")
        found = None
        for item in items:
            if item.get("session_id") == session_id:
                found = item
                break
        if found is None:
            found = {"session_id": session_id, "message_count": 0}
            items.append(found)
        found["updated_at"] = now
        if assignment_id is not None:
            found["assignment_id"] = assignment_id
        if date_str is not None:
            found["date"] = date_str
        if preview:
            found["preview"] = preview[:200]
        try:
            found["message_count"] = int(found.get("message_count") or 0)
        except Exception:
            _log.debug("numeric conversion failed", exc_info=True)
            found["message_count"] = 0
        try:
            inc = int(message_increment or 0)
        except Exception:
            _log.debug("numeric conversion failed", exc_info=True)
            inc = 0
        if inc:
            found["message_count"] = max(0, int(found.get("message_count") or 0) + inc)

        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        save_student_sessions_index(student_id, items[:SESSION_INDEX_MAX_ITEMS])

def append_student_session_message(
    student_id: str,
    session_id: str,
    role: str,
    content: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    base = student_sessions_base_dir(student_id)
    base.mkdir(parents=True, exist_ok=True)
    path = student_session_file(student_id, session_id)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "role": role,
        "content": content,
    }
    if meta:
        record.update({k: v for k, v in meta.items() if k not in _RESERVED_META_KEYS})
    line = json.dumps(record, ensure_ascii=False) + "\n"
    data = line.encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


# ---------------------------------------------------------------------------
# Teacher sessions index
# ---------------------------------------------------------------------------

def load_teacher_sessions_index(teacher_id: str) -> List[Dict[str, Any]]:
    path = teacher_sessions_index_path(teacher_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, ValueError) as exc:
        _log.warning("corrupt teacher session index %s: %s", path, exc)
        return []
    return data if isinstance(data, list) else []

def save_teacher_sessions_index(teacher_id: str, items: List[Dict[str, Any]]) -> None:
    path = teacher_sessions_index_path(teacher_id)
    _atomic_write_json(path, items)

def update_teacher_session_index(
    teacher_id: str,
    session_id: str,
    preview: str,
    message_increment: int = 0,
) -> None:
    path = teacher_sessions_index_path(teacher_id)
    with _session_index_lock(path):
        items = load_teacher_sessions_index(teacher_id)
        now = datetime.now().isoformat(timespec="seconds")
        found = None
        for item in items:
            if item.get("session_id") == session_id:
                found = item
                break
        if found is None:
            found = {"session_id": session_id, "message_count": 0}
            items.append(found)
        found["updated_at"] = now
        if preview:
            found["preview"] = preview[:200]
        try:
            found["message_count"] = int(found.get("message_count") or 0)
        except Exception:
            _log.debug("numeric conversion failed", exc_info=True)
            found["message_count"] = 0
        try:
            inc = int(message_increment or 0)
        except Exception:
            _log.debug("numeric conversion failed", exc_info=True)
            inc = 0
        if inc:
            found["message_count"] = max(0, int(found.get("message_count") or 0) + inc)

        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        save_teacher_sessions_index(teacher_id, items[:SESSION_INDEX_MAX_ITEMS])

def append_teacher_session_message(
    teacher_id: str,
    session_id: str,
    role: str,
    content: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    base = teacher_sessions_base_dir(teacher_id)
    base.mkdir(parents=True, exist_ok=True)
    path = teacher_session_file(teacher_id, session_id)
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "role": role,
        "content": content,
    }
    if meta:
        record.update({k: v for k, v in meta.items() if k not in _RESERVED_META_KEYS})
    line = json.dumps(record, ensure_ascii=False) + "\n"
    data = line.encode("utf-8")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
