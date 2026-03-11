#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence


def build_analysis_rollout_decision(*, artifact_dir: Path) -> Dict[str, Any]:
    policy_payload = _load_json_if_exists(artifact_dir / 'analysis-policy.json')
    preflight_payload = _load_json_if_exists(artifact_dir / 'analysis-preflight.json')

    artifact_gaps: list[str] = []
    if not policy_payload:
        artifact_gaps.append('analysis-policy.json missing')
    if not preflight_payload:
        artifact_gaps.append('analysis-preflight.json missing')

    policy_valid = bool((policy_payload or {}).get('valid'))
    blocking_issues = list((preflight_payload or {}).get('blocking_issues') or [])
    warnings = list((preflight_payload or {}).get('warnings') or [])
    ownership_summary = dict((preflight_payload or {}).get('ownership_summary') or {})
    top_owners = list(ownership_summary.get('top_owners') or [])
    recommended_actions = list(ownership_summary.get('top_actions') or [])

    ready_for_rollout = bool(preflight_payload) and policy_valid and len(blocking_issues) == 0 and bool((preflight_payload or {}).get('ok'))
    decision = 'go_for_controlled_rollout' if ready_for_rollout else 'blocked'
    decision_label = 'GO for controlled rollout' if ready_for_rollout else 'BLOCKED'

    if artifact_gaps:
        summary = 'Analysis rollout is blocked because required guardrail artifacts are missing.'
    elif not policy_valid:
        summary = 'Analysis rollout is blocked because policy validation did not pass.'
    elif blocking_issues:
        summary = 'Analysis rollout is blocked until blocking issues are resolved.'
    else:
        summary = 'Analysis rollout is ready for controlled rollout.'

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'decision': decision,
        'decision_label': decision_label,
        'ready_for_rollout': ready_for_rollout,
        'policy_valid': policy_valid,
        'blocking_issue_count': len(blocking_issues),
        'warning_count': len(warnings),
        'artifact_gaps': artifact_gaps,
        'summary': summary,
        'top_owners': top_owners,
        'recommended_actions': recommended_actions,
    }



def _load_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    return dict(payload or {}) if isinstance(payload, dict) else {}



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a structured analysis rollout decision artifact.')
    parser.add_argument('--artifact-dir', default='analysis-artifacts', help='directory containing analysis-policy.json and analysis-preflight.json')
    parser.add_argument('--output', default='', help='optional output JSON path')
    args = parser.parse_args(argv)

    payload = build_analysis_rollout_decision(artifact_dir=Path(args.artifact_dir))
    rendered = json.dumps(payload, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
