from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.class_report_service import (
    build_class_report_deps,
    enqueue_class_report_review_item,
    write_class_report,
)
from services.api.routes.class_report_routes import build_router


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / 'data'
        self.UPLOADS_DIR = root / 'uploads'



def test_teacher_class_report_routes_expose_list_detail_rerun_and_review_queue(tmp_path: Path) -> None:
    core = _Core(tmp_path)
    deps = build_class_report_deps(core)
    write_class_report(
        'report_1',
        {
            'report_id': 'report_1',
            'job_id': 'job_1',
            'teacher_id': 'teacher_1',
            'class_name': '高二2403班',
            'analysis_type': 'class_report',
            'target_type': 'report',
            'target_id': 'report_1',
            'strategy_id': 'class_signal.teacher.report',
            'status': 'analysis_ready',
            'confidence': 0.86,
            'summary': '班级整体对实验设计理解偏弱',
            'analysis_artifact': {'executive_summary': '班级整体对实验设计理解偏弱'},
            'artifact_meta': {
                'parse_confidence': 0.86,
                'missing_fields': [],
                'provenance': {'source': 'structured'},
                'job_id': 'job_1',
                'report_id': 'report_1',
            },
        },
        deps=deps,
    )
    enqueue_class_report_review_item(
        report_id='report_1',
        teacher_id='teacher_1',
        reason='low_confidence',
        confidence=0.41,
        target_id='report_1',
        deps=deps,
    )

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        list_res = client.get('/teacher/class-reports/reports', params={'teacher_id': 'teacher_1'})
        detail_res = client.get('/teacher/class-reports/reports/report_1', params={'teacher_id': 'teacher_1'})
        rerun_res = client.post(
            '/teacher/class-reports/reports/report_1/rerun',
            json={'teacher_id': 'teacher_1', 'reason': 'refresh'},
        )
        review_res = client.get('/teacher/class-reports/review-queue', params={'teacher_id': 'teacher_1'})

    assert list_res.status_code == 200
    assert list_res.json()['items'][0]['report_id'] == 'report_1'
    assert detail_res.status_code == 200
    assert detail_res.json()['report']['report_id'] == 'report_1'
    assert rerun_res.status_code == 200
    assert rerun_res.json()['status'] == 'rerun_requested'
    assert review_res.status_code == 200
    assert review_res.json()['items'][0]['reason'] == 'low_confidence'



def test_teacher_class_report_routes_delegate_to_analysis_report_plane(monkeypatch, tmp_path: Path) -> None:
    core = _Core(tmp_path)
    called = {}

    import services.api.routes.class_report_routes as class_report_routes

    def _list(**kwargs):
        called['list'] = kwargs
        return {'items': []}

    def _get(**kwargs):
        called['get'] = kwargs
        return {'report': {'report_id': kwargs['report_id']}, 'analysis_artifact': {}, 'artifact_meta': {}}

    def _rerun(**kwargs):
        called['rerun'] = kwargs
        return {'ok': True, 'status': 'rerun_requested', 'domain': 'class_report'}

    def _review(**kwargs):
        called['review'] = kwargs
        return {'items': []}

    monkeypatch.setattr(class_report_routes, 'list_analysis_reports', _list, raising=False)
    monkeypatch.setattr(class_report_routes, 'get_analysis_report', _get, raising=False)
    monkeypatch.setattr(class_report_routes, 'rerun_analysis_report', _rerun, raising=False)
    monkeypatch.setattr(class_report_routes, 'list_analysis_review_queue', _review, raising=False)

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        client.get('/teacher/class-reports/reports', params={'teacher_id': 'teacher_1'})
        client.get('/teacher/class-reports/reports/report_1', params={'teacher_id': 'teacher_1'})
        client.post('/teacher/class-reports/reports/report_1/rerun', json={'teacher_id': 'teacher_1', 'reason': 'refresh'})
        client.get('/teacher/class-reports/review-queue', params={'teacher_id': 'teacher_1'})

    assert called['list']['domain'] == 'class_report'
    assert called['get']['domain'] == 'class_report'
    assert called['rerun']['domain'] == 'class_report'
    assert called['review']['domain'] == 'class_report'
