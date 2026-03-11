#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.api.analysis_policy_service import load_analysis_policy, load_analysis_policy_from_path
from services.api.specialist_agents.metrics_service import SpecialistMetricsService

_RUNTIME_REASON_COUNTERS = {
    'timeout': 'timeout_count',
    'invalid_output': 'invalid_output_count',
    'budget_exceeded': 'budget_rejection_count',
    'specialist_execution_failed': 'fallback_count',
}



def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else {}



def _resolve_release_thresholds(
    *,
    policy: Dict[str, Any] | None,
    max_changed_ratio: float | None,
    max_invalid_output_count: int | None,
    max_timeout_count: int | None,
    max_timeout_rate: float | None,
    max_invalid_output_rate: float | None,
    max_budget_rejection_rate: float | None,
    max_fallback_rate: float | None,
    window_sec: int | None,
) -> Dict[str, Any]:
    release_policy = dict((load_analysis_policy(policy=policy).get('release_readiness') or {}))
    thresholds = dict(release_policy.get('thresholds') or {})
    overrides = {
        'max_changed_ratio': max_changed_ratio,
        'max_invalid_output_count': max_invalid_output_count,
        'max_timeout_count': max_timeout_count,
        'max_timeout_rate': max_timeout_rate,
        'max_invalid_output_rate': max_invalid_output_rate,
        'max_budget_rejection_rate': max_budget_rejection_rate,
        'max_fallback_rate': max_fallback_rate,
        'window_sec': window_sec,
    }
    for key, value in overrides.items():
        if value is not None:
            thresholds[key] = value
    return {
        'max_changed_ratio': float(thresholds.get('max_changed_ratio') or 0.2),
        'max_invalid_output_count': int(thresholds.get('max_invalid_output_count') or 0),
        'max_timeout_count': int(thresholds.get('max_timeout_count') or 0),
        'max_timeout_rate': float(thresholds.get('max_timeout_rate') or 0.05),
        'max_invalid_output_rate': float(thresholds.get('max_invalid_output_rate') or 0.05),
        'max_budget_rejection_rate': float(thresholds.get('max_budget_rejection_rate') or 0.02),
        'max_fallback_rate': float(thresholds.get('max_fallback_rate') or 0.1),
        'window_sec': int(thresholds.get('window_sec') or 3600),
    }



