from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .fs_atomic import atomic_write_json

_log = logging.getLogger(__name__)


def parse_iso_ts(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        _log.debug("unparseable ISO timestamp: %s", raw)
        return None


def compare_iso_ts(a: Any, b: Any) -> int:
    left = parse_iso_ts(a)
    right = parse_iso_ts(b)
    if left and right:
        if left > right:
            return 1
        if left < right:
            return -1
        return 0
    if left and not right:
        return 1
    if right and not left:
        return -1
    return 0


def default_session_view_state() -> Dict[str, Any]:
    return {
        "title_map": {},
        "hidden_ids": [],
        "active_session_id": "",
        "updated_at": "",
    }


def normalize_session_view_state_payload(raw: Any) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    title_map_raw = data.get("title_map") if isinstance(data.get("title_map"), dict) else {}
    title_map: Dict[str, str] = {}
    for key, value in title_map_raw.items():
        sid = str(key or "").strip()
        title = str(value or "").strip()
        if not sid or not title:
            continue
        title_map[sid[:200]] = title[:120]

    hidden_ids: List[str] = []
    seen_hidden: set[str] = set()
    hidden_raw = data.get("hidden_ids") if isinstance(data.get("hidden_ids"), list) else []
    for item in hidden_raw:
        sid = str(item or "").strip()
        if not sid:
            continue
        sid = sid[:200]
        if sid in seen_hidden:
            continue
        seen_hidden.add(sid)
        hidden_ids.append(sid)

    active_session_id = str(data.get("active_session_id") or "").strip()[:200]
    updated_at_raw = str(data.get("updated_at") or "").strip()
    updated_at = updated_at_raw if parse_iso_ts(updated_at_raw) else ""

    return {
        "title_map": title_map,
        "hidden_ids": hidden_ids,
        "active_session_id": active_session_id,
        "updated_at": updated_at,
    }


def load_session_view_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return default_session_view_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to read session view state from %s", path, exc_info=True)
        return default_session_view_state()
    return normalize_session_view_state_payload(data)


def save_session_view_state(path: Path, state: Dict[str, Any]) -> None:
    normalized = normalize_session_view_state_payload(state)
    if not normalized.get("updated_at"):
        normalized["updated_at"] = datetime.now().isoformat(timespec="milliseconds")
    atomic_write_json(path, normalized)
