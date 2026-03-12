from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.compare_analysis_runs import compare_analysis_runs
from scripts.replay_analysis_run import replay_analysis_run

SCRIPT_PATH = Path('scripts/export_analysis_ops_snapshot.py')


def _detail_payload(*, summary: str = '班级对实验设计的理解偏弱', confidence: float = 0.73, review_reason: str = 'low_confidence') -> dict:
    return {
        'report': {
            'report_id': 'report_1',
            'analysis_type': 'survey',
            'target_type': 'report',
            'target_id': 'report_1',
            'strategy_id': 'survey.teacher.report',
            'strategy_version': 'v1',
            'prompt_version': 'v1',
            'adapter_version': 'v1',
            'runtime_version': 'v1',
        },
        'analysis_artifact': {
            'executive_summary': summary,
            'teaching_recommendations': ['补充实验设计例题讲解'],
            'confidence_and_gaps': {'confidence': confidence},
        },
        'artifact_meta': {
            'parse_confidence': confidence,
            'missing_fields': ['question_summaries'],
            'review_reason': review_reason,
        },
        'replay_context': {
            'artifact_payload': {
                'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider'},
                'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高二2403班', 'sample_size': 35},
                'question_summaries': [],
                'group_breakdowns': [],
                'free_text_signals': [],
                'attachments': [],
                'parse_confidence': confidence,
                'missing_fields': ['question_summaries'],
                'provenance': {'source': 'structured'},
            }
        },
    }



def test_replay_analysis_run_rebuilds_report_inputs(tmp_path: Path) -> None:
    report_path = tmp_path / 'report.json'
    report_path.write_text(json.dumps(_detail_payload(), ensure_ascii=False), encoding='utf-8')

    result = replay_analysis_run(report_path=report_path)

    assert result['lineage']['strategy_version'] == 'v1'
    assert result['lineage']['prompt_version'] == 'v1'
    assert result['replay_request']['strategy_target']['strategy_id'] == 'survey.teacher.report'
    assert result['replay_request']['artifact_payload']['survey_meta']['title'] == '课堂反馈问卷'
    assert result['replay_request']['analysis_artifact']['executive_summary'] == '班级对实验设计的理解偏弱'



def test_replay_analysis_run_requires_full_lineage(tmp_path: Path) -> None:
    report_path = tmp_path / 'report-missing-lineage.json'
    payload = _detail_payload()
    payload['report'].pop('runtime_version', None)
    report_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    with pytest.raises(ValueError, match='lineage'):
        replay_analysis_run(report_path=report_path)



def test_replay_analysis_run_requires_artifact_payload(tmp_path: Path) -> None:
    report_path = tmp_path / 'report-missing-artifact.json'
    payload = _detail_payload()
    payload['replay_context'] = {}
    report_path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')

    with pytest.raises(ValueError, match='artifact'):
        replay_analysis_run(report_path=report_path)



def test_compare_analysis_runs_outputs_compact_diff_summary(tmp_path: Path) -> None:
    baseline_path = tmp_path / 'baseline.json'
    candidate_path = tmp_path / 'candidate.json'
    baseline_path.write_text(json.dumps(_detail_payload(), ensure_ascii=False), encoding='utf-8')
    candidate_path.write_text(
        json.dumps(
            _detail_payload(summary='班级理解略有提升，但实验变量控制仍不稳定', confidence=0.61, review_reason='missing_fields'),
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    diff = compare_analysis_runs(baseline_report_path=baseline_path, candidate_report_path=candidate_path)

    assert diff['changed'] is True
    assert diff['summary_changed'] is True
    assert diff['recommendations_changed'] is False
    assert diff['reason_code_changed'] is True
    assert diff['diff']['confidence']['delta'] == pytest.approx(-0.12)
    assert diff['diff']['summary']['before'] == '班级对实验设计的理解偏弱'


def test_export_analysis_ops_snapshot_script_outputs_replay_compare_summary(tmp_path: Path) -> None:
    data_dir = tmp_path / 'data'
    reports_dir = data_dir / 'survey_reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / 'report_2.json').write_text(
        json.dumps(
            {
                'report_id': 'report_2',
                'updated_at': '2026-03-12T12:00:00',
                'strategy_id': 'survey.teacher.report',
                'rerun_base_lineage': {'report_id': 'report_1', 'strategy_version': 'v1'},
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--data-dir', str(data_dir), '--window-sec', '86400'],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert 'runtime_metrics' in payload
    assert 'review_feedback' in payload
    assert payload['replay_compare']['candidate_pairs'][0]['report_id'] == 'report_2'

