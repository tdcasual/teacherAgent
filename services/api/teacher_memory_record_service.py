from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class TeacherMemoryRecordDeps:
    ensure_teacher_workspace: Callable[[str], Any]
    teacher_workspace_dir: Callable[[str], Any]
    teacher_session_file: Callable[[str, str], Any]
    load_teacher_sessions_index: Callable[[str], List[Dict[str, Any]]]
    save_teacher_sessions_index: Callable[[str, List[Dict[str, Any]]], None]
    session_index_max_items: int
    now_iso: Callable[[], str]
    norm_text: Callable[[str], str]
    loose_match: Callable[[str, str], bool]
    conflicts: Callable[[str, str], bool]
    auto_infer_enabled: bool
    auto_infer_min_chars: int
    auto_infer_block_patterns: Sequence[Any]
    temporary_hint_patterns: Sequence[Any]
    auto_infer_stable_patterns: Sequence[Any]
    auto_infer_lookback_turns: int
    auto_infer_min_repeats: int
    auto_max_proposals_per_day: int
    proposal_path: Callable[[str, str], Any]
    atomic_write_json: Callable[[Any, Any], None]


def teacher_memory_recent_proposals(teacher_id: str, *, deps: TeacherMemoryRecordDeps, limit: int = 200) -> List[Dict[str, Any]]:
    deps.ensure_teacher_workspace(teacher_id)
    proposals_dir = deps.teacher_workspace_dir(teacher_id) / "proposals"
    if not proposals_dir.exists():
        return []
    take = max(1, min(int(limit or 200), 1000))
    files = sorted(
        proposals_dir.glob("*.json"),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    )
    out: List[Dict[str, Any]] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if "proposal_id" not in data:
            data["proposal_id"] = path.stem
        out.append(data)
        if len(out) >= take:
            break
    return out


def teacher_memory_recent_user_turns(
    teacher_id: str,
    session_id: str,
    *,
    deps: TeacherMemoryRecordDeps,
    limit: int = 24,
) -> List[str]:
    path = deps.teacher_session_file(teacher_id, session_id)
    if not path.exists():
        return []
    take = max(1, min(int(limit or 24), 120))
    out: List[str] = []
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in reversed(lines):
        text = str(line or "").strip()
        if not text:
            continue
        try:
            rec = json.loads(text)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        if str(rec.get("role") or "") != "user":
            continue
        if bool(rec.get("synthetic")):
            continue
        content = str(rec.get("content") or "").strip()
        if not content:
            continue
        out.append(content[:400])
        if len(out) >= take:
            break
    out.reverse()
    return out


def teacher_memory_auto_infer_candidate(
    teacher_id: str,
    session_id: str,
    user_text: str,
    *,
    deps: TeacherMemoryRecordDeps,
) -> Optional[Dict[str, Any]]:
    if not deps.auto_infer_enabled:
        return None
    text = str(user_text or "").strip()
    norm = deps.norm_text(text)
    if len(norm) < deps.auto_infer_min_chars:
        return None
    if any(p.search(text) for p in deps.auto_infer_block_patterns):
        return None
    if any(p.search(text) for p in deps.temporary_hint_patterns):
        return None
    if not any(p.search(text) for p in deps.auto_infer_stable_patterns):
        return None
    history = teacher_memory_recent_user_turns(
        teacher_id,
        session_id,
        deps=deps,
        limit=deps.auto_infer_lookback_turns,
    )
    similar_hits = 0
    for prior in history:
        if deps.loose_match(text, prior):
            similar_hits += 1
    if similar_hits < deps.auto_infer_min_repeats:
        return None
    return {
        "target": "MEMORY",
        "title": "自动记忆：老师默认偏好",
        "content": text[:1200].strip(),
        "trigger": "implicit_repeated_preference",
        "similar_hits": similar_hits,
    }


def teacher_session_index_item(teacher_id: str, session_id: str, *, deps: TeacherMemoryRecordDeps) -> Dict[str, Any]:
    for item in deps.load_teacher_sessions_index(teacher_id):
        if str(item.get("session_id") or "") == str(session_id):
            return item
    return {}


