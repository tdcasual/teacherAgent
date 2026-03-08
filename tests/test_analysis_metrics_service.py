from __future__ import annotations

from services.api.analysis_metrics_service import AnalysisMetricsService
from services.api.specialist_agents.events import SpecialistRuntimeEvent



def test_metrics_service_counts_completed_failed_and_timeout_events() -> None:
    service = AnalysisMetricsService()
    service.record(
        SpecialistRuntimeEvent(
            phase='completed',
            handoff_id='handoff_1',
            agent_id='survey_analyst',
            task_kind='survey.analysis',
            domain='survey',
            strategy_id='survey.teacher.report',
        )
    )
    service.record(
        SpecialistRuntimeEvent(
            phase='failed',
            handoff_id='handoff_2',
            agent_id='survey_analyst',
            task_kind='survey.analysis',
            domain='survey',
            strategy_id='survey.teacher.report',
            metadata={'code': 'timeout'},
        )
    )

    snapshot = service.snapshot()

    assert snapshot['by_phase']['completed'] == 1
    assert snapshot['by_phase']['failed'] == 1
    assert snapshot['by_domain']['survey']['completed'] == 1
    assert snapshot['by_domain']['survey']['failed'] == 1
    assert snapshot['by_strategy']['survey.teacher.report']['completed'] == 1
    assert snapshot['by_strategy']['survey.teacher.report']['failed'] == 1
    assert snapshot['by_reason']['timeout'] == 1
