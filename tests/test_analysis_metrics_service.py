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



def test_metrics_service_exports_stable_counters_unknown_buckets_and_aux_events() -> None:
    service = AnalysisMetricsService()
    service.record(
        SpecialistRuntimeEvent(
            phase='started',
            handoff_id='handoff_1',
            agent_id='',
            task_kind='survey.analysis',
            domain='',
            strategy_id='',
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
            metadata={'code': 'invalid_output'},
        )
    )
    service.record_review_downgrade(
        domain='survey',
        strategy_id='survey.teacher.report',
        agent_id='survey_analyst',
        reason_code='invalid_output',
    )
    service.record_rerun(domain='survey', strategy_id='survey.teacher.report')

    snapshot = service.snapshot()

    assert snapshot['schema_version'] == 'v1'
    assert snapshot['counters']['run_count'] == 1
    assert snapshot['counters']['fail_count'] == 1
    assert snapshot['counters']['invalid_output_count'] == 1
    assert snapshot['counters']['review_downgrade_count'] == 1
    assert snapshot['counters']['rerun_count'] == 1
    assert snapshot['by_domain']['unknown']['started'] == 1
    assert snapshot['by_strategy']['unknown']['started'] == 1
    assert snapshot['by_agent']['unknown']['started'] == 1
    assert snapshot['by_phase']['review_downgraded'] == 1
    assert snapshot['by_phase']['rerun_requested'] == 1
    assert snapshot['by_reason']['invalid_output'] == 2



def test_metrics_service_tracks_workflow_resolution_and_outcome_feedback_loop() -> None:
    service = AnalysisMetricsService()
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
    service.record_workflow_outcome(
        role='teacher',
        requested_skill_id='',
        effective_skill_id='physics-homework-generator',
        reason='auto_rule',
        resolution_mode='auto',
        outcome='done',
        outcome_reason='done',
    )

    snapshot = service.snapshot()
    routing = snapshot['workflow_routing']

    assert routing['counters']['resolution_count'] == 1
    assert routing['counters']['auto_selected_count'] == 1
    assert routing['counters']['outcome_count'] == 1
    assert routing['by_effective_skill']['physics-homework-generator']['resolved'] == 1
    assert routing['by_effective_skill']['physics-homework-generator']['done'] == 1
    assert routing['by_reason']['auto_rule'] == 1
    assert routing['by_resolution_mode']['auto'] == 1
    assert routing['by_outcome']['done'] == 1
    assert routing['by_outcome_reason']['done'] == 1
