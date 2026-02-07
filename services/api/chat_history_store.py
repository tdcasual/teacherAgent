from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _default_now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass(frozen=True)
class ChatHistoryStoreDeps:
    student_sessions_dir: Path
    teacher_sessions_dir: Path
    safe_fs_id: Callable[[str, str], str]
    atomic_write_json: Callable[[Path, Any], None]
    now_iso: Callable[[], str] = _default_now_iso
    session_index_max_items: int = 500


def student_sessions_base_dir(student_id: str, deps: ChatHistoryStoreDeps) -> Path:
    return deps.student_sessions_dir / deps.safe_fs_id(student_id, prefix="student")


def student_sessions_index_path(student_id: str, deps: ChatHistoryStoreDeps) -> Path:
    return student_sessions_base_dir(student_id, deps) / "index.json"


def student_session_view_state_path(student_id: str, deps: ChatHistoryStoreDeps) -> Path:
    return student_sessions_base_dir(student_id, deps) / "view_state.json"


def student_session_file(student_id: str, session_id: str, deps: ChatHistoryStoreDeps) -> Path:
    safe_session = deps.safe_fs_id(session_id or "main", prefix="session")
    return student_sessions_base_dir(student_id, deps) / f"{safe_session}.jsonl"


def teacher_sessions_base_dir(teacher_id: str, deps: ChatHistoryStoreDeps) -> Path:
    return deps.teacher_sessions_dir / deps.safe_fs_id(teacher_id, prefix="teacher")


def teacher_sessions_index_path(teacher_id: str, deps: ChatHistoryStoreDeps) -> Path:
    return teacher_sessions_base_dir(teacher_id, deps) / "index.json"


def teacher_session_view_state_path(teacher_id: str, deps: ChatHistoryStoreDeps) -> Path:
    return teacher_sessions_base_dir(teacher_id, deps) / "view_state.json"


def teacher_session_file(teacher_id: str, session_id: str, deps: ChatHistoryStoreDeps) -> Path:
    safe_session = deps.safe_fs_id(session_id or "main", prefix="session")
    return teacher_sessions_base_dir(teacher_id, deps) / f"{safe_session}.jsonl"


def load_student_sessions_index(student_id: str, deps: ChatHistoryStoreDeps) -> List[Dict[str, Any]]:
    path = student_sessions_index_path(student_id, deps)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def save_student_sessions_index(student_id: str, items: List[Dict[str, Any]], deps: ChatHistoryStoreDeps) -> None:
    path = student_sessions_index_path(student_id, deps)
    deps.atomic_write_json(path, items)


def load_teacher_sessions_index(teacher_id: str, deps: ChatHistoryStoreDeps) -> List[Dict[str, Any]]:
    path = teacher_sessions_index_path(teacher_id, deps)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def save_teacher_sessions_index(teacher_id: str, items: List[Dict[str, Any]], deps: ChatHistoryStoreDeps) -> None:
    path = teacher_sessions_index_path(teacher_id, deps)
    deps.atomic_write_json(path, items)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _index_cap(deps: ChatHistoryStoreDeps) -> int:
    return max(1, _to_int(deps.session_index_max_items, 500))


def update_student_session_index(
    student_id: str,
    session_id: str,
    assignment_id: Optional[str],
    date_str: Optional[str],
    preview: str,
    message_increment: int,
    deps: ChatHistoryStoreDeps,
) -> None:
    items = load_student_sessions_index(student_id, deps)
    now = deps.now_iso()
    found: Optional[Dict[str, Any]] = None
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
    found["message_count"] = _to_int(found.get("message_count"), 0)
    inc = _to_int(message_increment, 0)
    if inc:
        found["message_count"] = max(0, _to_int(found.get("message_count"), 0) + inc)
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    save_student_sessions_index(student_id, items[: _index_cap(deps)], deps)


def append_student_session_message(
    student_id: str,
    session_id: str,
    role: str,
    content: str,
    meta: Optional[Dict[str, Any]],
    deps: ChatHistoryStoreDeps,
) -> None:
    base = student_sessions_base_dir(student_id, deps)
    base.mkdir(parents=True, exist_ok=True)
    path = student_session_file(student_id, session_id, deps)
    record: Dict[str, Any] = {"ts": deps.now_iso(), "role": role, "content": content}
    if meta:
        record.update(meta)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def update_teacher_session_index(
    teacher_id: str,
    session_id: str,
    preview: str,
    message_increment: int,
    deps: ChatHistoryStoreDeps,
) -> None:
    items = load_teacher_sessions_index(teacher_id, deps)
    now = deps.now_iso()
    found: Optional[Dict[str, Any]] = None
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
    found["message_count"] = _to_int(found.get("message_count"), 0)
    inc = _to_int(message_increment, 0)
    if inc:
        found["message_count"] = max(0, _to_int(found.get("message_count"), 0) + inc)
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    save_teacher_sessions_index(teacher_id, items[: _index_cap(deps)], deps)


def append_teacher_session_message(
    teacher_id: str,
    session_id: str,
    role: str,
    content: str,
    meta: Optional[Dict[str, Any]],
    deps: ChatHistoryStoreDeps,
) -> None:
    base = teacher_sessions_base_dir(teacher_id, deps)
    base.mkdir(parents=True, exist_ok=True)
    path = teacher_session_file(teacher_id, session_id, deps)
    record: Dict[str, Any] = {"ts": deps.now_iso(), "role": role, "content": content}
    if meta:
        record.update(meta)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
