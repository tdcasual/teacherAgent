from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path('scripts/quality/check_analysis_policy.py')



def test_analysis_policy_quality_gate_passes_for_default_repo_config() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout.splitlines()[0])
    assert payload['summary']['reason_recommendation_spec_count'] >= 1
    assert payload['summary']['required_edge_case_count'] >= 1



def test_analysis_policy_quality_gate_fails_for_invalid_config(tmp_path: Path) -> None:
    policy_path = tmp_path / 'invalid_policy.json'
    policy_path.write_text(
        json.dumps(
            {
                'release_readiness': {
                    'thresholds': {
                        'max_timeout_rate': 3,
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--config', str(policy_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 1
    assert '[FAIL]' in proc.stderr



def test_analysis_policy_quality_gate_print_only_does_not_block(tmp_path: Path) -> None:
    policy_path = tmp_path / 'invalid_policy.json'
    policy_path.write_text(
        json.dumps(
            {
                'review_feedback': {
                    'reason_recommendation_specs': {
                        'invalid_output': {
                            'default_priority': 'urgent',
                        }
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--config', str(policy_path), '--print-only'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout.splitlines()[0])
    assert payload['config_path'] == str(policy_path)
    assert payload['valid'] is False


def test_analysis_policy_quality_gate_writes_output_file(tmp_path: Path) -> None:
    output_path = tmp_path / 'analysis_policy.json'

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--output', str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding='utf-8'))
    assert payload['valid'] is True
    assert payload['summary']['strategy_domain_count'] >= 1
