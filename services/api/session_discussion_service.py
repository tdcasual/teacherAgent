from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionDiscussionDeps:
    marker: str
    load_student_sessions_index: Callable[[str], List[Dict[str, Any]]]
    student_session_file: Callable[[str, str], Path]


def _session_ids(student_id: str, assignment_id: str, *, deps: SessionDiscussionDeps) -> List[str]:
    session_ids: List[str] = [assignment_id]
    try:
        for item in deps.load_student_sessions_index(student_id):
            if item.get("assignment_id") != assignment_id:
                continue
            sid = str(item.get("session_id") or "").strip()
            if sid and sid not in session_ids:
                session_ids.append(sid)
    except Exception:
        _log.warning("failed to load session index for student=%s", student_id, exc_info=True)
    return session_ids


def _default_discussion_result(assignment_id: str) -> Dict[str, Any]:
    return {
        "status": "not_started",
        "pass": False,
        "session_id": assignment_id,
        "message_count": 0,
    }


def _scan_session_file(path: Path, *, session_id: str, marker: str) -> Dict[str, Any]:
    passed = False
    message_count = 0
    last_ts = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                _log.debug("JSON parse failed", exc_info=True)
                continue
            if not isinstance(obj, dict):
                continue
            message_count += 1
            ts = str(obj.get("ts") or "")
            if ts:
                last_ts = ts
            if str(obj.get("role") or "") == "assistant":
                content = str(obj.get("content") or "")
                if marker and marker in content:
                    passed = True
    return {
        "status": "pass" if passed else "in_progress",
        "pass": passed,
        "session_id": session_id,
        "message_count": message_count,
        "last_ts": last_ts,
    }


def _is_better_discussion_result(candidate: Dict[str, Any], current: Dict[str, Any]) -> bool:
    if bool(candidate.get("pass")) and not bool(current.get("pass")):
        return True
    return bool(candidate.get("pass")) == bool(current.get("pass")) and int(candidate.get("message_count") or 0) > int(
        current.get("message_count") or 0
    )


def session_discussion_pass(student_id: str, assignment_id: str, *, deps: SessionDiscussionDeps) -> Dict[str, Any]:
    best = _default_discussion_result(assignment_id)
    for sid in _session_ids(student_id, assignment_id, deps=deps):
        path = deps.student_session_file(student_id, sid)
        if not path.exists():
            continue

        try:
            candidate = _scan_session_file(path, session_id=sid, marker=deps.marker)
            if _is_better_discussion_result(candidate, best):
                best = candidate
        except Exception:
            _log.warning("failed to read session file %s for student=%s", path, student_id, exc_info=True)
            continue

    return best
