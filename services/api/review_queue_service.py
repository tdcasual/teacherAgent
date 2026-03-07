from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .analysis_metadata_repository import AnalysisMetadataRepository
from .review_queue_models import ReviewQueueItem

_OPEN_STATUSES = {'queued', 'claimed'}


@dataclass(frozen=True)
class ReviewQueueDeps:
    metadata_repo: AnalysisMetadataRepository
    queue_log: str
    now_iso: Any



def enqueue_review_item(
    *,
    domain: str,
    report_id: str,
    teacher_id: str,
    reason: str,
    confidence: Optional[float],
    target_type: str,
    target_id: str,
    deps: ReviewQueueDeps,
) -> Dict[str, Any]:
    current_items = _load_latest_items(deps)
    item_id = f"{str(domain or 'review').strip()}_{len(current_items) + 1}"
    timestamp = deps.now_iso()
    item = ReviewQueueItem(
        item_id=item_id,
        domain=str(domain or '').strip(),
        report_id=str(report_id or '').strip(),
        teacher_id=str(teacher_id or '').strip(),
        target_type=str(target_type or '').strip(),
        target_id=str(target_id or '').strip(),
        status='queued',
        reason=str(reason or '').strip(),
        confidence=confidence,
        operation='enqueue',
        created_at=timestamp,
        updated_at=timestamp,
    )
    deps.metadata_repo.append_jsonl(deps.queue_log, item.model_dump(exclude_none=True))
    return item.model_dump(exclude_none=True)



def claim_review_item(*, item_id: str, reviewer_id: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(item_id=item_id, reviewer_id=reviewer_id, status='claimed', operation='claim', deps=deps)



def resolve_review_item(*, item_id: str, reviewer_id: str, resolution_note: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(
        item_id=item_id,
        reviewer_id=reviewer_id,
        status='resolved',
        operation='resolve',
        resolution_note=resolution_note,
        deps=deps,
    )



def reject_review_item(*, item_id: str, reviewer_id: str, resolution_note: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(
        item_id=item_id,
        reviewer_id=reviewer_id,
        status='rejected',
        operation='reject',
        resolution_note=resolution_note,
        deps=deps,
    )



def list_review_items(
    *,
    teacher_id: Optional[str],
    domain: Optional[str],
    status: Optional[str],
    deps: ReviewQueueDeps,
) -> Dict[str, Any]:
    teacher_id_final = str(teacher_id or '').strip() or None
    domain_final = str(domain or '').strip() or None
    status_final = str(status or '').strip() or None
    items = []
    for item in _load_latest_items(deps):
        if teacher_id_final and item.teacher_id != teacher_id_final:
            continue
        if domain_final and item.domain != domain_final:
            continue
        if status_final and item.status != status_final:
            continue
        items.append(item.model_dump(exclude_none=True))
    return {'items': items}



def read_review_queue_items(*, deps: ReviewQueueDeps) -> List[Dict[str, Any]]:
    return [item.model_dump(exclude_none=True) for item in _load_latest_items(deps)]



def has_open_review_item(*, report_id: str, teacher_id: str, domain: Optional[str], deps: ReviewQueueDeps) -> bool:
    for item in _load_latest_items(deps):
        if item.report_id != str(report_id or '').strip():
            continue
        if item.teacher_id != str(teacher_id or '').strip():
            continue
        if domain and item.domain != str(domain or '').strip():
            continue
        if item.status in _OPEN_STATUSES:
            return True
    return False



def _transition_item(
    *,
    item_id: str,
    reviewer_id: str,
    status: str,
    operation: str,
    deps: ReviewQueueDeps,
    resolution_note: Optional[str] = None,
) -> Dict[str, Any]:
    items = {item.item_id: item for item in _load_latest_items(deps)}
    current = items[str(item_id or '').strip()]
    updated = current.model_copy(
        update={
            'status': status,
            'operation': operation,
            'reviewer_id': str(reviewer_id or '').strip() or None,
            'resolution_note': str(resolution_note or '').strip() or None,
            'updated_at': deps.now_iso(),
        }
    )
    deps.metadata_repo.append_jsonl(deps.queue_log, updated.model_dump(exclude_none=True))
    return updated.model_dump(exclude_none=True)



def _load_latest_items(deps: ReviewQueueDeps) -> List[ReviewQueueItem]:
    latest: Dict[str, ReviewQueueItem] = {}
    for index, raw in enumerate(deps.metadata_repo.read_jsonl(deps.queue_log)):
        normalized = _normalize_item(raw, index=index)
        latest[normalized.item_id] = normalized
    return list(latest.values())



def _normalize_item(raw: Dict[str, Any], *, index: int) -> ReviewQueueItem:
    item_id = str(raw.get('item_id') or raw.get('report_id') or raw.get('job_id') or f'review_{index + 1}').strip() or f'review_{index + 1}'
    domain = str(raw.get('domain') or 'survey').strip() or 'survey'
    report_id = str(raw.get('report_id') or raw.get('job_id') or item_id).strip()
    target_type = str(raw.get('target_type') or 'report').strip() or 'report'
    target_id = str(raw.get('target_id') or report_id).strip() or report_id
    status = str(raw.get('status') or 'queued').strip() or 'queued'
    operation = str(raw.get('operation') or 'enqueue').strip() or 'enqueue'
    updated_at = str(raw.get('updated_at') or raw.get('created_at') or '').strip() or None
    created_at = str(raw.get('created_at') or updated_at or '').strip() or None
    confidence = raw.get('confidence')
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except Exception:
        confidence_value = None
    return ReviewQueueItem(
        item_id=item_id,
        domain=domain,
        report_id=report_id,
        teacher_id=str(raw.get('teacher_id') or '').strip(),
        target_type=target_type,
        target_id=target_id,
        status=status,
        reason=str(raw.get('reason') or '').strip(),
        confidence=confidence_value,
        operation=operation,
        reviewer_id=str(raw.get('reviewer_id') or '').strip() or None,
        resolution_note=str(raw.get('resolution_note') or '').strip() or None,
        created_at=created_at,
        updated_at=updated_at,
    )
