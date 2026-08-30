from pathlib import Path

from services.api.analysis_metrics_service import AnalysisMetricsService
from services.api.analysis_metrics_store import AnalysisMetricsStore
from services.api.specialist_agents.events import SpecialistRuntimeEvent


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
        effective_skill_id='homework-generator',
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
    assert snapshot['workflow_routing']['by_effective_skill']['homework-generator']['resolved'] == 1



def test_analysis_metrics_store_persists_review_downgrade_snapshot(tmp_path: Path) -> None:
    store = AnalysisMetricsStore(tmp_path / 'data' / 'analysis' / 'metrics_snapshot.json')
    writer = AnalysisMetricsService(store=store)
    writer.record_review_downgrade(
        domain='video_homework',
        strategy_id='video_homework.teacher.report',
        agent_id='video_homework_analyst',
        reason_code='invalid_output',
    )

    payload = AnalysisMetricsService(store=store).snapshot()
    assert payload['counters']['review_downgrade_count'] == 1
    assert payload['by_domain']['video_homework']['review_downgraded'] == 1
