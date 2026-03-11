#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Sequence


def build_analysis_release_notes(*, artifact_dir: Path, date_text: str, release_ref: str) -> str:
    decision_payload = _load_json_if_exists(artifact_dir / 'analysis-rollout-decision.json')
    brief_text = _load_text_if_exists(artifact_dir / 'analysis-rollout-brief.md')
    go_live_summary_text = _load_text_if_exists(artifact_dir / 'analysis-go-live-summary.md')

    summary_text = str(decision_payload.get('summary') or '').strip() or 'No rollout decision summary available.'
    decision_label = str(decision_payload.get('decision_label') or decision_payload.get('decision') or 'UNKNOWN')
    verification_lines = _extract_section_lines(go_live_summary_text, 'Verification Snapshot')
    next_action_lines = _extract_section_lines(brief_text, 'Recommended Actions')

    lines = [
        '# Analysis Release Notes',
        '',
        f'Date: {date_text}',
        f'Release: {release_ref}',
        '',
        '## Summary',
        summary_text,
        '',
        '## Release Decision',
        f'- {decision_label}',
        '',
        '## Verification Snapshot',
    ]
    if verification_lines:
        lines.extend(verification_lines)
    else:
        lines.append('- No verification snapshot available.')
    lines.append('')

    lines.append('## Recommended Next Actions')
    if next_action_lines:
        lines.extend(next_action_lines)
    else:
        lines.append('- No recommended next actions available.')
    lines.append('')

    return '\n'.join(lines).rstrip() + '\n'



def _extract_section_lines(text: str, heading: str) -> list[str]:
    if not text:
        return []
    lines = text.splitlines()
    target = f'## {heading}'
    collecting = False
    collected: list[str] = []
    for line in lines:
        if line.strip() == target:
            collecting = True
            continue
        if collecting and line.startswith('## '):
            break
        if collecting and line.strip():
            collected.append(line)
    return collected



def _load_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    return dict(payload or {}) if isinstance(payload, dict) else {}



def _load_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ''
    return path.read_text(encoding='utf-8')



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build markdown analysis release notes from rollout artifacts.')
    parser.add_argument('--artifact-dir', default='analysis-artifacts', help='directory containing analysis rollout artifacts')
    parser.add_argument('--date', default='', help='date string to embed in the notes')
    parser.add_argument('--release-ref', default='', help='release ref to embed in the notes')
    parser.add_argument('--output', default='', help='optional output markdown path')
    args = parser.parse_args(argv)

    rendered = build_analysis_release_notes(
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
