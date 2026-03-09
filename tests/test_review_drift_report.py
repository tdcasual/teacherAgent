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