def mark_teacher_session_memory_flush(teacher_id: str, session_id: str, cycle_no: int, *, deps: TeacherMemoryRecordDeps) -> None:
    items = deps.load_teacher_sessions_index(teacher_id)
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
    found["memory_flush_at"] = now
    found["memory_flush_cycle"] = max(1, int(cycle_no or 1))
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    deps.save_teacher_sessions_index(teacher_id, items[: deps.session_index_max_items])


def teacher_memory_find_conflicting_applied(
    teacher_id: str,
    *,
    proposal_id: str,
    target: str,
    content: str,
    deps: TeacherMemoryRecordDeps,
) -> List[str]:
    if str(target or "").upper() != "MEMORY":
        return []
    out: List[str] = []
    for rec in teacher_memory_recent_proposals(teacher_id, deps=deps, limit=500):
        rid = str(rec.get("proposal_id") or "").strip()
        if not rid or rid == proposal_id:
            continue
        if str(rec.get("status") or "").strip().lower() != "applied":
            continue
        if str(rec.get("target") or "").strip().upper() != "MEMORY":
            continue
        if rec.get("superseded_by"):
            continue
        old_content = str(rec.get("content") or "")
        if deps.conflicts(content, old_content):
            out.append(rid)
    return out


def teacher_memory_mark_superseded(
    teacher_id: str,
    proposal_ids: List[str],
    by_proposal_id: str,
    *,
    deps: TeacherMemoryRecordDeps,
) -> None:
    if not proposal_ids:
        return
    stamp = deps.now_iso()
    for pid in proposal_ids:
        path = deps.proposal_path(teacher_id, pid)
        if not path.exists():
            continue
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            rec = {}
        if not isinstance(rec, dict):
            continue
        rec["superseded_at"] = stamp
        rec["superseded_by"] = str(by_proposal_id or "")
        deps.atomic_write_json(path, rec)


def teacher_memory_auto_quota_reached(teacher_id: str, *, deps: TeacherMemoryRecordDeps) -> bool:
    if deps.auto_max_proposals_per_day <= 0:
        return False
    today = datetime.now().date().isoformat()
    count = 0
    for rec in teacher_memory_recent_proposals(teacher_id, deps=deps, limit=300):
        created_at = str(rec.get("created_at") or "")
        if not created_at.startswith(today):
            continue
        status = str(rec.get("status") or "").strip().lower()
        if status not in {"proposed", "applied"}:
            continue
        source = str(rec.get("source") or "").strip().lower()
        if not source.startswith("auto_"):
            continue
        count += 1
        if count >= deps.auto_max_proposals_per_day:
            return True
    return False


def teacher_memory_find_duplicate(
    teacher_id: str,
    *,
    target: str,
    content: str,
    dedupe_key: str,
    deps: TeacherMemoryRecordDeps,
) -> Optional[Dict[str, Any]]:
    target_norm = str(target or "MEMORY").upper()
    content_norm = deps.norm_text(content)
    for rec in teacher_memory_recent_proposals(teacher_id, deps=deps, limit=300):
        status = str(rec.get("status") or "").strip().lower()
        if status not in {"proposed", "applied"}:
            continue
        rec_key = str(rec.get("dedupe_key") or "").strip()
        if rec_key and rec_key == dedupe_key:
            return rec
        rec_target = str(rec.get("target") or "").upper()
        if rec_target != target_norm:
            continue
        rec_content_norm = deps.norm_text(str(rec.get("content") or ""))
        if content_norm and rec_content_norm and rec_content_norm == content_norm:
            return rec
    return None


def teacher_session_compaction_cycle_no(teacher_id: str, session_id: str, *, deps: TeacherMemoryRecordDeps) -> int:
    item = teacher_session_index_item(teacher_id, session_id, deps=deps)
    try:
        runs = int(item.get("compaction_runs") or 0)
    except Exception:
        runs = 0
    return max(1, runs + 1)
