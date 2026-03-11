#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def build_analysis_rollout_summary(*, artifact_dir: Path) -> str:
    policy_path = artifact_dir / 'analysis-policy.json'
    preflight_path = artifact_dir / 'analysis-preflight.json'
    decision_path = artifact_dir / 'analysis-rollout-decision.json'

    lines = ['### Analysis rollout guardrails', '']
    if decision_path.exists():
        decision_payload = json.loads(decision_path.read_text(encoding='utf-8'))
        lines.append(f"- decision: {decision_payload.get('decision_label') or decision_payload.get('decision')}")
        if str(decision_payload.get('summary') or '').strip():
            lines.append(f"- decision summary: {decision_payload.get('summary')}")
    if policy_path.exists():
        payload = json.loads(policy_path.read_text(encoding='utf-8'))
        lines.append(f"- policy valid: {payload.get('valid')}")
        lines.append(
            f"- policy summary: reason_specs={((payload.get('summary') or {}).get('reason_recommendation_spec_count'))} edge_cases={((payload.get('summary') or {}).get('required_edge_case_count'))}"
        )
    else:
        lines.append('- policy artifact missing')

    if preflight_path.exists():
        payload = json.loads(preflight_path.read_text(encoding='utf-8'))
        blocking_issues = list(payload.get('blocking_issues') or [])
        classified_blocking_issues = list(payload.get('classified_blocking_issues') or [])
        ownership_summary = dict(payload.get('ownership_summary') or {})
        top_owners = list(ownership_summary.get('top_owners') or [])
        top_actions = list(ownership_summary.get('top_actions') or [])
        lines.append(f"- preflight ok: {payload.get('ok')}")
        lines.append(f"- preflight blocking issues: {len(blocking_issues)}")
        lines.append(f"- preflight warnings: {len(list(payload.get('warnings') or []))}")
        if top_owners:
            rendered_top_owners = ', '.join(
                f"{item.get('owner_label') or item.get('owner')}({int(item.get('count') or 0)})"
                for item in top_owners[:3]
            )
            lines.append(f"- top owners: {rendered_top_owners}")
        if classified_blocking_issues:
            rendered_issues = '; '.join(
                f"{item.get('code')}→{item.get('owner_label') or item.get('owner')}"
                for item in classified_blocking_issues[:3]
            )
            lines.append(f"- classified blocking issues: {rendered_issues}")
        if top_actions:
            rendered_actions = '; '.join(
                f"{item.get('owner_label') or item.get('owner')}: {item.get('recommended_action')}"
                for item in top_actions[:3]
            )
            lines.append(f"- recommended actions: {rendered_actions}")
    else:
        lines.append('- preflight artifact missing')
    return '\n'.join(lines) + '\n'


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Render analysis rollout artifact summary as markdown.')
    parser.add_argument('--artifact-dir', default='analysis-artifacts', help='directory containing analysis-policy.json and analysis-preflight.json')
    parser.add_argument('--output', default='', help='optional output markdown path')
    args = parser.parse_args(argv)

    rendered = build_analysis_rollout_summary(artifact_dir=Path(args.artifact_dir))
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
