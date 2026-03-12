from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .teacher_memory_propose_service import _teacher_memory_provenance

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TeacherMemoryStorageDeps:
    ensure_teacher_workspace: Callable[[str], Any]
    teacher_workspace_dir: Callable[[str], Any]
    safe_fs_id: Callable[..., str]
    atomic_write_json: Callable[[Any, Any], None]
    now_iso: Callable[[], str]
    teacher_daily_memory_path: Callable[[str], Any]
    teacher_workspace_file: Callable[[str, str], Any]
    log_event: Callable[[str, str, Dict[str, Any]], None]



def teacher_proposal_path(teacher_id: str, proposal_id: str, *, deps: TeacherMemoryStorageDeps) -> Any:
    deps.ensure_teacher_workspace(teacher_id)
    base = deps.teacher_workspace_dir(teacher_id) / 'proposals'
    return base / f"{deps.safe_fs_id(proposal_id, prefix='proposal')}.json"



def ensure_teacher_memory_provenance(rec: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(rec, dict):
        return {}
    provenance = rec.get('provenance') if isinstance(rec.get('provenance'), dict) else None
    if provenance:
        return provenance
    source = str(rec.get('source') or 'manual').strip().lower() or 'manual'
    meta = rec.get('meta') if isinstance(rec.get('meta'), dict) else None
    provenance = _teacher_memory_provenance(source, meta)
    rec['provenance'] = provenance
    return provenance



def teacher_memory_list_proposals(
    teacher_id: str,
    *,
    deps: TeacherMemoryStorageDeps,
    status: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    deps.ensure_teacher_workspace(teacher_id)
    proposals_dir = deps.teacher_workspace_dir(teacher_id) / 'proposals'
    proposals_dir.mkdir(parents=True, exist_ok=True)
    status_norm = (status or '').strip().lower() or None
    if status_norm and status_norm not in {'proposed', 'applied', 'rejected'}:
        return {'ok': False, 'error': 'invalid_status', 'teacher_id': teacher_id}

    def _safe_mtime(path: Any) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    take = max(1, min(int(limit or 20), 200))
    files = sorted(proposals_dir.glob('*.json'), key=_safe_mtime, reverse=True)
    items: List[Dict[str, Any]] = []
    for path in files:
        try:
            rec = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            _log.warning('failed to read proposal file %s', path, exc_info=True)
            continue
        if not isinstance(rec, dict):
            continue
        rec_status = str(rec.get('status') or '').strip().lower()
        if rec_status == 'deleted':
            continue
        if status_norm and rec_status != status_norm:
            continue
        if 'proposal_id' not in rec:
            rec['proposal_id'] = path.stem
        ensure_teacher_memory_provenance(rec)
        items.append(rec)
        if len(items) >= take:
            break
    return {'ok': True, 'teacher_id': teacher_id, 'proposals': items}



def teacher_memory_remove_entry_from_file(path: Any, proposal_id: str) -> bool:
    if not path.exists():
        return False
    try:
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    except Exception:
        _log.warning('failed to read memory file for delete path=%s', path, exc_info=True)
        return False

    marker = f'- entry_id: {proposal_id}'
    marker_idx = -1
    for idx, line in enumerate(lines):
        if str(line or '').strip() == marker:
            marker_idx = idx
            break
    if marker_idx < 0:
        return False

    start = marker_idx
    for idx in range(marker_idx, -1, -1):
        if str(lines[idx] or '').startswith('## '):
            start = idx
            break
    end = marker_idx + 1
    while end < len(lines):
        if str(lines[end] or '').startswith('## '):
            break
        end += 1
    while end < len(lines) and not str(lines[end] or '').strip():
        end += 1

    next_lines = lines[:start] + lines[end:]
    next_text = '\n'.join(next_lines).strip()
    if next_text:
        next_text += '\n'
    try:
        path.write_text(next_text, encoding='utf-8')
    except Exception:
        _log.warning('failed to write memory file for delete path=%s', path, exc_info=True)
        return False
    return True



def teacher_memory_delete_proposal(
    teacher_id: str,
    proposal_id: str,
    *,
    deps: TeacherMemoryStorageDeps,
) -> Dict[str, Any]:
    pid = str(proposal_id or '').strip()
    if not pid:
        return {'ok': False, 'error': 'proposal_id_required'}
    path = teacher_proposal_path(teacher_id, pid, deps=deps)
    if not path.exists():
        return {'ok': False, 'error': 'proposal not found', 'proposal_id': pid}

    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        _log.warning('failed to read proposal file for delete teacher=%s proposal=%s', teacher_id, pid, exc_info=True)
        record = {}
    if not isinstance(record, dict):
        record = {}

    status_before = str(record.get('status') or 'proposed').strip().lower() or 'proposed'
    if status_before == 'deleted':
        return {'ok': True, 'proposal_id': pid, 'status': 'deleted', 'detail': 'already_deleted'}

    deleted_applied_path = ''
    if status_before == 'applied':
        applied_path_raw = str(record.get('applied_to') or '').strip()
        candidate_paths: List[Any] = []
        if applied_path_raw:
            from pathlib import Path
            candidate_paths.append(Path(applied_path_raw))
        target = str(record.get('target') or 'MEMORY').upper()
        if target == 'DAILY':
            candidate_paths.append(deps.teacher_daily_memory_path(teacher_id))
        elif target in {'MEMORY', 'USER', 'AGENTS', 'SOUL', 'HEARTBEAT'}:
            candidate_paths.append(deps.teacher_workspace_file(teacher_id, f"{target}.md" if target != 'MEMORY' else 'MEMORY.md'))
        else:
            candidate_paths.append(deps.teacher_workspace_file(teacher_id, 'MEMORY.md'))
        for candidate in candidate_paths:
            if teacher_memory_remove_entry_from_file(candidate, pid):
                deleted_applied_path = str(candidate)
                break

    record['proposal_id'] = pid
    record['status'] = 'deleted'
    record['deleted_at'] = deps.now_iso()
    record['deleted_from_status'] = status_before
    if deleted_applied_path:
        record['deleted_from_path'] = deleted_applied_path
    deps.atomic_write_json(path, record)
    deps.log_event(
        teacher_id,
        'proposal_deleted',
        {
            'proposal_id': pid,
            'target': str(record.get('target') or 'MEMORY'),
            'source': str(record.get('source') or 'manual'),
            'deleted_from_status': status_before,
        },
    )
    return {'ok': True, 'proposal_id': pid, 'status': 'deleted'}
