from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/quality/render_analysis_rollout_summary.py')


def test_render_analysis_rollout_summary_includes_owners_and_actions(tmp_path: Path) -> None:
    artifact_dir = tmp_path / 'analysis-artifacts'
    artifact_dir.mkdir()
    (artifact_dir / 'analysis-policy.json').write_text(
        json.dumps({'valid': True, 'summary': {'reason_recommendation_spec_count': 8, 'required_edge_case_count': 5}}, ensure_ascii=False),
        encoding='utf-8',
    )
    (artifact_dir / 'analysis-preflight.json').write_text(
        json.dumps(
            {
                'ok': False,
                'blocking_issues': [{'code': 'invalid_output_count_exceeded'}],
                'warnings': [],
                'ownership_summary': {
                    'top_owners': [
                        {'owner': 'runtime', 'owner_label': 'Runtime', 'count': 2},
                        {'owner': 'platform_api', 'owner_label': 'Platform/API', 'count': 1},
                    ],
                    'top_actions': [
                        {'owner': 'runtime', 'owner_label': 'Runtime', 'count': 2, 'recommended_action': 'Stabilize specialist output schema handling.'},
                        {'owner': 'platform_api', 'owner_label': 'Platform/API', 'count': 1, 'recommended_action': 'Fix analysis policy configuration.'},
                    ],
                },
                'classified_blocking_issues': [
                    {'code': 'invalid_output_count_exceeded', 'owner': 'runtime', 'owner_label': 'Runtime'},
                ],
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    (artifact_dir / 'analysis-rollout-decision.json').write_text(
        json.dumps(
            {
                'decision': 'blocked',
                'decision_label': 'BLOCKED',
                'ready_for_rollout': False,
                'summary': 'Analysis rollout is blocked until blocking issues are resolved.',
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--artifact-dir', str(artifact_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    output = proc.stdout
    assert 'Analysis rollout guardrails' in output
    assert 'decision: BLOCKED' in output
    assert 'decision summary: Analysis rollout is blocked until blocking issues are resolved.' in output
    assert 'top owners: Runtime(2), Platform/API(1)' in output
    assert 'recommended actions: Runtime: Stabilize specialist output schema handling.' in output
