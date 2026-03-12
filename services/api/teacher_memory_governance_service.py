from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherMemoryGovernanceDeps:
    recent_proposals: Callable[[str, int], List[Dict[str, Any]]]
    norm_text: Callable[[str], str]
    conflicts: Callable[[str, str], bool]
    now_iso: Callable[[], str]
    proposal_path: Callable[[str, str], Any]
    atomic_write_json: Callable[[Any, Any], None]
    auto_max_proposals_per_day: int



def teacher_memory_find_conflicting_applied(
    teacher_id: str,
    *,
    proposal_id: str,
    target: str,
    content: str,
    deps: TeacherMemoryGovernanceDeps,
) -> List[str]:
    if str(target or '').upper() != 'MEMORY':
        return []
    out: List[str] = []
    for rec in deps.recent_proposals(teacher_id, 500):
        rid = str(rec.get('proposal_id') or '').strip()
        if not rid or rid == proposal_id:
            continue
        if str(rec.get('status') or '').strip().lower() != 'applied':
            continue
        if str(rec.get('target') or '').strip().upper() != 'MEMORY':
            continue
        if rec.get('superseded_by'):
            continue
        old_content = str(rec.get('content') or '')
        if deps.conflicts(content, old_content):
            out.append(rid)
    return out



def teacher_memory_mark_superseded(
    teacher_id: str,
    proposal_ids: List[str],
    by_proposal_id: str,
    *,
    deps: TeacherMemoryGovernanceDeps,
) -> None:
    if not proposal_ids:
        return
    stamp = deps.now_iso()
    for pid in proposal_ids:
        path = deps.proposal_path(teacher_id, pid)
        if not path.exists():
            continue
        try:
            rec = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            _log.warning('failed to read proposal file for supersede teacher=%s proposal=%s', teacher_id, pid, exc_info=True)
            rec = {}
        if not isinstance(rec, dict):
            continue
        rec['superseded_at'] = stamp
        rec['superseded_by'] = str(by_proposal_id or '')
        deps.atomic_write_json(path, rec)



def teacher_memory_auto_quota_reached(teacher_id: str, *, deps: TeacherMemoryGovernanceDeps) -> bool:
    if deps.auto_max_proposals_per_day <= 0:
        return False
    today = str(deps.now_iso() or '').strip().split('T', 1)[0]
    if not today:
        return False
    count = 0
    for rec in deps.recent_proposals(teacher_id, 300):
        created_at = str(rec.get('created_at') or '')
        if not created_at.startswith(today):
            continue
        status = str(rec.get('status') or '').strip().lower()
        if status not in {'proposed', 'applied'}:
            continue
        source = str(rec.get('source') or '').strip().lower()
        if not source.startswith('auto_'):
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
    deps: TeacherMemoryGovernanceDeps,
) -> Optional[Dict[str, Any]]:
    target_norm = str(target or 'MEMORY').upper()
    content_norm = deps.norm_text(content)
    for rec in deps.recent_proposals(teacher_id, 300):
        status = str(rec.get('status') or '').strip().lower()
        if status not in {'proposed', 'applied'}:
            continue
        rec_key = str(rec.get('dedupe_key') or '').strip()
        if rec_key and rec_key == dedupe_key:
            return rec
        rec_target = str(rec.get('target') or '').upper()
        if rec_target != target_norm:
            continue
        rec_content_norm = deps.norm_text(str(rec.get('content') or ''))
        if content_norm and rec_content_norm and rec_content_norm == content_norm:
            return rec
    return None
