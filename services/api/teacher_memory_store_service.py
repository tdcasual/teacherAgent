from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherMemoryStoreDeps:
    teacher_workspace_dir: Callable[[str], Any]
    proposal_path: Callable[[str, str], Any]
    recent_proposals: Callable[[str, int], List[Dict[str, Any]]]
    is_expired_record: Callable[[Dict[str, Any], Optional[datetime]], bool]
    rank_score: Callable[[Dict[str, Any]], float]
    now_iso: Callable[[], str]


def teacher_memory_event_log_path(teacher_id: str, *, deps: TeacherMemoryStoreDeps) -> Any:
    base = deps.teacher_workspace_dir(teacher_id) / "telemetry"
    base.mkdir(parents=True, exist_ok=True)
    return base / "memory_events.jsonl"


def teacher_memory_log_event(
    teacher_id: str,
    event: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    deps: TeacherMemoryStoreDeps,
) -> None:
    rec: Dict[str, Any] = {
        "ts": deps.now_iso(),
        "event": str(event or "").strip() or "unknown",
    }
    if isinstance(payload, dict):
        for k, v in payload.items():
            if v is None:
                continue
            rec[str(k)] = v
    try:
        path = teacher_memory_event_log_path(teacher_id, deps=deps)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        _log.warning("failed to write memory event log for teacher=%s", teacher_id, exc_info=True)
        return


def teacher_memory_load_events(teacher_id: str, *, deps: TeacherMemoryStoreDeps, limit: int = 5000) -> List[Dict[str, Any]]:
    path = teacher_memory_event_log_path(teacher_id, deps=deps)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for raw in reversed(lines):
        line = str(raw or "").strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            _log.debug("skipping malformed JSONL line in event log for teacher=%s", teacher_id)
            continue
        if not isinstance(rec, dict):
            continue
        out.append(rec)
        if len(out) >= max(100, int(limit or 5000)):
            break
    out.reverse()
    return out


def teacher_memory_load_record(teacher_id: str, proposal_id: str, *, deps: TeacherMemoryStoreDeps) -> Optional[Dict[str, Any]]:
    path = deps.proposal_path(teacher_id, proposal_id)
    if not path.exists():
        return None
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        _log.warning("failed to read proposal file for teacher=%s proposal=%s", teacher_id, proposal_id, exc_info=True)
        return None
    if not isinstance(rec, dict):
        return None
    if "proposal_id" not in rec:
        rec["proposal_id"] = proposal_id
    return rec


def teacher_memory_active_applied_records(
    teacher_id: str,
    *,
    deps: TeacherMemoryStoreDeps,
    target: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    target_norm = str(target or "").strip().upper() or None
    out: List[Dict[str, Any]] = []
    now = datetime.now()
    for rec in deps.recent_proposals(teacher_id, max(200, limit * 4)):
        if str(rec.get("status") or "").strip().lower() != "applied":
            continue
        if rec.get("superseded_by"):
            continue
        rec_target = str(rec.get("target") or "").strip().upper()
        if target_norm and rec_target != target_norm:
            continue
        if deps.is_expired_record(rec, now):
            continue
        out.append(rec)
    out.sort(
        key=lambda r: (
            deps.rank_score(r),
            str(r.get("applied_at") or r.get("created_at") or ""),
        ),
        reverse=True,
    )
    return out[: max(1, int(limit or 200))]
