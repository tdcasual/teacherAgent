from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, MutableMapping, Optional


@contextmanager
def acquire_limiters(limiter: Any) -> Iterator[None]:
    semas: List[Any]
    if isinstance(limiter, (list, tuple)):
        semas = []
        seen: set[int] = set()
        for sema in limiter:
            sema_id = id(sema)
            if sema_id in seen:
                continue
            seen.add(sema_id)
            semas.append(sema)
    else:
        semas = [limiter]
    acquired: List[Any] = []
    for sema in semas:
        sema.acquire()
        acquired.append(sema)
    try:
        yield
    finally:
        for sema in reversed(acquired):
            sema.release()


def trim_messages(
    messages: List[Dict[str, Any]],
    *,
    role_hint: Optional[str],
    max_messages: int,
    max_messages_student: int,
    max_messages_teacher: int,
    max_chars: int,
) -> List[Dict[str, Any]]:
    if not messages:
        return []
    if role_hint == "student":
        keep = max_messages_student
    elif role_hint == "teacher":
        keep = max_messages_teacher
    else:
        keep = max_messages
    trimmed: List[Dict[str, Any]] = []
    for msg in messages[-keep:]:
        role = msg.get("role")
        content = msg.get("content") or ""
        if isinstance(content, str) and len(content) > max_chars:
            content = content[:max_chars] + "…"
        trimmed.append({"role": role, "content": content})
    return trimmed


@contextmanager
def student_inflight_guard(
    *,
    student_id: Optional[str],
    inflight: MutableMapping[str, int],
    lock: Any,
    limit: int,
) -> Iterator[bool]:
    if not student_id:
        yield True
        return
    allowed = True
    with lock:
        cur = int(inflight.get(student_id, 0) or 0)
        if cur >= int(limit):
            allowed = False
        else:
            inflight[student_id] = cur + 1
    try:
        yield allowed
    finally:
        if not allowed:
            return
        with lock:
            cur = int(inflight.get(student_id, 0) or 0)
            if cur <= 1:
                inflight.pop(student_id, None)
            else:
                inflight[student_id] = cur - 1
