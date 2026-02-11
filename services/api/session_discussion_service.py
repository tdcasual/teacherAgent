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


def session_discussion_pass(student_id: str, assignment_id: str, *, deps: SessionDiscussionDeps) -> Dict[str, Any]:
    marker = deps.marker

    # Prefer assignment_id as session_id. If missing, fall back to any session indexed to this assignment.
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

    best = {"status": "not_started", "pass": False, "session_id": assignment_id, "message_count": 0}
    for sid in session_ids:
        path = deps.student_session_file(student_id, sid)
        if not path.exists():
            continue

        passed = False
        message_count = 0
        last_ts = ""
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    message_count += 1
                    ts = str(obj.get("ts") or "")
                    if ts:
                        last_ts = ts
                    # Only trust assistant output for completion markers to avoid student "self-pass".
                    if str(obj.get("role") or "") == "assistant":
                        content = str(obj.get("content") or "")
                        if marker and marker in content:
                            passed = True

            cur = {
                "status": "pass" if passed else "in_progress",
                "pass": passed,
                "session_id": sid,
                "message_count": message_count,
                "last_ts": last_ts,
            }
            # Choose a "better" session: pass beats in_progress/not_started; otherwise prefer more messages.
            if bool(cur["pass"]) and not bool(best.get("pass")):
                best = cur
            elif bool(cur["pass"]) == bool(best.get("pass")) and int(cur["message_count"]) > int(best.get("message_count") or 0):
                best = cur
        except Exception:
            _log.warning("failed to read session file %s for student=%s", path, student_id, exc_info=True)
            continue

    return best
