from __future__ import annotations

from pathlib import Path

from services.api.analysis_metrics_service import AnalysisMetricsService
from services.api.analysis_ops_service import AnalysisOpsService
from services.api.review_feedback_store import append_review_feedback_row


def test_analysis_ops_service_merges_metrics_review_feedback_and_replay_summary(tmp_path: Path) -> None:
    metrics_service = AnalysisMetricsService()
    metrics_service.record_workflow_resolution(
        role='teacher',
        requested_skill_id='',
        effective_skill_id='physics-homework-generator',
        reason='auto_rule',
        confidence=0.64,
        resolution_mode='auto',
        auto_selected=True,
        requested_rewritten=False,
    )
    metrics_service.record_review_downgrade(
        domain='survey',
        strategy_id='survey.teacher.report',
        agent_id='survey_analyst',
        reason_code='invalid_output',
    )
    append_review_feedback_row(
        tmp_path / 'analysis' / 'review_feedback.jsonl',
        {
            'item_id': 'survey_1',
            'report_id': 'report_1',
            'teacher_id': 'teacher_1',
            'domain': 'survey',
            'strategy_id': 'survey.teacher.report',
            'target_type': 'report',
            'target_id': 'report_1',
            'status': 'rejected',
            'operation': 'reject',
            'reason': 'low_confidence',
            'reason_code': 'low_confidence',
            'confidence': 0.41,
            'reviewer_id': 'reviewer_1',
            'operator_note': 'invalid executive summary',
            'disposition': 'rejected',
            'created_at': '2026-03-12T11:59:00',
            'updated_at': '2026-03-12T12:00:00',
        },
    )

    service = AnalysisOpsService(
        metrics_service=metrics_service,
        review_feedback_path=tmp_path / 'analysis' / 'review_feedback.jsonl',
        now_iso=lambda: '2026-03-12T12:00:00',
    )

    payload = service.snapshot(window_sec=86400)

    assert payload['generated_at'] == '2026-03-12T12:00:00'
    assert payload['window_sec'] == 86400
    assert payload['workflow_routing']['counters']['resolution_count'] >= 1
    assert payload['review_feedback']['summary']['total_items'] >= 1
    assert 'recommendations' in payload['review_feedback']
    assert payload['ops_summary']['top_failure_reason'] == 'invalid_output'
    assert payload['ops_summary']['top_review_reason'] == 'low_confidence'
    assert payload['ops_summary']['needs_attention'] is True


def test_analysis_ops_service_exposes_recent_rerun_compare_candidates(tmp_path: Path) -> None:
    data_dir = tmp_path / 'data'
    reports_dir = data_dir / 'survey_reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / 'report_2.json').write_text(
        '{"report_id": "report_2", "updated_at": "2026-03-12T12:00:00", "strategy_id": "survey.teacher.report", "rerun_base_lineage": {"report_id": "report_1", "strategy_version": "v1"}}',
        encoding='utf-8',
    )

    service = AnalysisOpsService(
        metrics_service=AnalysisMetricsService(),
        review_feedback_path=data_dir / 'analysis' / 'review_feedback.jsonl',
        data_dir=data_dir,
        now_iso=lambda: '2026-03-12T12:00:00',
    )

    payload = service.snapshot(window_sec=86400)

    assert payload['replay_compare']['candidate_pairs'][0]['report_id'] == 'report_2'
    assert payload['replay_compare']['candidate_pairs'][0]['has_rerun_base_lineage'] is True
    assert payload['replay_compare']['candidate_pairs'][0]['base_report_id'] == 'report_1'

