from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api.analysis_metrics_service import AnalysisMetricsService
from services.api.analysis_metrics_store import AnalysisMetricsStore
from services.api.routes.analysis_report_routes import build_router
from services.api.specialist_agents.events import SpecialistRuntimeEvent


class _Core:
    def __init__(self, root: Path) -> None:
        self.DATA_DIR = root / 'data'
        self.analysis_metrics_service = None



def test_analysis_metrics_store_round_trips_snapshot(tmp_path: Path) -> None:
    store = AnalysisMetricsStore(tmp_path / 'data' / 'analysis' / 'metrics_snapshot.json')
    service = AnalysisMetricsService(store=store)
    service.record(
        SpecialistRuntimeEvent(
            phase='started',
            handoff_id='h_1',
            agent_id='survey_analyst',
            task_kind='survey.analysis',
            domain='survey',
            strategy_id='survey.teacher.report',
        )
    )
    service.record_workflow_resolution(
        role='teacher',
        requested_skill_id='',
        effective_skill_id='physics-homework-generator',
        reason='auto_rule',
        confidence=0.64,
        resolution_mode='auto',
        auto_selected=True,
        requested_rewritten=False,
    )

    reloaded = AnalysisMetricsService(store=store)
    snapshot = reloaded.snapshot()

    assert snapshot['counters']['run_count'] == 1
    assert snapshot['workflow_routing']['counters']['resolution_count'] == 1
    assert snapshot['workflow_routing']['by_effective_skill']['physics-homework-generator']['resolved'] == 1



def test_analysis_report_routes_metrics_endpoint_reads_persisted_snapshot(tmp_path: Path) -> None:
    store = AnalysisMetricsStore(tmp_path / 'data' / 'analysis' / 'metrics_snapshot.json')
    writer = AnalysisMetricsService(store=store)
    writer.record_review_downgrade(
        domain='survey',
        strategy_id='survey.teacher.report',
        agent_id='survey_analyst',
        reason_code='invalid_output',
    )

    core = _Core(tmp_path)
    core.analysis_metrics_service = AnalysisMetricsService(store=store)

    app = FastAPI()
    app.include_router(build_router(core))

    with TestClient(app) as client:
        metrics_res = client.get('/teacher/analysis/metrics')

    assert metrics_res.status_code == 200
    payload = metrics_res.json()
    assert payload['metrics']['counters']['review_downgrade_count'] == 1
    assert payload['metrics']['by_domain']['survey']['review_downgraded'] == 1
