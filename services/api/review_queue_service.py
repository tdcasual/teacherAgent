from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .analysis_metadata_repository import AnalysisMetadataRepository
from .review_queue_models import ReviewQueueDomainSummary, ReviewQueueItem, ReviewQueueSummary

_OPEN_STATUSES = {'queued', 'claimed', 'escalated', 'retry_requested'}
_REASON_CODE_ALIASES = {
    'low_confidence_bundle': 'low_confidence',
    'low_confidence_parse': 'low_confidence',
    'needs_review': 'manual_review',
}
_DISPOSITION_BY_STATUS = {
    'queued': 'open',
    'claimed': 'in_review',
    'resolved': 'resolved',
    'rejected': 'rejected',
    'dismissed': 'dismissed',
    'escalated': 'escalated',
    'retry_requested': 'retry_requested',
}
_TIMESTAMP_FIELD_BY_STATUS = {
    'claimed': 'claimed_at',
    'resolved': 'resolved_at',
    'rejected': 'rejected_at',
    'dismissed': 'dismissed_at',
    'escalated': 'escalated_at',
    'retry_requested': 'retried_at',
}


@dataclass(frozen=True)
class ReviewQueueDeps:
    metadata_repo: AnalysisMetadataRepository
    queue_log: str
    now_iso: Any
    metrics_service: Any | None = None



def enqueue_review_item(
    *,
    domain: str,
    report_id: str,
    teacher_id: str,
    reason: str,
    confidence: Optional[float],
    target_type: str,
    target_id: str,
    strategy_id: Optional[str] = None,
    deps: ReviewQueueDeps,
) -> Dict[str, Any]:
    current_items = _load_latest_items(deps)
    item_id = f"{str(domain or 'review').strip()}_{len(current_items) + 1}"
    timestamp = deps.now_iso()
    reason_raw = str(reason or '').strip()
    item = ReviewQueueItem(
        item_id=item_id,
        domain=str(domain or '').strip(),
        report_id=str(report_id or '').strip(),
        teacher_id=str(teacher_id or '').strip(),
        strategy_id=str(strategy_id or '').strip() or None,
        target_type=str(target_type or '').strip(),
        target_id=str(target_id or '').strip(),
        status='queued',
        reason=reason_raw,
        reason_code=_normalize_reason_code(reason_raw),
        confidence=confidence,
        operation='enqueue',
        disposition=_disposition_for_status('queued'),
        created_at=timestamp,
        updated_at=timestamp,
    )
    deps.metadata_repo.append_jsonl(deps.queue_log, item.model_dump(exclude_none=True))
    metrics_service = getattr(deps, 'metrics_service', None)
    record_review_downgrade = getattr(metrics_service, 'record_review_downgrade', None)
    if callable(record_review_downgrade):
        record_review_downgrade(
            domain=item.domain,
            strategy_id=item.strategy_id,
            agent_id=None,
            reason_code=item.reason_code,
        )
    return item.model_dump(exclude_none=True)



