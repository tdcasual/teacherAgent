#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Sequence

_KNOWN_ARTIFACTS = (
    {
        'name': 'analysis-policy.json',
        'format': 'json',
        'artifact_type': 'policy',
        'build_order': 10,
        'depends_on': [],
        'generated_by': 'scripts/quality/check_analysis_policy.py',
    },
    {
        'name': 'analysis-preflight.json',
        'format': 'json',
        'artifact_type': 'preflight',
        'build_order': 20,
        'depends_on': [],
        'generated_by': 'scripts/quality/check_analysis_preflight.py',
    },
    {
        'name': 'analysis-rollout-decision.json',
        'format': 'json',
        'artifact_type': 'decision',
        'build_order': 30,
        'depends_on': ['analysis-policy.json', 'analysis-preflight.json'],
        'generated_by': 'scripts/quality/build_analysis_rollout_decision.py',
    },
    {
        'name': 'analysis-rollout-brief.md',
        'format': 'markdown',
        'artifact_type': 'brief',
        'build_order': 40,
        'depends_on': ['analysis-policy.json', 'analysis-preflight.json', 'analysis-rollout-decision.json'],
        'generated_by': 'scripts/quality/build_analysis_rollout_brief.py',
    },
    {
        'name': 'analysis-go-live-summary.md',
        'format': 'markdown',
        'artifact_type': 'go_live_summary',
        'build_order': 50,
        'depends_on': ['analysis-rollout-decision.json', 'analysis-rollout-brief.md'],
        'generated_by': 'scripts/quality/build_analysis_go_live_summary.py',
    },
    {
        'name': 'analysis-release-notes.md',
        'format': 'markdown',
        'artifact_type': 'release_notes',
        'build_order': 60,
        'depends_on': ['analysis-rollout-decision.json', 'analysis-rollout-brief.md', 'analysis-go-live-summary.md'],
        'generated_by': 'scripts/quality/build_analysis_release_notes.py',
    },
    {
        'name': 'analysis-artifact-manifest.json',
        'format': 'json',
        'artifact_type': 'artifact_manifest',
        'build_order': 70,
        'depends_on': [
            'analysis-policy.json',
            'analysis-preflight.json',
            'analysis-rollout-decision.json',
            'analysis-rollout-brief.md',
            'analysis-go-live-summary.md',
            'analysis-release-notes.md',
        ],
        'generated_by': 'scripts/quality/build_analysis_artifact_manifest.py',
    },
)


def build_analysis_artifact_manifest(*, artifact_dir: Path) -> Dict[str, Any]:
    artifacts = []
    for spec in _KNOWN_ARTIFACTS:
        path = artifact_dir / str(spec['name'])
        artifacts.append(
            {
                'name': str(spec['name']),
                'path': str(path),
                'exists': path.exists(),
                'format': str(spec['format']),
                'artifact_type': str(spec['artifact_type']),
                'build_order': int(spec['build_order']),
                'depends_on': list(spec['depends_on']),
                'generated_by': str(spec['generated_by']),
            }
        )
    artifacts.sort(key=lambda item: (int(item['build_order']), str(item['name'])))
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'artifact_dir': str(artifact_dir),
        'artifact_count': len(artifacts),
        'build_sequence': [str(item['name']) for item in artifacts],
        'artifacts': artifacts,
    }



def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build a manifest for analysis rollout artifacts.')
    parser.add_argument('--artifact-dir', default='analysis-artifacts', help='directory containing analysis artifacts')
    parser.add_argument('--output', default='', help='optional output JSON path')
    args = parser.parse_args(argv)

    payload = build_analysis_artifact_manifest(artifact_dir=Path(args.artifact_dir))
    rendered = json.dumps(payload, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
