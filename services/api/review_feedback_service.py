from __future__ import annotations

from collections import defaultdict
from typing import Any, DefaultDict, Dict, Iterable, List

from .analysis_policy_service import load_analysis_policy

_PRIORITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def _count_value(raw: Any) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0



def build_review_feedback_dataset(*, items: Iterable[Dict[str, Any]], policy: Dict[str, Any] | None = None) -> Dict[str, Any]:
    rows = [_normalize_feedback_row(raw) for raw in items]
    recommendations = build_review_feedback_recommendations(items=rows, policy=policy)
    return {
        'items': rows,
        'summary': build_review_feedback_summary(items=rows),
        'drift_summary': summarize_review_feedback_drift(items=rows),
        'tuning_recommendations': recommendations,
        'feedback_loop_summary': build_feedback_loop_summary(recommendations=recommendations),
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



def summarize_review_feedback_drift(*, items: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [_normalize_feedback_row(raw) for raw in items]
    by_domain: DefaultDict[str, int] = defaultdict(int)
    by_strategy: DefaultDict[str, int] = defaultdict(int)
    by_reason_code: DefaultDict[str, int] = defaultdict(int)

    for item in rows:
        domain = str(item.get('domain') or '').strip()
        strategy_id = str(item.get('strategy_id') or '').strip()
        reason_code = str(item.get('reason_code') or '').strip()
        if domain:
            by_domain[domain] += 1
        if strategy_id:
            by_strategy[strategy_id] += 1
        if reason_code:
            by_reason_code[reason_code] += 1

    return {
        'total_items': len(rows),
        'by_domain': dict(by_domain),
        'by_strategy': dict(by_strategy),
        'by_reason_code': dict(by_reason_code),
        'top_regression_domains': _top_counts('domain', by_domain),
        'top_regression_strategies': _top_counts('strategy_id', by_strategy),
        'top_reason_codes': _top_counts('reason_code', by_reason_code),
    }



def build_review_feedback_recommendations(*, items: Iterable[Dict[str, Any]], policy: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    rows = [_normalize_feedback_row(raw) for raw in items]
    review_policy = load_analysis_policy(policy=policy).get('review_feedback') or {}
    grouped: dict[tuple[str, str, str, str], Dict[str, Any]] = {}
    high_impact_dispositions = {str(item).strip() for item in list(review_policy.get('high_impact_dispositions') or []) if str(item).strip()}
    retry_dispositions = {str(item).strip() for item in list(review_policy.get('retry_dispositions') or []) if str(item).strip()}

    for item in rows:
        reason_code = str(item.get('reason_code') or '').strip()
        if not reason_code:
            continue
        domain = str(item.get('domain') or '').strip() or 'unknown'
        strategy_id = str(item.get('strategy_id') or '').strip()
        scope_type = 'strategy' if strategy_id else 'domain'
        scope_id = strategy_id or domain
        spec = _recommendation_spec(reason_code=reason_code, review_policy=review_policy)
        key = (scope_type, scope_id, str(spec['action_type']), reason_code)
        if key not in grouped:
            grouped[key] = {
                'scope_type': scope_type,
                'scope_id': scope_id,
                'action_type': spec['action_type'],
                'reason_code': reason_code,
                'recommended_action': spec['recommended_action'],
                'owner_hint': spec['owner_hint'],
                'default_priority': spec['default_priority'],
                'item_count': 0,
                'rejected_count': 0,
                'retry_count': 0,
                'sample_domains': set(),
                'sample_strategies': set(),
            }
        bucket = grouped[key]
        bucket['item_count'] += 1
        bucket['sample_domains'].add(domain)
        if strategy_id:
            bucket['sample_strategies'].add(strategy_id)
        disposition = str(item.get('disposition') or '').strip()
        operation = str(item.get('operation') or '').strip()
        if disposition in high_impact_dispositions or operation == 'reject':
            bucket['rejected_count'] += 1
        if disposition in retry_dispositions or operation == 'retry':
            bucket['retry_count'] += 1

    recommendations: List[Dict[str, Any]] = []
    for bucket in grouped.values():
        priority = _recommendation_priority(bucket=bucket, review_policy=review_policy)
        recommendations.append(
            {
                'scope_type': bucket['scope_type'],
                'scope_id': bucket['scope_id'],
                'action_type': bucket['action_type'],
                'priority': priority,
                'reason_code': bucket['reason_code'],
                'reason_codes': [bucket['reason_code']],
                'recommended_action': bucket['recommended_action'],
                'owner_hint': bucket['owner_hint'],
                'evidence': {
                    'item_count': int(bucket['item_count']),
                    'rejected_count': int(bucket['rejected_count']),
                    'retry_count': int(bucket['retry_count']),
                    'sample_domains': sorted(bucket['sample_domains']),
                    'sample_strategies': sorted(bucket['sample_strategies']),
                },
            }
        )
    recommendations.sort(
        key=lambda item: (
            _PRIORITY_ORDER.get(str(item.get('priority') or 'low'), 99),
            -int(((item.get('evidence') or {}).get('item_count') or 0)),
            str(item.get('scope_id') or ''),
            str(item.get('action_type') or ''),
        )
    )
    return recommendations



def build_feedback_loop_summary(*, recommendations: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [dict(item or {}) for item in recommendations if isinstance(item, dict)]
    by_priority: DefaultDict[str, int] = defaultdict(int)
    by_action_type: DefaultDict[str, int] = defaultdict(int)
    by_scope: DefaultDict[str, int] = defaultdict(int)

    for item in rows:
        priority = str(item.get('priority') or '').strip() or 'unknown'
        action_type = str(item.get('action_type') or '').strip() or 'unknown'
        scope_id = str(item.get('scope_id') or '').strip() or 'unknown'
        by_priority[priority] += 1
        by_action_type[action_type] += 1
        by_scope[scope_id] += 1

    return {
        'total_recommendations': len(rows),
        'by_priority': dict(by_priority),
        'by_action_type': dict(by_action_type),
        'high_priority_count': int(by_priority.get('high') or 0),
        'top_targets': _top_counts('scope_id', by_scope),
    }



def _top_counts(key: str, values: Dict[str, int], *, limit: int = 5) -> List[Dict[str, Any]]:
    rows = [{key: name, 'count': int(count)} for name, count in values.items() if str(name or '').strip()]
    rows.sort(key=lambda item: (-_count_value(item.get('count')), str(item.get(key))))
    return rows[:limit]



def _recommendation_spec(*, reason_code: str, review_policy: Dict[str, Any]) -> Dict[str, str]:
    normalized = str(reason_code or '').strip()
    default = dict(review_policy.get('fallback_recommendation') or {})
    if not default:
        default = {
            'action_type': 'investigate_review_feedback',
            'default_priority': 'medium',
            'recommended_action': 'Inspect review feedback samples and convert them into explicit strategy fixes.',
            'owner_hint': 'strategy_owner',
        }
    specs = dict(review_policy.get('reason_recommendation_specs') or {})
    if not normalized:
        return default
    resolved = specs.get(normalized)
    if not isinstance(resolved, dict):
        return default
    return {
        'action_type': str(resolved.get('action_type') or default['action_type']),
        'default_priority': str(resolved.get('default_priority') or default['default_priority']),
        'recommended_action': str(resolved.get('recommended_action') or default['recommended_action']),
        'owner_hint': str(resolved.get('owner_hint') or default['owner_hint']),
    }



def _recommendation_priority(*, bucket: Dict[str, Any], review_policy: Dict[str, Any]) -> str:
    default_priority = str(bucket.get('default_priority') or 'medium').strip() or 'medium'
    item_count = int(bucket.get('item_count') or 0)
    rejected_count = int(bucket.get('rejected_count') or 0)
    retry_count = int(bucket.get('retry_count') or 0)
    priority_rules = dict(review_policy.get('priority_rules') or {})
    high_rejected_threshold = int(priority_rules.get('high_if_rejected_count_at_least') or 1)
    medium_retry_threshold = int(priority_rules.get('medium_if_retry_count_at_least') or 1)
    medium_item_threshold = int(priority_rules.get('medium_if_item_count_at_least') or 2)

    if rejected_count >= high_rejected_threshold or default_priority == 'high':
        return 'high'
    if retry_count >= medium_retry_threshold or item_count >= medium_item_threshold or default_priority == 'medium':
        return 'medium'
    return 'low'



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
