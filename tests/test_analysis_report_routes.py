from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.analysis_metrics_service import AnalysisMetricsService
from services.api.routes.analysis_report_routes import build_router
from services.api.specialist_agents.events import SpecialistRuntimeEvent
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



def test_analysis_report_routes_expose_unified_list_detail_rerun_and_review_queue(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    write_survey_report(
        'report_1',
        {
            'report_id': 'report_1',
            'job_id': 'job_1',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'status': 'analysis_ready',
            'confidence': 0.86,
            'summary': '班级整体对实验设计理解偏弱',
            'analysis_artifact': {'executive_summary': '班级整体对实验设计理解偏弱'},
            'bundle_meta': {'parse_confidence': 0.86, 'missing_fields': []},
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

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        list_res = client.get('/teacher/analysis/reports', params={'teacher_id': 'teacher_1', 'domain': 'survey'})
        detail_res = client.get('/teacher/analysis/reports/report_1', params={'teacher_id': 'teacher_1', 'domain': 'survey'})
        rerun_res = client.post('/teacher/analysis/reports/report_1/rerun', json={'teacher_id': 'teacher_1', 'domain': 'survey', 'reason': 'refresh'})
        review_res = client.get('/teacher/analysis/review-queue', params={'teacher_id': 'teacher_1', 'domain': 'survey'})

    assert list_res.status_code == 200
    assert list_res.json()['items'][0]['report_id'] == 'report_1'
    assert list_res.json()['items'][0]['analysis_type'] == 'survey'
    assert detail_res.status_code == 200
    assert detail_res.json()['report']['strategy_id'] == 'survey.teacher.report'
    assert rerun_res.status_code == 200
    assert rerun_res.json()['domain'] == 'survey'
    assert review_res.status_code == 200
    assert review_res.json()['items'][0]['domain'] == 'survey'
    assert core.analysis_metrics_service.snapshot()['counters']['rerun_count'] == 1


def test_analysis_report_routes_expose_review_queue_summary_and_actions(monkeypatch, tmp_path: Path) -> None:
    core = _Core(tmp_path)
    called = {}

    import services.api.routes.analysis_report_routes as analysis_report_routes

    def _review(**kwargs):
        called['review'] = kwargs
        return {
            'items': [
                {
                    'item_id': 'rvw_1',
                    'domain': 'survey',
                    'report_id': 'report_1',
                    'teacher_id': 'teacher_1',
                    'status': 'queued',
                    'reason': 'low_confidence_bundle',
                    'reason_code': 'low_confidence',
                    'disposition': 'open',
                }
            ],
            'summary': {'total_items': 1, 'unresolved_items': 1, 'domains': [{'domain': 'survey', 'total_items': 1, 'unresolved_items': 1}]},
        }

    def _action(**kwargs):
        called['action'] = kwargs
        return {
            'item_id': 'rvw_1',
            'domain': 'survey',
            'status': 'retry_requested',
            'disposition': 'retry_requested',
        }

    monkeypatch.setattr(analysis_report_routes, 'list_analysis_review_queue', _review, raising=False)
    monkeypatch.setattr(analysis_report_routes, 'operate_analysis_review_queue_item', _action, raising=False)

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        review_res = client.get('/teacher/analysis/review-queue', params={'teacher_id': 'teacher_1', 'status': 'unresolved'})
        action_res = client.post(
            '/teacher/analysis/review-queue/rvw_1/actions',
            json={
                'teacher_id': 'teacher_1',
                'domain': 'survey',
                'action': 'retry',
                'reviewer_id': 'reviewer_1',
                'operator_note': 'rerun requested from workbench',
            },
        )

    assert review_res.status_code == 200
    assert review_res.json()['summary']['unresolved_items'] == 1
    assert action_res.status_code == 200
    assert action_res.json()['status'] == 'retry_requested'
    assert called['review']['status'] == 'unresolved'
    assert called['action']['action'] == 'retry'
    assert called['action']['item_id'] == 'rvw_1'


def test_analysis_report_routes_expose_analysis_metrics_snapshot(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    core.analysis_metrics_service.record_review_downgrade(
        domain='survey',
        strategy_id='survey.teacher.report',
        agent_id='survey_analyst',
        reason_code='invalid_output',
    )

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        metrics_res = client.get('/teacher/analysis/metrics')

    assert metrics_res.status_code == 200
    payload = metrics_res.json()
    assert payload['ok'] is True
    assert payload['metrics']['schema_version'] == 'v1'
    assert payload['metrics']['counters']['review_downgrade_count'] == 1
    assert payload['metrics']['by_domain']['survey']['review_downgraded'] == 1


def test_analysis_report_routes_expose_specialist_quality_summary(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    core.analysis_metrics_service.record(
        SpecialistRuntimeEvent(
            phase='started',
            handoff_id='handoff_1',
            agent_id='video_homework_analyst',
            task_kind='video_homework.analysis',
            domain='video_homework',
            strategy_id='video_homework.teacher.report',
        )
    )
    core.analysis_metrics_service.record(
        SpecialistRuntimeEvent(
            phase='failed',
            handoff_id='handoff_1',
            agent_id='video_homework_analyst',
            task_kind='video_homework.analysis',
            domain='video_homework',
            strategy_id='video_homework.teacher.report',
            metadata={'code': 'budget_exceeded'},
        )
    )

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        metrics_res = client.get('/teacher/analysis/metrics')

    assert metrics_res.status_code == 200
    payload = metrics_res.json()
    assert payload['metrics']['specialist_quality']['budget_rejection_rate'] == 1.0
    assert payload['metrics']['specialist_quality']['ready_for_release'] is False


def test_analysis_report_routes_support_windowed_strategy_quality(tmp_path: Path) -> None:
    current_ts = [1_000.0]
    core = _Core(tmp_path)
    core.analysis_metrics_service = AnalysisMetricsService(now_ts=lambda: current_ts[0])
    core.analysis_metrics_service.record(
        SpecialistRuntimeEvent(
            phase='started',
            handoff_id='handoff_old',
            agent_id='survey_analyst',
            task_kind='survey.analysis',
            domain='survey',
            strategy_id='survey.teacher.report',
        )
    )
    core.analysis_metrics_service.record(
        SpecialistRuntimeEvent(
            phase='completed',
            handoff_id='handoff_old',
            agent_id='survey_analyst',
            task_kind='survey.analysis',
            domain='survey',
            strategy_id='survey.teacher.report',
        )
    )
    current_ts[0] = 8_200.0
    core.analysis_metrics_service.record(
        SpecialistRuntimeEvent(
            phase='started',
            handoff_id='handoff_new',
            agent_id='video_homework_analyst',
            task_kind='video_homework.analysis',
            domain='video_homework',
            strategy_id='video_homework.teacher.report',
        )
    )
    core.analysis_metrics_service.record(
        SpecialistRuntimeEvent(
            phase='failed',
            handoff_id='handoff_new',
            agent_id='video_homework_analyst',
            task_kind='video_homework.analysis',
            domain='video_homework',
            strategy_id='video_homework.teacher.report',
            metadata={'code': 'timeout'},
        )
    )

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        metrics_res = client.get('/teacher/analysis/metrics', params={'window_sec': 3600, 'group_by': 'strategy'})

    assert metrics_res.status_code == 200
    payload = metrics_res.json()['metrics']
    assert payload['window_sec'] == 3600
    assert 'survey' not in payload['by_domain']
    assert payload['specialist_quality_by_strategy']['video_homework.teacher.report']['ready_for_release'] is False
    assert 'survey.teacher.report' not in payload['specialist_quality_by_strategy']
