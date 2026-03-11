#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Sequence


def build_analysis_rollout_brief(*, artifact_dir: Path) -> str:
    policy_payload = _load_json_if_exists(artifact_dir / 'analysis-policy.json')
    preflight_payload = _load_json_if_exists(artifact_dir / 'analysis-preflight.json')
    decision_payload = _load_json_if_exists(artifact_dir / 'analysis-rollout-decision.json')

    lines = ['# Analysis Rollout Brief', '']

    if decision_payload:
        lines.append(f"Decision: {decision_payload.get('decision_label') or decision_payload.get('decision')}")
        if str(decision_payload.get('summary') or '').strip():
            lines.append(f"Summary: {decision_payload.get('summary')}")
    else:
        lines.append('Decision: UNKNOWN')
        lines.append('Summary: analysis-rollout-decision.json missing.')
    lines.append('')

    if policy_payload:
        lines.append('## Policy')
        lines.append(f"- Policy valid: {bool(policy_payload.get('valid'))}")
        summary = dict(policy_payload.get('summary') or {})
        lines.append(
            f"- Reason specs: {int(summary.get('reason_recommendation_spec_count') or 0)}; required edge cases: {int(summary.get('required_edge_case_count') or 0)}"
        )
        lines.append('')

    if preflight_payload:
        lines.append('## Preflight')
        blocking_issues = list(preflight_payload.get('blocking_issues') or [])
        warnings = list(preflight_payload.get('warnings') or [])
        lines.append(f"- Preflight ok: {bool(preflight_payload.get('ok'))}")
        lines.append(f"- Blocking issues: {len(blocking_issues)}")
        lines.append(f"- Warnings: {len(warnings)}")
        lines.append('')

    top_owners = list((decision_payload or {}).get('top_owners') or ((preflight_payload.get('ownership_summary') or {}) if preflight_payload else {}).get('top_owners') or [])
    if top_owners:
        lines.append('## Top Owners')
        for item in top_owners[:5]:
            lines.append(f"- {(item.get('owner_label') or item.get('owner'))} ({int(item.get('count') or 0)})")
        lines.append('')

    recommended_actions = list((decision_payload or {}).get('recommended_actions') or ((preflight_payload.get('ownership_summary') or {}) if preflight_payload else {}).get('top_actions') or [])
    if recommended_actions:
        lines.append('## Recommended Actions')
        for item in recommended_actions[:5]:
            lines.append(f"- {(item.get('owner_label') or item.get('owner'))}: {item.get('recommended_action')}")
        lines.append('')

    return '\n'.join(lines).rstrip() + '\n'



def _load_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    return dict(payload or {}) if isinstance(payload, dict) else {}



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a markdown analysis rollout brief artifact.')
    parser.add_argument('--artifact-dir', default='analysis-artifacts', help='directory containing analysis rollout JSON artifacts')
    parser.add_argument('--output', default='', help='optional output markdown path')
    args = parser.parse_args(argv)

    rendered = build_analysis_rollout_brief(artifact_dir=Path(args.artifact_dir))
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