def build_analysis_release_readiness_report(
    *,
    contract_check: Dict[str, Any],
    metrics_snapshot: Dict[str, Any],
    drift_summary: Dict[str, Any],
    shadow_compare_summary: Dict[str, Any],
    max_changed_ratio: float | None = None,
    max_invalid_output_count: int | None = None,
    max_timeout_count: int | None = None,
    max_timeout_rate: float | None = None,
    max_invalid_output_rate: float | None = None,
    max_budget_rejection_rate: float | None = None,
    max_fallback_rate: float | None = None,
    window_sec: int | None = None,
    group_by: str = '',
    strategy_id: str = '',
    policy: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    thresholds = _resolve_release_thresholds(
        policy=policy,
        max_changed_ratio=max_changed_ratio,
        max_invalid_output_count=max_invalid_output_count,
        max_timeout_count=max_timeout_count,
        max_timeout_rate=max_timeout_rate,
        max_invalid_output_rate=max_invalid_output_rate,
        max_budget_rejection_rate=max_budget_rejection_rate,
        max_fallback_rate=max_fallback_rate,
        window_sec=window_sec,
    )
    max_changed_ratio = float(thresholds['max_changed_ratio'])
    max_invalid_output_count = int(thresholds['max_invalid_output_count'])
    max_timeout_count = int(thresholds['max_timeout_count'])
    max_timeout_rate = float(thresholds['max_timeout_rate'])
    max_invalid_output_rate = float(thresholds['max_invalid_output_rate'])
    max_budget_rejection_rate = float(thresholds['max_budget_rejection_rate'])
    max_fallback_rate = float(thresholds['max_fallback_rate'])
    window_sec = int(thresholds['window_sec'])

    blocking_issues: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    metrics_counters = dict(metrics_snapshot.get('counters') or {}) if isinstance(metrics_snapshot, dict) else {}
    invalid_output_count = int(metrics_counters.get('invalid_output_count') or 0)
    timeout_count = int(metrics_counters.get('timeout_count') or 0)
    review_downgrade_count = int(metrics_counters.get('review_downgrade_count') or 0)
    changed_ratio = float(shadow_compare_summary.get('changed_ratio') or 0.0)
    changed_pairs = int(shadow_compare_summary.get('changed_pairs') or 0)
    total_pairs = int(shadow_compare_summary.get('total_pairs') or 0)
    drift_total = int(drift_summary.get('total_items') or 0)

    specialist_quality_raw = metrics_snapshot.get('specialist_quality') if isinstance(metrics_snapshot, dict) else None
    if isinstance(specialist_quality_raw, dict) and specialist_quality_raw:
        specialist_quality = dict(specialist_quality_raw)
    else:
        specialist_quality = SpecialistMetricsService(
            max_timeout_rate=max_timeout_rate,
            max_invalid_output_rate=max_invalid_output_rate,
            max_budget_rejection_rate=max_budget_rejection_rate,
            max_fallback_rate=max_fallback_rate,
        ).summarize(metrics_snapshot)

    grouped_quality = _resolve_grouped_quality(
        metrics_snapshot=metrics_snapshot,
        group_by=group_by,
        window_sec=window_sec,
        max_timeout_rate=max_timeout_rate,
        max_invalid_output_rate=max_invalid_output_rate,
        max_budget_rejection_rate=max_budget_rejection_rate,
        max_fallback_rate=max_fallback_rate,
    )

    if not bool(contract_check.get('ok')):
        blocking_issues.append({'code': 'contract_check_failed', 'detail': 'analysis domain contract check did not pass'})
    if invalid_output_count > int(max_invalid_output_count):
        blocking_issues.append({'code': 'invalid_output_count_exceeded', 'detail': f'invalid_output_count={invalid_output_count}'})
    if timeout_count > int(max_timeout_count):
        blocking_issues.append({'code': 'timeout_count_exceeded', 'detail': f'timeout_count={timeout_count}'})
    if changed_ratio > float(max_changed_ratio):
        blocking_issues.append(
            {
                'code': 'shadow_compare_changed_ratio_exceeded',
                'detail': f'changed_ratio={changed_ratio:.4f} total_pairs={total_pairs} changed_pairs={changed_pairs}',
            }
        )
    blocking_issues.extend(list(specialist_quality.get('blocking_issues') or []))
    blocking_issues.extend(_grouped_blocking_issues(grouped_quality=grouped_quality, group_by=group_by, strategy_id=strategy_id))

    if review_downgrade_count > 0:
        warnings.append({'code': 'review_downgrade_present', 'detail': f'review_downgrade_count={review_downgrade_count}'})
    if drift_total > 0:
        warnings.append({'code': 'review_feedback_present', 'detail': f'review_feedback_items={drift_total}'})
    if 0 < changed_ratio <= float(max_changed_ratio):
        warnings.append({'code': 'shadow_compare_changed_pairs_present', 'detail': f'changed_ratio={changed_ratio:.4f}'})

    return {
        'ready_for_release': len(blocking_issues) == 0,
        'blocking_issues': blocking_issues,
        'warnings': warnings,
        'inputs': {
            'contract_check': contract_check,
            'metrics_snapshot': metrics_snapshot,
            'specialist_quality': specialist_quality,
            'group_by': str(group_by or '').strip() or None,
            'strategy_id': str(strategy_id or '').strip() or None,
            'window_sec': int(window_sec),
            'drift_summary': drift_summary,
            'shadow_compare_summary': shadow_compare_summary,
        },
        'thresholds': thresholds,
    }



def _resolve_grouped_quality(
    *,
    metrics_snapshot: Dict[str, Any],
    group_by: str,
    window_sec: int,
    max_timeout_rate: float,
    max_invalid_output_rate: float,
    max_budget_rejection_rate: float,
    max_fallback_rate: float,
) -> Dict[str, Dict[str, Any]]:
    group_by_final = str(group_by or '').strip()
    if group_by_final not in {'strategy', 'agent'}:
        return {}
    grouped_key = f'specialist_quality_by_{group_by_final}'
    grouped_quality_raw = metrics_snapshot.get(grouped_key) if isinstance(metrics_snapshot, dict) else None
    if isinstance(grouped_quality_raw, dict) and grouped_quality_raw:
        return {str(key): dict(value) for key, value in grouped_quality_raw.items() if isinstance(value, dict)}
    grouped_snapshots = _group_runtime_records(metrics_snapshot, group_by=group_by_final, window_sec=window_sec)
    if not grouped_snapshots:
        return {}
    return SpecialistMetricsService(
        max_timeout_rate=max_timeout_rate,
        max_invalid_output_rate=max_invalid_output_rate,
        max_budget_rejection_rate=max_budget_rejection_rate,
        max_fallback_rate=max_fallback_rate,
    ).summarize_grouped(grouped_snapshots)



def _grouped_blocking_issues(
    *,
    grouped_quality: Dict[str, Dict[str, Any]],
    group_by: str,
    strategy_id: str,
) -> List[Dict[str, Any]]:
    group_by_final = str(group_by or '').strip()
    if group_by_final not in {'strategy', 'agent'} or not grouped_quality:
        return []
    issues: List[Dict[str, Any]] = []
    target_group = str(strategy_id or '').strip()
    for bucket, summary in grouped_quality.items():
        if target_group and group_by_final == 'strategy' and bucket != target_group:
            continue
        if not isinstance(summary, dict) or bool(summary.get('ready_for_release', True)):
            continue
        for issue in list(summary.get('blocking_issues') or []):
            normalized = dict(issue or {})
            normalized['scope'] = bucket
            issues.append(normalized)
    return issues



def _group_runtime_records(metrics_snapshot: Dict[str, Any], *, group_by: str, window_sec: int) -> Dict[str, Dict[str, Any]]:
    records_raw = metrics_snapshot.get('recent_runtime_records') if isinstance(metrics_snapshot, dict) else None
    if not isinstance(records_raw, list):
        return {}
    now_ts = max([float(item.get('timestamp_sec') or 0.0) for item in records_raw if isinstance(item, dict)] or [0.0])
    threshold = now_ts - float(int(window_sec or 0))
    field_name = 'strategy_id' if group_by == 'strategy' else 'agent_id'
    grouped: Dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for item in records_raw:
        if not isinstance(item, dict):
            continue
        timestamp_sec = float(item.get('timestamp_sec') or 0.0)
        if timestamp_sec < threshold:
            continue
        bucket = str(item.get(field_name) or '').strip() or 'unknown'
        grouped[bucket].append(dict(item))
    return {bucket: _build_runtime_snapshot_from_records(items) for bucket, items in grouped.items() if items}



def _build_runtime_snapshot_from_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    counters = {
        'run_count': 0,
        'fail_count': 0,
        'timeout_count': 0,
        'invalid_output_count': 0,
        'budget_rejection_count': 0,
        'fallback_count': 0,
        'review_downgrade_count': 0,
        'reviewer_reject_count': 0,
        'rerun_count': 0,
    }
    by_phase: Dict[str, int] = defaultdict(int)
    for item in records:
        phase = str(item.get('phase') or '').strip() or 'unknown'
        reason_code = str(item.get('reason_code') or '').strip() or None
        by_phase[phase] += 1
        if phase == 'started':
            counters['run_count'] += 1
        if phase == 'failed':
            counters['fail_count'] += 1
        if phase == 'review_downgraded':
            counters['review_downgrade_count'] += 1
        if phase == 'reviewer_rejected':
            counters['reviewer_reject_count'] += 1
        if phase == 'rerun_requested':
            counters['rerun_count'] += 1
        if reason_code:
            counter_key = _RUNTIME_REASON_COUNTERS.get(reason_code)
            if counter_key:
                counters[counter_key] += 1
    return {'counters': counters, 'by_phase': dict(by_phase)}



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a compact analysis release-readiness report from contract, metrics, drift, and shadow compare signals.')
    parser.add_argument('--contract-check', required=True, help='path to contract-check JSON')
    parser.add_argument('--metrics', required=True, help='path to metrics snapshot JSON')
    parser.add_argument('--drift-summary', required=True, help='path to drift summary JSON')
    parser.add_argument('--shadow-compare', required=True, help='path to shadow compare summary JSON')
    parser.add_argument('--policy-config', default='', help='optional analysis policy JSON path')
    parser.add_argument('--max-changed-ratio', type=float, default=None)
    parser.add_argument('--max-invalid-output-count', type=int, default=None)
    parser.add_argument('--max-timeout-count', type=int, default=None)
    parser.add_argument('--max-timeout-rate', type=float, default=None)
    parser.add_argument('--max-invalid-output-rate', type=float, default=None)
    parser.add_argument('--max-budget-rejection-rate', type=float, default=None)
    parser.add_argument('--max-fallback-rate', type=float, default=None)
    parser.add_argument('--window-sec', type=int, default=None)
    parser.add_argument('--group-by', default='', help='optional grouping for specialist quality: strategy|agent')
    parser.add_argument('--strategy-id', default='', help='optional strategy target when group_by=strategy')
    parser.add_argument('--output', default='', help='optional output file path, defaults to stdout')
    args = parser.parse_args(argv)

    policy = load_analysis_policy_from_path(Path(args.policy_config)) if args.policy_config else None

    payload = build_analysis_release_readiness_report(
        contract_check=_load_json(Path(args.contract_check)),
        metrics_snapshot=_load_json(Path(args.metrics)),
        drift_summary=_load_json(Path(args.drift_summary)).get('summary', _load_json(Path(args.drift_summary))),
        shadow_compare_summary=_load_json(Path(args.shadow_compare)),
        max_changed_ratio=args.max_changed_ratio,
        max_invalid_output_count=args.max_invalid_output_count,
        max_timeout_count=args.max_timeout_count,
        max_timeout_rate=args.max_timeout_rate,
        max_invalid_output_rate=args.max_invalid_output_rate,
        max_budget_rejection_rate=args.max_budget_rejection_rate,
        max_fallback_rate=args.max_fallback_rate,
        window_sec=args.window_sec,
        group_by=args.group_by,
        strategy_id=args.strategy_id,
        policy=policy,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
