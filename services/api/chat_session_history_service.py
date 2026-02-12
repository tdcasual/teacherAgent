from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

_log = logging.getLogger(__name__)



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
    mode = (direction or "backward").strip().lower()
    if mode not in {"forward", "backward"}:
        mode = "backward"

    if mode == "forward":
        start = max(0, int(cursor))
        messages: List[Dict[str, Any]] = []
        next_cursor = start
        with path.open("r", encoding="utf-8") as handle:
            for idx, line in enumerate(handle):
                if idx < start:
                    continue
                if len(messages) >= take:
                    break
                line = (line or "").strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    _log.debug("JSON parse failed", exc_info=True)
                    continue
                if isinstance(obj, dict):
                    messages.append(obj)
                next_cursor = idx + 1
        return {"messages": messages, "next_cursor": next_cursor}

    lines = path.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    end = total if int(cursor) < 0 else max(0, min(int(cursor), total))
    messages_rev: List[Dict[str, Any]] = []
    min_idx = end
    for idx in range(end - 1, -1, -1):
        if len(messages_rev) >= take:
            break
        line = (lines[idx] or "").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            _log.debug("JSON parse failed", exc_info=True)
            continue
        if isinstance(obj, dict):
            messages_rev.append(obj)
            min_idx = idx
    messages = list(reversed(messages_rev))
    next_cursor = max(0, int(min_idx))
    return {"messages": messages, "next_cursor": next_cursor}
