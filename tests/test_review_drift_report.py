from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/build_review_drift_report.py')



def test_build_review_drift_report_script_outputs_summary(tmp_path: Path) -> None:
    input_path = tmp_path / 'review_feedback.jsonl'
    input_path.write_text(
        '\n'.join(
            [
                json.dumps({
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'strategy_id': 'survey.teacher.report',
                    'operation': 'reject',
                    'disposition': 'rejected',
                    'reason_code': 'invalid_output',
                }, ensure_ascii=False),
                json.dumps({
                    'item_id': 'rvw_2',
                    'domain': 'survey',
                    'strategy_id': 'survey.teacher.report',
                    'operation': 'retry',
                    'disposition': 'retry_requested',
                    'reason_code': 'low_confidence',
                }, ensure_ascii=False),
            ]
        ) + '\n',
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--input', str(input_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['summary']['by_domain']['survey'] == 2
    assert payload['summary']['top_regression_domains'][0]['domain'] == 'survey'


def test_build_review_drift_report_includes_tuning_recommendations(tmp_path: Path) -> None:
    input_path = tmp_path / 'review_feedback.jsonl'
    input_path.write_text(
        '\n'.join(
            [
                json.dumps({
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'strategy_id': 'survey.teacher.report',
                    'operation': 'reject',
                    'disposition': 'rejected',
                    'reason_code': 'invalid_output',
                }, ensure_ascii=False),
            ]
        ) + '\n',
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--input', str(input_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['summary']['by_strategy']['survey.teacher.report'] == 1
    assert payload['tuning_recommendations'][0]['action_type'] == 'harden_output_schema'


def test_build_review_drift_report_accepts_policy_config(tmp_path: Path) -> None:
    input_path = tmp_path / 'review_feedback.jsonl'
    policy_path = tmp_path / 'analysis_policy.json'
    input_path.write_text(
        '\n'.join(
            [
                json.dumps({
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'strategy_id': 'survey.teacher.report',
                    'operation': 'reject',
                    'disposition': 'rejected',
                    'reason_code': 'invalid_output',
                }, ensure_ascii=False),
            ]
        ) + '\n',
        encoding='utf-8',
    )
    policy_path.write_text(
        json.dumps(
            {
                'review_feedback': {
                    'reason_recommendation_specs': {
                        'invalid_output': {
                            'action_type': 'custom_invalid_output_fix',
                            'recommended_action': 'Use the custom invalid-output playbook.',
                            'owner_hint': 'runtime_owner',
                            'default_priority': 'medium',
                        }
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--input', str(input_path), '--policy-config', str(policy_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['tuning_recommendations'][0]['action_type'] == 'custom_invalid_output_fix'
    assert payload['tuning_recommendations'][0]['owner_hint'] == 'runtime_owner'
