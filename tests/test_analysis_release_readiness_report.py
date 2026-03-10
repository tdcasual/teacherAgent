from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.build_analysis_release_readiness_report import build_analysis_release_readiness_report


SCRIPT_PATH = Path('scripts/build_analysis_release_readiness_report.py')



def test_build_analysis_release_readiness_report_ready_when_all_gates_pass() -> None:
    payload = build_analysis_release_readiness_report(
        contract_check={'ok': True, 'domain_count': 3},
        metrics_snapshot={
            'counters': {
                'invalid_output_count': 0,
                'timeout_count': 0,
                'review_downgrade_count': 1,
            }
        },
        drift_summary={
            'total_items': 2,
            'top_reason_codes': [{'reason_code': 'low_confidence', 'count': 2}],
        },
        shadow_compare_summary={
            'total_pairs': 10,
            'changed_pairs': 1,
            'changed_ratio': 0.1,
            'top_changed_reports': [{'report_id': 'report_2', 'domain': 'survey'}],
        },
    )

    assert payload['ready_for_release'] is True
    assert payload['blocking_issues'] == []
    assert payload['warnings']



def test_build_analysis_release_readiness_report_blocks_on_contract_failure_and_high_change_ratio() -> None:
    payload = build_analysis_release_readiness_report(
        contract_check={'ok': False, 'domain_count': 3},
        metrics_snapshot={
            'counters': {
                'invalid_output_count': 2,
                'timeout_count': 0,
                'review_downgrade_count': 0,
            }
        },
        drift_summary={'total_items': 0, 'top_reason_codes': []},
        shadow_compare_summary={
            'total_pairs': 10,
            'changed_pairs': 6,
            'changed_ratio': 0.6,
            'top_changed_reports': [{'report_id': 'report_2', 'domain': 'survey'}],
        },
        max_changed_ratio=0.2,
        max_invalid_output_count=0,
    )

    assert payload['ready_for_release'] is False
    assert any(issue['code'] == 'contract_check_failed' for issue in payload['blocking_issues'])
    assert any(issue['code'] == 'shadow_compare_changed_ratio_exceeded' for issue in payload['blocking_issues'])
    assert any(issue['code'] == 'invalid_output_count_exceeded' for issue in payload['blocking_issues'])



def test_build_analysis_release_readiness_report_cli_outputs_json(tmp_path: Path) -> None:
    contract_path = tmp_path / 'contract.json'
    metrics_path = tmp_path / 'metrics.json'
    drift_path = tmp_path / 'drift.json'
    shadow_path = tmp_path / 'shadow.json'

    contract_path.write_text(json.dumps({'ok': True, 'domain_count': 3}, ensure_ascii=False), encoding='utf-8')
    metrics_path.write_text(json.dumps({'counters': {'invalid_output_count': 0, 'timeout_count': 0, 'review_downgrade_count': 0}}, ensure_ascii=False), encoding='utf-8')
    drift_path.write_text(json.dumps({'total_items': 1, 'top_reason_codes': []}, ensure_ascii=False), encoding='utf-8')
    shadow_path.write_text(json.dumps({'total_pairs': 2, 'changed_pairs': 0, 'changed_ratio': 0.0, 'top_changed_reports': []}, ensure_ascii=False), encoding='utf-8')

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            '--contract-check',
            str(contract_path),
            '--metrics',
            str(metrics_path),
            '--drift-summary',
            str(drift_path),
            '--shadow-compare',
            str(shadow_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['ready_for_release'] is True
