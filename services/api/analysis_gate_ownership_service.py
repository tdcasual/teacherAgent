from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

_OWNER_LABELS = {
    'platform_api': 'Platform/API',
    'runtime': 'Runtime',
    'evaluation': 'Evaluation',
    'strategy_owner': 'Strategy Owner',
    'unassigned': 'Unassigned',
}

_DIRECT_CODE_RULES = {
    'policy_validation_failed': {
        'owner': 'platform_api',
        'recommended_action': 'Fix analysis policy configuration and rerun policy and preflight gates.',
    },
    'contract_check_failed': {
        'owner': 'platform_api',
        'recommended_action': 'Reconcile analysis domain contract changes before rollout continues.',
    },
    'strategy_eval_not_ready_for_expansion': {
        'owner': 'evaluation',
        'recommended_action': 'Fix eval expectation failures or add missing edge-case fixtures before rollout expansion.',
    },
    'shadow_compare_changed_ratio_exceeded': {
        'owner': 'evaluation',
        'recommended_action': 'Inspect shadow compare diffs and align rollout expectations before expansion.',
    },
}

_RUNTIME_CODE_TOKENS = (
    'invalid_output',
    'timeout',
    'budget_rejection',
    'fallback',
    'specialist_execution_failed',
)

_NORMALIZED_HINTS = {
    'platform_api': 'platform_api',
    'artifact_adapter': 'platform_api',
    'runtime': 'runtime',
    'runtime_and_prompt': 'runtime',
    'prompt_and_runtime': 'runtime',
    'selector_and_prompt': 'evaluation',
    'evaluation': 'evaluation',
    'strategy_owner': 'evaluation',
}


def _count_value(raw: Any) -> int:
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def classify_blocking_issues(
    *,
    blocking_issues: Sequence[Dict[str, Any]] | None,
    tuning_recommendations: Sequence[Dict[str, Any]] | None = None,
) -> List[Dict[str, Any]]:
    issues = [dict(item or {}) for item in list(blocking_issues or []) if isinstance(item, dict)]
    supporting_owner_hints = _supporting_owner_hints(tuning_recommendations=tuning_recommendations)
    dominant_hint = supporting_owner_hints[0] if len(supporting_owner_hints) == 1 else ''
    classified: List[Dict[str, Any]] = []
    for item in issues:
        code = str(item.get('code') or '').strip()
        resolved = _resolve_owner(code=code, dominant_hint=dominant_hint)
        classified.append(
            {
                **item,
                'owner': resolved['owner'],
                'owner_label': _OWNER_LABELS[resolved['owner']],
                'recommended_action': resolved['recommended_action'],
                'supporting_owner_hints': list(supporting_owner_hints),
            }
        )
    return classified



def summarize_issue_ownership(*, classified_issues: Iterable[Dict[str, Any]] | None) -> Dict[str, Any]:
    rows = [dict(item or {}) for item in list(classified_issues or []) if isinstance(item, dict)]
    grouped: Dict[str, Dict[str, Any]] = {}
    action_counts: Dict[tuple[str, str], int] = {}
    for item in rows:
        owner = str(item.get('owner') or '').strip() or 'unassigned'
        bucket = grouped.setdefault(
            owner,
            {
                'owner': owner,
                'owner_label': _OWNER_LABELS.get(owner, _OWNER_LABELS['unassigned']),
                'count': 0,
                'codes': [],
                'recommended_actions': [],
                'supporting_owner_hints': [],
            },
        )
        bucket['count'] += 1
        code = str(item.get('code') or '').strip()
        if code and code not in bucket['codes']:
            bucket['codes'].append(code)
        recommended_action = str(item.get('recommended_action') or '').strip()
        if recommended_action:
            if recommended_action not in bucket['recommended_actions']:
                bucket['recommended_actions'].append(recommended_action)
            action_key = (owner, recommended_action)
            action_counts[action_key] = int(action_counts.get(action_key) or 0) + 1
        for owner_hint in list(item.get('supporting_owner_hints') or []):
            normalized = str(owner_hint or '').strip()
            if normalized and normalized not in bucket['supporting_owner_hints']:
                bucket['supporting_owner_hints'].append(normalized)
    top_owners = sorted(grouped.values(), key=lambda item: (-_count_value(item.get('count')), str(item.get('owner'))))
    by_owner = {item['owner']: item for item in top_owners}
    top_actions = [
        {
            'owner': owner,
            'owner_label': _OWNER_LABELS.get(owner, _OWNER_LABELS['unassigned']),
            'count': int(count),
            'recommended_action': recommended_action,
        }
        for (owner, recommended_action), count in action_counts.items()
    ]
    top_actions.sort(
        key=lambda item: (
            -_count_value(item.get('count')),
            -_count_value((by_owner.get(str(item.get('owner')) or '') or {}).get('count')),
            str(item.get('owner')),
            str(item.get('recommended_action')),
        )
    )
    return {
        'total_blocking_issues': len(rows),
        'by_owner': by_owner,
        'top_owners': top_owners,
        'top_actions': top_actions,
    }



def _resolve_owner(*, code: str, dominant_hint: str) -> Dict[str, str]:
    direct = _DIRECT_CODE_RULES.get(code)
    if isinstance(direct, dict):
        return {'owner': str(direct['owner']), 'recommended_action': str(direct['recommended_action'])}
    if any(token in code for token in _RUNTIME_CODE_TOKENS):
        return {
            'owner': 'runtime',
            'recommended_action': _runtime_recommended_action(code=code),
        }
    if dominant_hint:
        return {
            'owner': dominant_hint,
            'recommended_action': 'Start with the dominant tuning recommendation owner before rerunning the preflight gate.',
        }
    if code == 'analysis_preflight_execution_failed':
        return {
            'owner': 'unassigned',
            'recommended_action': 'Inspect preflight execution logs and route the failure to the correct owner before retrying.',
        }
    return {
        'owner': 'unassigned',
        'recommended_action': 'Inspect the blocking issue and assign an explicit owner before retrying rollout.',
    }



def _runtime_recommended_action(*, code: str) -> str:
    if 'invalid_output' in code:
        return 'Stabilize specialist output schema handling and add regression coverage for invalid outputs.'
    if 'timeout' in code:
        return 'Reduce timeout pressure or rebalance runtime budgets before the next rollout attempt.'
    if 'budget_rejection' in code:
        return 'Rebalance execution budgets or simplify the strategy path before rollout continues.'
    if 'fallback' in code or 'specialist_execution_failed' in code:
        return 'Stabilize specialist runner failure paths and verify fallback behavior with regression coverage.'
    return 'Stabilize specialist runtime quality signals before retrying rollout.'



def _supporting_owner_hints(*, tuning_recommendations: Sequence[Dict[str, Any]] | None) -> List[str]:
    hints: List[str] = []
    for item in list(tuning_recommendations or []):
        if not isinstance(item, dict):
            continue
        normalized = _normalize_owner_hint(item.get('owner_hint'))
        if normalized and normalized not in hints:
            hints.append(normalized)
    return hints



def _normalize_owner_hint(raw_value: Any) -> str:
    value = str(raw_value or '').strip()
    if not value:
        return ''
    return _NORMALIZED_HINTS.get(value, '')
