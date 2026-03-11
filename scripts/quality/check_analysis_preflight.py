#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_analysis_release_readiness_report import build_analysis_release_readiness_report  # noqa: E402
from scripts.build_analysis_shadow_compare_report import build_analysis_shadow_compare_report  # noqa: E402
from scripts.check_analysis_domain_contract import check_analysis_domain_contract  # noqa: E402
from scripts.analysis_strategy_eval import evaluate_fixture_tree  # noqa: E402
from services.api.analysis_policy_service import (  # noqa: E402
    DEFAULT_ANALYSIS_POLICY_PATH,
    build_analysis_policy_summary,
    load_analysis_policy,
    load_analysis_policy_from_path,
)
from services.api.review_feedback_service import build_review_feedback_dataset  # noqa: E402



def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(f'expected JSON object: {path}')
    return payload



def _load_review_feedback_items(path: Path) -> List[Dict[str, Any]]:
    if path.suffix == '.jsonl':
        items: List[Dict[str, Any]] = []
        for raw_line in path.read_text(encoding='utf-8').splitlines():
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                items.append(dict(payload))
        return items

    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, dict) and isinstance(payload.get('items'), list):
        return [dict(item or {}) for item in payload.get('items') or [] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [dict(item or {}) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [dict(payload)]
    raise ValueError(f'unsupported review feedback payload: {path}')



def _strategy_eval_blocking_issues(strategy_eval_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocking_issues: List[Dict[str, Any]] = []
    rollout = dict(strategy_eval_report.get('rollout_recommendations') or {})
    if not bool(rollout.get('ready_for_expansion')):
        blocking_issues.append(
            {
                'code': 'strategy_eval_not_ready_for_expansion',
                'detail': (
                    'strategy eval rollout_recommendations.ready_for_expansion=false '
                    f"expectation_failures={int(strategy_eval_report.get('expectation_failures') or 0)} "
                    f"high_priority_tuning_recommendations={int(rollout.get('high_priority_tuning_recommendations') or 0)}"
                ),
            }
        )
    return blocking_issues



def build_analysis_preflight_report(
    *,
    fixtures_dir: Path,
    review_feedback_path: Path,
    metrics_path: Path,
    baseline_dir: Path,
    candidate_dir: Path,
    policy_config_path: Path | None,
) -> Dict[str, Any]:
    policy = load_analysis_policy_from_path(policy_config_path) if policy_config_path else load_analysis_policy()
    policy_check = {
        'config_path': str(policy_config_path or DEFAULT_ANALYSIS_POLICY_PATH),
        'valid': True,
        'summary': build_analysis_policy_summary(policy),
    }
    contract_check = check_analysis_domain_contract()
    review_feedback_items = _load_review_feedback_items(review_feedback_path)
    review_feedback_dataset = build_review_feedback_dataset(items=review_feedback_items, policy=policy)
    strategy_eval = evaluate_fixture_tree(
        fixtures_dir,
        review_feedback={'items': review_feedback_items},
        policy=policy,
    )
    shadow_compare = build_analysis_shadow_compare_report(
        baseline_dir=baseline_dir,
        candidate_dir=candidate_dir,
    )
    metrics_snapshot = _load_json(metrics_path)
    release_readiness = build_analysis_release_readiness_report(
        contract_check=contract_check,
        metrics_snapshot=metrics_snapshot,
        drift_summary=review_feedback_dataset.get('drift_summary') or {},
        shadow_compare_summary=shadow_compare,
        policy=policy,
    )

    blocking_issues = list(release_readiness.get('blocking_issues') or [])
    blocking_issues.extend(_strategy_eval_blocking_issues(strategy_eval))
    warnings = list(release_readiness.get('warnings') or [])
    if int(((review_feedback_dataset.get('feedback_loop_summary') or {}).get('high_priority_count') or 0)) > 0:
        warnings.append(
            {
                'code': 'high_priority_tuning_recommendations_present',
                'detail': f"high_priority_count={int(((review_feedback_dataset.get('feedback_loop_summary') or {}).get('high_priority_count') or 0))}",
            }
        )

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'ok': len(blocking_issues) == 0,
        'blocking_issues': blocking_issues,
        'warnings': warnings,
        'policy_check': policy_check,
        'contract_check': contract_check,
        'review_feedback': {
            'summary': review_feedback_dataset.get('summary') or {},
            'drift_summary': review_feedback_dataset.get('drift_summary') or {},
            'feedback_loop_summary': review_feedback_dataset.get('feedback_loop_summary') or {},
            'tuning_recommendations': review_feedback_dataset.get('tuning_recommendations') or [],
        },
        'strategy_eval': strategy_eval,
        'shadow_compare': shadow_compare,
        'release_readiness': release_readiness,
    }



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run a unified offline analysis preflight gate.')
    parser.add_argument('--fixtures', default='tests/fixtures', help='fixture directory for strategy eval')
    parser.add_argument('--review-feedback', required=True, help='review feedback JSON or JSONL input')
    parser.add_argument('--metrics', required=True, help='analysis metrics snapshot JSON')
    parser.add_argument('--baseline-dir', required=True, help='baseline report directory for shadow compare')
    parser.add_argument('--candidate-dir', required=True, help='candidate report directory for shadow compare')
    parser.add_argument('--policy-config', default='', help='optional analysis policy JSON path')
    parser.add_argument('--output', default='', help='optional output report path')
    args = parser.parse_args(argv)

    try:
        payload = build_analysis_preflight_report(
            fixtures_dir=Path(args.fixtures),
            review_feedback_path=Path(args.review_feedback),
            metrics_path=Path(args.metrics),
            baseline_dir=Path(args.baseline_dir),
            candidate_dir=Path(args.candidate_dir),
            policy_config_path=Path(args.policy_config) if args.policy_config else None,
        )
    except Exception as exc:
        payload = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'ok': False,
            'blocking_issues': [{'code': 'analysis_preflight_execution_failed', 'detail': str(exc)}],
            'warnings': [],
        }
        rendered = json.dumps(payload, ensure_ascii=False)
        if args.output:
            Path(args.output).write_text(rendered + '\n', encoding='utf-8')
        print(rendered)
        print(f'[FAIL] {exc}', file=sys.stderr)
        return 1

    rendered = json.dumps(payload, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    if payload['ok']:
        print('[OK] Analysis preflight gate passed.')
        return 0
    print('[FAIL] Analysis preflight gate blocked.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
