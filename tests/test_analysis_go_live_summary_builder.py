from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/quality/build_analysis_go_live_summary.py')


def test_build_analysis_go_live_summary_renders_release_decision_and_snapshot(tmp_path: Path) -> None:
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
                'warnings': [{'code': 'review_feedback_present'}],
                'ownership_summary': {
                    'top_owners': [{'owner': 'runtime', 'owner_label': 'Runtime', 'count': 2}],
                    'top_actions': [
                        {
                            'owner': 'runtime',
                            'owner_label': 'Runtime',
                            'count': 2,
                            'recommended_action': 'Stabilize specialist output schema handling.',
                        }
                    ],
                },
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
                'top_owners': [{'owner': 'runtime', 'owner_label': 'Runtime', 'count': 2}],
                'recommended_actions': [
                    {
                        'owner': 'runtime',
                        'owner_label': 'Runtime',
                        'count': 2,
                        'recommended_action': 'Stabilize specialist output schema handling.',
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    (artifact_dir / 'analysis-rollout-brief.md').write_text('# Analysis Rollout Brief\n\nDecision: BLOCKED\n', encoding='utf-8')

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--artifact-dir', str(artifact_dir), '--date', '2026-03-11', '--release-ref', 'main@abc123'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    output = proc.stdout
    assert '# Analysis Go-Live Summary' in output
    assert 'Date: 2026-03-11' in output
    assert 'Release: main@abc123' in output
    assert 'Go decision: `BLOCKED`' in output
    assert 'Verification Snapshot' in output
    assert '- Policy valid: True' in output
    assert '- Blocking issues: 1' in output
    assert 'Top Owners' in output
    assert '- Runtime (2)' in output
    assert 'Recommended Actions' in output
    assert '- Runtime: Stabilize specialist output schema handling.' in output
