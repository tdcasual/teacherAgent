from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/quality/build_analysis_rollout_decision.py')


def test_build_analysis_rollout_decision_go_for_controlled_rollout(tmp_path: Path) -> None:
    artifact_dir = tmp_path / 'analysis-artifacts'
    artifact_dir.mkdir()
    (artifact_dir / 'analysis-policy.json').write_text(
        json.dumps({'valid': True, 'summary': {'reason_recommendation_spec_count': 8, 'required_edge_case_count': 5}}, ensure_ascii=False),
        encoding='utf-8',
    )
    (artifact_dir / 'analysis-preflight.json').write_text(
        json.dumps({'ok': True, 'blocking_issues': [], 'warnings': [], 'ownership_summary': {'top_owners': [], 'top_actions': []}}, ensure_ascii=False),
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--artifact-dir', str(artifact_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload['decision'] == 'go_for_controlled_rollout'
    assert payload['ready_for_rollout'] is True
    assert payload['top_owners'] == []


def test_build_analysis_rollout_decision_blocks_and_surfaces_actions(tmp_path: Path) -> None:
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

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--artifact-dir', str(artifact_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload['decision'] == 'blocked'
    assert payload['ready_for_rollout'] is False
    assert payload['top_owners'][0]['owner'] == 'runtime'
    assert payload['recommended_actions'][0]['recommended_action'] == 'Stabilize specialist output schema handling.'
