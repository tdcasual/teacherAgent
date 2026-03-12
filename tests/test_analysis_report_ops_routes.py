from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.analysis_metrics_service import AnalysisMetricsService
from services.api.review_feedback_store import append_review_feedback_row
from services.api.routes.analysis_report_routes import build_router
from services.api.survey_repository import (
    append_survey_review_queue_item,
    write_survey_bundle,
    write_survey_report,
)


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'
        self.analysis_metrics_service = AnalysisMetricsService()



def _seed_survey_report(core: _Core) -> None:
    write_survey_report(
        'report_1',
        {
            'report_id': 'report_1',
            'job_id': 'job_1',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'analysis_ready',
            'confidence': 0.86,
            'summary': '整体掌握稳定。',
            'analysis_artifact': {'executive_summary': '整体掌握稳定。'},
            'bundle_meta': {'parse_confidence': 0.86, 'missing_fields': []},
            'created_at': '2026-03-06T10:00:00',
            'updated_at': '2026-03-06T10:05:00',
        },
        core=core,
    )
    write_survey_bundle(
        'job_1',
        {
            'survey_meta': {'title': '课堂反馈问卷', 'provider': 'provider', 'submission_id': 'sub-1'},
            'audience_scope': {'teacher_id': 'teacher_1', 'class_name': '高二2403班', 'sample_size': 35},
            'question_summaries': [],
            'group_breakdowns': [],
            'free_text_signals': [],
            'attachments': [],
            'parse_confidence': 0.86,
            'missing_fields': [],
            'provenance': {'source': 'structured'},
        },
        core=core,
    )
    append_survey_review_queue_item(
        {'report_id': 'report_1', 'teacher_id': 'teacher_1', 'reason': 'low_confidence', 'confidence': 0.41},
        core=core,
    )



def test_analysis_report_routes_expose_ops_summary_and_bulk_rerun(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    _seed_survey_report(core)

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        list_res = client.get('/teacher/analysis/reports', params={'teacher_id': 'teacher_1'})
        bulk_res = client.post(
            '/teacher/analysis/reports/bulk-rerun',
            json={'teacher_id': 'teacher_1', 'report_ids': ['report_1'], 'reason': 'ops_refresh'},
        )

    assert list_res.status_code == 200
    assert list_res.json()['summary']['total_reports'] == 1
    assert list_res.json()['summary']['review_required_reports'] == 1
    assert list_res.json()['summary']['domains'][0]['domain'] == 'survey'

    assert bulk_res.status_code == 200
    payload = bulk_res.json()
    assert payload['requested_count'] == 1
    assert payload['accepted_count'] == 1
    assert payload['items'][0]['report_id'] == 'report_1'
    assert payload['items'][0]['domain'] == 'survey'



def test_analysis_report_bulk_rerun_route_rejects_empty_ids(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        res = client.post(
            '/teacher/analysis/reports/bulk-rerun',
            json={'teacher_id': 'teacher_1', 'report_ids': [], 'reason': 'ops_refresh'},
        )

    assert res.status_code == 422



def test_analysis_report_ops_route_exposes_unified_ops_snapshot(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    core.analysis_metrics_service.record_workflow_resolution(
        role='teacher',
        requested_skill_id='',
        effective_skill_id='physics-homework-generator',
        reason='auto_rule',
        confidence=0.64,
        resolution_mode='auto',
        auto_selected=True,
        requested_rewritten=False,
    )
    append_review_feedback_row(
        core.DATA_DIR / 'analysis' / 'review_feedback.jsonl',
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

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        res = client.get('/teacher/analysis/ops', params={'window_sec': 86400})

    assert res.status_code == 200
    payload = res.json()
    assert payload['window_sec'] == 86400
    assert payload['workflow_routing']['counters']['resolution_count'] == 1
    assert payload['review_feedback']['summary']['total_items'] == 1
    assert payload['ops_summary']['top_review_reason'] == 'low_confidence'
