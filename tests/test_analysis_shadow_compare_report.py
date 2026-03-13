from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.build_analysis_shadow_compare_report import build_analysis_shadow_compare_report

SCRIPT_PATH = Path('scripts/build_analysis_shadow_compare_report.py')



def _detail_payload(*, report_id: str, summary: str = '班级对实验设计的理解偏弱', confidence: float = 0.73, review_reason: str = 'low_confidence') -> dict:
    return {
        'report': {
            'report_id': report_id,
            'analysis_type': 'survey',
            'target_type': 'report',
            'target_id': report_id,
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



def test_build_analysis_shadow_compare_report_aggregates_pairs(tmp_path: Path) -> None:
    baseline_dir = tmp_path / 'baseline'
    candidate_dir = tmp_path / 'candidate'
    baseline_dir.mkdir()
    candidate_dir.mkdir()

    (baseline_dir / 'report_1.json').write_text(json.dumps(_detail_payload(report_id='report_1'), ensure_ascii=False), encoding='utf-8')
    (candidate_dir / 'report_1.json').write_text(json.dumps(_detail_payload(report_id='report_1'), ensure_ascii=False), encoding='utf-8')

    (baseline_dir / 'report_2.json').write_text(json.dumps(_detail_payload(report_id='report_2'), ensure_ascii=False), encoding='utf-8')
    (candidate_dir / 'report_2.json').write_text(
        json.dumps(
            _detail_payload(
                report_id='report_2',
                summary='班级理解略有提升，但实验变量控制仍不稳定',
                confidence=0.61,
                review_reason='missing_fields',
            ),
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )

    report = build_analysis_shadow_compare_report(baseline_dir=baseline_dir, candidate_dir=candidate_dir)

    assert report['total_pairs'] == 2
    assert report['changed_pairs'] == 1
    assert report['changed_ratio'] == pytest.approx(0.5)
    assert report['by_domain']['survey']['total_pairs'] == 2
    assert report['pairs'][0]['report_id'] == 'report_1'
    assert report['pairs'][1]['report_id'] == 'report_2'
    assert report['pairs'][1]['changed'] is True
    assert report['top_changed_reports'][0]['report_id'] == 'report_2'



def test_build_analysis_shadow_compare_report_requires_matching_file_sets(tmp_path: Path) -> None:
    baseline_dir = tmp_path / 'baseline'
    candidate_dir = tmp_path / 'candidate'
    baseline_dir.mkdir()
    candidate_dir.mkdir()

    (baseline_dir / 'report_1.json').write_text(json.dumps(_detail_payload(report_id='report_1'), ensure_ascii=False), encoding='utf-8')

    with pytest.raises(ValueError, match='matching report files'):
        build_analysis_shadow_compare_report(baseline_dir=baseline_dir, candidate_dir=candidate_dir)



def test_build_analysis_shadow_compare_report_cli_outputs_json(tmp_path: Path) -> None:
    baseline_dir = tmp_path / 'baseline'
    candidate_dir = tmp_path / 'candidate'
    baseline_dir.mkdir()
    candidate_dir.mkdir()

    (baseline_dir / 'report_1.json').write_text(json.dumps(_detail_payload(report_id='report_1'), ensure_ascii=False), encoding='utf-8')
    (candidate_dir / 'report_1.json').write_text(json.dumps(_detail_payload(report_id='report_1'), ensure_ascii=False), encoding='utf-8')

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--baseline-dir', str(baseline_dir), '--candidate-dir', str(candidate_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['total_pairs'] == 1
    assert payload['changed_pairs'] == 0
