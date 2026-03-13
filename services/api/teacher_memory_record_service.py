from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from .teacher_memory_governance_service import (
    TeacherMemoryGovernanceDeps,
)
from .teacher_memory_governance_service import (
    teacher_memory_auto_quota_reached as _teacher_memory_auto_quota_reached_impl,
)
from .teacher_memory_governance_service import (
    teacher_memory_find_conflicting_applied as _teacher_memory_find_conflicting_applied_impl,
)
from .teacher_memory_governance_service import (
    teacher_memory_find_duplicate as _teacher_memory_find_duplicate_impl,
)
from .teacher_memory_governance_service import (
    teacher_memory_mark_superseded as _teacher_memory_mark_superseded_impl,
)

_log = logging.getLogger(__name__)


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
    proposals_dir = deps.teacher_workspace_dir(teacher_id) / 'proposals'
    if not proposals_dir.exists():
        return []
    take = max(1, min(int(limit or 200), 1000))
    files = sorted(
        proposals_dir.glob('*.json'),
        key=lambda path: path.stat().st_mtime if path.exists() else 0,
        reverse=True,
    )
    out: List[Dict[str, Any]] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            _log.warning('failed to read proposal file %s', path, exc_info=True)
            continue
        if not isinstance(data, dict):
            continue
        if 'proposal_id' not in data:
            data['proposal_id'] = path.stem
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
    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    for line in reversed(lines):
        text = str(line or '').strip()
        if not text:
            continue
        try:
            rec = json.loads(text)
        except Exception:
            _log.debug('skipping malformed JSONL line in session file for teacher=%s session=%s', teacher_id, session_id)
            continue
        if not isinstance(rec, dict):
            continue
        if str(rec.get('role') or '') != 'user':
            continue
        if bool(rec.get('synthetic')):
            continue
        content = str(rec.get('content') or '').strip()
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
    text = str(user_text or '').strip()
    norm = deps.norm_text(text)
    if len(norm) < deps.auto_infer_min_chars:
        return None
    if any(pattern.search(text) for pattern in deps.auto_infer_block_patterns):
        return None
    if any(pattern.search(text) for pattern in deps.temporary_hint_patterns):
        return None
    if not any(pattern.search(text) for pattern in deps.auto_infer_stable_patterns):
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
        'target': 'MEMORY',
        'title': '自动记忆：老师默认偏好',
        'content': text[:1200].strip(),
        'trigger': 'implicit_repeated_preference',
        'similar_hits': similar_hits,
    }



def teacher_session_index_item(teacher_id: str, session_id: str, *, deps: TeacherMemoryRecordDeps) -> Dict[str, Any]:
    for item in deps.load_teacher_sessions_index(teacher_id):
        if str(item.get('session_id') or '') == str(session_id):
            return item
    return {}



def mark_teacher_session_memory_flush(teacher_id: str, session_id: str, cycle_no: int, *, deps: TeacherMemoryRecordDeps) -> None:
    items = deps.load_teacher_sessions_index(teacher_id)
    now = deps.now_iso()
    found: Optional[Dict[str, Any]] = None
    for item in items:
        if item.get('session_id') == session_id:
            found = item
            break
    if found is None:
        found = {'session_id': session_id, 'message_count': 0}
        items.append(found)
    found['updated_at'] = now
    found['memory_flush_at'] = now
    found['memory_flush_cycle'] = max(1, int(cycle_no or 1))
    items.sort(key=lambda item: item.get('updated_at') or '', reverse=True)
    deps.save_teacher_sessions_index(teacher_id, items[: deps.session_index_max_items])



def _governance_deps(deps: TeacherMemoryRecordDeps) -> TeacherMemoryGovernanceDeps:
    return TeacherMemoryGovernanceDeps(
        recent_proposals=lambda teacher_id, limit: teacher_memory_recent_proposals(teacher_id, deps=deps, limit=limit),
        norm_text=deps.norm_text,
        conflicts=deps.conflicts,
        now_iso=deps.now_iso,
        proposal_path=deps.proposal_path,
        atomic_write_json=deps.atomic_write_json,
        auto_max_proposals_per_day=deps.auto_max_proposals_per_day,
    )



def teacher_memory_find_conflicting_applied(
    teacher_id: str,
    *,
    proposal_id: str,
    target: str,
    content: str,
    deps: TeacherMemoryRecordDeps,
) -> List[str]:
    return _teacher_memory_find_conflicting_applied_impl(
        teacher_id,
        proposal_id=proposal_id,
        target=target,
        content=content,
        deps=_governance_deps(deps),
    )



def teacher_memory_mark_superseded(
    teacher_id: str,
    proposal_ids: List[str],
    by_proposal_id: str,
    *,
    deps: TeacherMemoryRecordDeps,
) -> None:
    _teacher_memory_mark_superseded_impl(
        teacher_id,
        proposal_ids,
        by_proposal_id,
        deps=_governance_deps(deps),
    )



def teacher_memory_auto_quota_reached(teacher_id: str, *, deps: TeacherMemoryRecordDeps) -> bool:
    return _teacher_memory_auto_quota_reached_impl(teacher_id, deps=_governance_deps(deps))



def teacher_memory_find_duplicate(
    teacher_id: str,
    *,
    target: str,
    content: str,
    dedupe_key: str,
    deps: TeacherMemoryRecordDeps,
) -> Optional[Dict[str, Any]]:
    return _teacher_memory_find_duplicate_impl(
        teacher_id,
        target=target,
        content=content,
        dedupe_key=dedupe_key,
        deps=_governance_deps(deps),
    )



def teacher_session_compaction_cycle_no(teacher_id: str, session_id: str, *, deps: TeacherMemoryRecordDeps) -> int:
    item = teacher_session_index_item(teacher_id, session_id, deps=deps)
    try:
        runs = int(item.get('compaction_runs') or 0)
    except Exception:
        _log.debug('non-integer compaction_runs for teacher=%s session=%s', teacher_id, session_id)
        runs = 0
    return max(1, runs + 1)
