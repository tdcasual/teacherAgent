#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List



def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    return payload if isinstance(payload, dict) else {}



def build_analysis_release_readiness_report(
    *,
    contract_check: Dict[str, Any],
    metrics_snapshot: Dict[str, Any],
    drift_summary: Dict[str, Any],
    shadow_compare_summary: Dict[str, Any],
    max_changed_ratio: float = 0.2,
    max_invalid_output_count: int = 0,
    max_timeout_count: int = 0,
) -> Dict[str, Any]:
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
            'drift_summary': drift_summary,
            'shadow_compare_summary': shadow_compare_summary,
        },
        'thresholds': {
            'max_changed_ratio': float(max_changed_ratio),
            'max_invalid_output_count': int(max_invalid_output_count),
            'max_timeout_count': int(max_timeout_count),
        },
    }



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a compact analysis release-readiness report from contract, metrics, drift, and shadow compare signals.')
    parser.add_argument('--contract-check', required=True, help='path to contract-check JSON')
    parser.add_argument('--metrics', required=True, help='path to metrics snapshot JSON')
    parser.add_argument('--drift-summary', required=True, help='path to drift summary JSON')
    parser.add_argument('--shadow-compare', required=True, help='path to shadow compare summary JSON')
    parser.add_argument('--max-changed-ratio', type=float, default=0.2)
    parser.add_argument('--max-invalid-output-count', type=int, default=0)
    parser.add_argument('--max-timeout-count', type=int, default=0)
    parser.add_argument('--output', default='', help='optional output file path, defaults to stdout')
    args = parser.parse_args(argv)

    payload = build_analysis_release_readiness_report(
        contract_check=_load_json(Path(args.contract_check)),
        metrics_snapshot=_load_json(Path(args.metrics)),
        drift_summary=_load_json(Path(args.drift_summary)).get('summary', _load_json(Path(args.drift_summary))),
        shadow_compare_summary=_load_json(Path(args.shadow_compare)),
        max_changed_ratio=args.max_changed_ratio,
        max_invalid_output_count=args.max_invalid_output_count,
        max_timeout_count=args.max_timeout_count,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
