from __future__ import annotations

from collections import defaultdict
from typing import Any, DefaultDict, Dict, Iterable


def build_review_feedback_dataset(*, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [_normalize_feedback_row(raw) for raw in items]
    return {
        'items': rows,
        'summary': build_review_feedback_summary(items=rows),
    }



def build_review_feedback_summary(*, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    by_action: DefaultDict[str, int] = defaultdict(int)
    by_domain: DefaultDict[str, int] = defaultdict(int)
    by_strategy: DefaultDict[str, int] = defaultdict(int)
    by_reason_code: DefaultDict[str, int] = defaultdict(int)
    by_disposition: DefaultDict[str, int] = defaultdict(int)
    by_domain_reason_code: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_domain_strategy: DefaultDict[str, DefaultDict[str, int]] = defaultdict(lambda: defaultdict(int))
    total_items = 0

    for raw in items:
        item = _normalize_feedback_row(raw)
        total_items += 1

        action = str(item.get('operation') or item.get('action') or '').strip()
        if action:
            by_action[action] += 1

        disposition = str(item.get('disposition') or '').strip()
        if disposition:
            by_disposition[disposition] += 1

        domain = str(item.get('domain') or '').strip()
        if domain:
            by_domain[domain] += 1

        strategy_id = str(item.get('strategy_id') or '').strip()
        if strategy_id:
            by_strategy[strategy_id] += 1
            if domain:
                by_domain_strategy[domain][strategy_id] += 1

        reason_code = str(item.get('reason_code') or '').strip()
        if reason_code:
            by_reason_code[reason_code] += 1
            if domain:
                by_domain_reason_code[domain][reason_code] += 1

    return {
        'total_items': total_items,
        'by_action': dict(by_action),
        'by_domain': dict(by_domain),
        'by_strategy': dict(by_strategy),
        'by_reason_code': dict(by_reason_code),
        'by_disposition': dict(by_disposition),
        'by_domain_reason_code': {key: dict(value) for key, value in by_domain_reason_code.items()},
        'by_domain_strategy': {key: dict(value) for key, value in by_domain_strategy.items()},
    }



def _normalize_feedback_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    item = dict(raw or {})
    return {
        'item_id': str(item.get('item_id') or '').strip(),
        'report_id': str(item.get('report_id') or '').strip(),
        'teacher_id': str(item.get('teacher_id') or '').strip(),
        'domain': str(item.get('domain') or '').strip(),
        'strategy_id': str(item.get('strategy_id') or '').strip() or None,
        'target_type': str(item.get('target_type') or '').strip() or None,
        'target_id': str(item.get('target_id') or '').strip() or None,
        'operation': str(item.get('operation') or item.get('action') or '').strip() or None,
        'status': str(item.get('status') or '').strip() or None,
        'disposition': str(item.get('disposition') or '').strip() or None,
        'reason': str(item.get('reason') or '').strip() or None,
        'reason_code': str(item.get('reason_code') or '').strip() or None,
        'confidence': item.get('confidence'),
        'reviewer_id': str(item.get('reviewer_id') or '').strip() or None,
        'operator_note': str(item.get('operator_note') or item.get('resolution_note') or '').strip() or None,
        'created_at': str(item.get('created_at') or '').strip() or None,
        'updated_at': str(item.get('updated_at') or '').strip() or None,
        'claimed_at': str(item.get('claimed_at') or '').strip() or None,
        'resolved_at': str(item.get('resolved_at') or '').strip() or None,
        'rejected_at': str(item.get('rejected_at') or '').strip() or None,
        'dismissed_at': str(item.get('dismissed_at') or '').strip() or None,
        'escalated_at': str(item.get('escalated_at') or '').strip() or None,
        'retried_at': str(item.get('retried_at') or '').strip() or None,
    }