def claim_review_item(*, item_id: str, reviewer_id: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(item_id=item_id, reviewer_id=reviewer_id, status='claimed', operation='claim', deps=deps)



def resolve_review_item(*, item_id: str, reviewer_id: str, resolution_note: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(
        item_id=item_id,
        reviewer_id=reviewer_id,
        status='resolved',
        operation='resolve',
        operator_note=resolution_note,
        deps=deps,
    )



def reject_review_item(*, item_id: str, reviewer_id: str, resolution_note: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(
        item_id=item_id,
        reviewer_id=reviewer_id,
        status='rejected',
        operation='reject',
        operator_note=resolution_note,
        deps=deps,
    )



def dismiss_review_item(*, item_id: str, reviewer_id: str, operator_note: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(
        item_id=item_id,
        reviewer_id=reviewer_id,
        status='dismissed',
        operation='dismiss',
        operator_note=operator_note,
        deps=deps,
    )



def escalate_review_item(*, item_id: str, reviewer_id: str, operator_note: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(
        item_id=item_id,
        reviewer_id=reviewer_id,
        status='escalated',
        operation='escalate',
        operator_note=operator_note,
        deps=deps,
    )



def retry_review_item(*, item_id: str, reviewer_id: str, operator_note: str, deps: ReviewQueueDeps) -> Dict[str, Any]:
    return _transition_item(
        item_id=item_id,
        reviewer_id=reviewer_id,
        status='retry_requested',
        operation='retry',
        operator_note=operator_note,
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
    scoped_items: List[ReviewQueueItem] = []
    for item in _load_latest_items(deps):
        if teacher_id_final and item.teacher_id != teacher_id_final:
            continue
        if domain_final and item.domain != domain_final:
            continue
        scoped_items.append(item)

    items = [
        item.model_dump(exclude_none=True)
        for item in scoped_items
        if _matches_status(item.status, status_final)
    ]
    return {
        'items': items,
        'summary': _build_summary(scoped_items, now_iso=deps.now_iso()).model_dump(exclude_none=True),
    }



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
    operator_note: Optional[str] = None,
) -> Dict[str, Any]:
    items = {item.item_id: item for item in _load_latest_items(deps)}
    current = items[str(item_id or '').strip()]
    timestamp = deps.now_iso()
    update_payload = {
        'status': status,
        'operation': operation,
        'reviewer_id': str(reviewer_id or '').strip() or None,
        'operator_note': str(operator_note or '').strip() or None,
        'resolution_note': str(operator_note or '').strip() or None,
        'disposition': _disposition_for_status(status),
        'updated_at': timestamp,
    }
    timestamp_field = _TIMESTAMP_FIELD_BY_STATUS.get(status)
    if timestamp_field:
        update_payload[timestamp_field] = timestamp
    updated = current.model_copy(update=update_payload)
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
    reason = str(raw.get('reason') or '').strip()
    reason_code = str(raw.get('reason_code') or '').strip() or _normalize_reason_code(reason)
    confidence = raw.get('confidence')
    try:
        confidence_value = float(confidence) if confidence is not None else None
    except Exception:
        confidence_value = None
    operator_note = str(raw.get('operator_note') or raw.get('resolution_note') or '').strip() or None
    return ReviewQueueItem(
        item_id=item_id,
        domain=domain,
        report_id=report_id,
        teacher_id=str(raw.get('teacher_id') or '').strip(),
        strategy_id=str(raw.get('strategy_id') or '').strip() or None,
        target_type=target_type,
        target_id=target_id,
        status=status,
        reason=reason,
        reason_code=reason_code,
        confidence=confidence_value,
        operation=operation,
        reviewer_id=str(raw.get('reviewer_id') or '').strip() or None,
        resolution_note=str(raw.get('resolution_note') or operator_note or '').strip() or None,
        operator_note=operator_note,
        disposition=str(raw.get('disposition') or _disposition_for_status(status)).strip() or _disposition_for_status(status),
        created_at=created_at,
        updated_at=updated_at,
        claimed_at=str(raw.get('claimed_at') or '').strip() or None,
        resolved_at=str(raw.get('resolved_at') or '').strip() or None,
        rejected_at=str(raw.get('rejected_at') or '').strip() or None,
        dismissed_at=str(raw.get('dismissed_at') or '').strip() or None,
        escalated_at=str(raw.get('escalated_at') or '').strip() or None,
        retried_at=str(raw.get('retried_at') or '').strip() or None,
    )



def _normalize_reason_code(reason: str) -> str:
    normalized = str(reason or '').strip().lower().replace(' ', '_').replace('-', '_')
    if not normalized:
        return 'unknown'
    return _REASON_CODE_ALIASES.get(normalized, normalized)



def _disposition_for_status(status: str) -> str:
    return _DISPOSITION_BY_STATUS.get(str(status or '').strip(), 'open')



def _matches_status(item_status: str, requested_status: Optional[str]) -> bool:
    if not requested_status:
        return True
    if requested_status == 'unresolved':
        return str(item_status or '').strip() in _OPEN_STATUSES
    return str(item_status or '').strip() == requested_status



def _build_summary(items: List[ReviewQueueItem], *, now_iso: str) -> ReviewQueueSummary:
    status_counts: Dict[str, int] = {}
    reason_counts: Dict[str, int] = {}
    domains: Dict[str, ReviewQueueDomainSummary] = {}
    unresolved_items = 0
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1
        reason_code = str(item.reason_code or 'unknown').strip() or 'unknown'
        reason_counts[reason_code] = reason_counts.get(reason_code, 0) + 1
        domain_summary = domains.get(item.domain)
        if domain_summary is None:
            domain_summary = ReviewQueueDomainSummary(domain=item.domain)
            domains[item.domain] = domain_summary
        domain_summary.total_items += 1
        domain_summary.status_counts[item.status] = domain_summary.status_counts.get(item.status, 0) + 1
        domain_summary.reason_counts[reason_code] = domain_summary.reason_counts.get(reason_code, 0) + 1
        if item.status in _OPEN_STATUSES:
            unresolved_items += 1
            domain_summary.unresolved_items += 1
    return ReviewQueueSummary(
        total_items=len(items),
        unresolved_items=unresolved_items,
        status_counts=status_counts,
        reason_counts=reason_counts,
        domains=[domains[key] for key in sorted(domains.keys())],
        generated_at=str(now_iso or '').strip() or None,
    )
