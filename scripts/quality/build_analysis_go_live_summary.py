#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Sequence


def build_analysis_go_live_summary(*, artifact_dir: Path, date_text: str, release_ref: str) -> str:
    policy_payload = _load_json_if_exists(artifact_dir / 'analysis-policy.json')
    preflight_payload = _load_json_if_exists(artifact_dir / 'analysis-preflight.json')
    decision_payload = _load_json_if_exists(artifact_dir / 'analysis-rollout-decision.json')
    brief_path = artifact_dir / 'analysis-rollout-brief.md'

    top_owners = list((decision_payload or {}).get('top_owners') or ((preflight_payload.get('ownership_summary') or {}) if preflight_payload else {}).get('top_owners') or [])
    recommended_actions = list((decision_payload or {}).get('recommended_actions') or ((preflight_payload.get('ownership_summary') or {}) if preflight_payload else {}).get('top_actions') or [])

    lines = [
        '# Analysis Go-Live Summary',
        '',
        f'Date: {date_text}',
        f'Release: {release_ref}',
        '',
        '## Release Decision',
        f"Go decision: `{decision_payload.get('decision_label') or decision_payload.get('decision') or 'UNKNOWN'}`",
    ]
    if str(decision_payload.get('summary') or '').strip():
        lines.append(f"Reason: {decision_payload.get('summary')}")
    lines.append('')

    lines.extend(
        [
            '## Verification Snapshot',
            f"- Policy valid: {bool(policy_payload.get('valid'))}",
            f"- Preflight ok: {bool(preflight_payload.get('ok'))}",
            f"- Blocking issues: {len(list(preflight_payload.get('blocking_issues') or []))}",
            f"- Warnings: {len(list(preflight_payload.get('warnings') or []))}",
            '',
        ]
    )

    if top_owners:
        lines.append('## Top Owners')
        for item in top_owners[:5]:
            lines.append(f"- {(item.get('owner_label') or item.get('owner'))} ({int(item.get('count') or 0)})")
        lines.append('')

    if recommended_actions:
        lines.append('## Recommended Actions')
        for item in recommended_actions[:5]:
            lines.append(f"- {(item.get('owner_label') or item.get('owner'))}: {item.get('recommended_action')}")
        lines.append('')

    lines.append('## Source Artifacts')
    lines.append(f"- Brief artifact present: {brief_path.exists()}")
    lines.append(f"- Policy artifact present: {bool(policy_payload)}")
    lines.append(f"- Preflight artifact present: {bool(preflight_payload)}")
    lines.append(f"- Decision artifact present: {bool(decision_payload)}")
    lines.append('')

    return '\n'.join(lines).rstrip() + '\n'



def _load_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    return dict(payload or {}) if isinstance(payload, dict) else {}



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a markdown go-live summary from analysis rollout artifacts.')
    parser.add_argument('--artifact-dir', default='analysis-artifacts', help='directory containing analysis rollout artifacts')
    parser.add_argument('--date', default='', help='date string to embed in the summary')
    parser.add_argument('--release-ref', default='', help='release ref to embed in the summary')
    parser.add_argument('--output', default='', help='optional output markdown path')
    args = parser.parse_args(argv)

    rendered = build_analysis_go_live_summary(
        artifact_dir=Path(args.artifact_dir),
        date_text=str(args.date or 'unknown'),
        release_ref=str(args.release_ref or 'unknown'),
    )
    if args.output:
        Path(args.output).write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
