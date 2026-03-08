from __future__ import annotations

import json
from pathlib import Path

from scripts.replay_analysis_run import replay_analysis_run



def test_replay_analysis_run_rebuilds_report_inputs(tmp_path: Path) -> None:
    report_path = tmp_path / 'report.json'
    report_path.write_text(
        json.dumps(
            {
                'report': {
                    'report_id': 'report_1',
                    'strategy_id': 'survey.teacher.report',
                    'strategy_version': 'v1',
                    'prompt_version': 'v1',
                    'adapter_version': 'v1',
                    'runtime_version': 'v1',
                },
                'artifact_meta': {
                    'parse_confidence': 0.73,
                    'missing_fields': ['question_summaries'],
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    result = replay_analysis_run(report_path=report_path)

    assert result['lineage']['strategy_version'] == 'v1'
    assert result['lineage']['prompt_version'] == 'v1'
    assert result['artifact_meta']['parse_confidence'] == 0.73
