from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)


def _normalize_direction(direction: str) -> str:
    mode = (direction or "backward").strip().lower()
    return mode if mode in {"forward", "backward"} else "backward"


def _parse_message_line(line: str) -> Optional[Dict[str, Any]]:
    text = (line or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        _log.debug("JSON parse failed", exc_info=True)
        return None
    return obj if isinstance(obj, dict) else None


def _load_forward_messages(path: Any, *, start: int, take: int) -> Tuple[List[Dict[str, Any]], int]:
    messages: List[Dict[str, Any]] = []
    next_cursor = start
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle):
            if idx < start:
                continue
            if len(messages) >= take:
                break
            parsed = _parse_message_line(line)
            if parsed is None:
                continue
            messages.append(parsed)
            next_cursor = idx + 1
    return messages, next_cursor


def _load_backward_messages(path: Any, *, end: int, take: int) -> Tuple[List[Dict[str, Any]], int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    end_idx = total if end < 0 else max(0, min(int(end), total))
    messages_rev: List[Dict[str, Any]] = []
    min_idx = end_idx
    for idx in range(end_idx - 1, -1, -1):
        if len(messages_rev) >= take:
            break
        parsed = _parse_message_line(lines[idx])
        if parsed is None:
            continue
        messages_rev.append(parsed)
        min_idx = idx
    return list(reversed(messages_rev)), max(0, int(min_idx))


def load_session_messages(
    path: Any,
    *,
    cursor: int = -1,
    limit: int = 50,
    direction: str = "backward",
) -> Dict[str, Any]:
    if not path.exists():
        return {"messages": [], "next_cursor": cursor}

    take = max(1, min(int(limit), 200))
    mode = _normalize_direction(direction)
    if mode == "forward":
        messages, next_cursor = _load_forward_messages(path, start=max(0, int(cursor)), take=take)
        return {"messages": messages, "next_cursor": next_cursor}

    messages, next_cursor = _load_backward_messages(path, end=int(cursor), take=take)
    return {"messages": messages, "next_cursor": next_cursor}
