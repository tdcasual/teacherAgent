from __future__ import annotations

import pytest

from services.api.specialist_agents.metrics_service import SpecialistMetricsService


def test_specialist_metrics_service_derives_quality_rates_and_release_gates() -> None:
    summary = SpecialistMetricsService(
        max_timeout_rate=0.1,
        max_invalid_output_rate=0.1,
        max_budget_rejection_rate=0.05,
        max_fallback_rate=0.2,
    ).summarize(
        {
            'counters': {
                'run_count': 10,
                'timeout_count': 2,
                'invalid_output_count': 1,
                'budget_rejection_count': 1,
                'fallback_count': 3,
            },
            'by_phase': {'completed': 7},
        }
    )

    assert summary['run_count'] == 10
    assert summary['completed_count'] == 7
    assert summary['success_rate'] == pytest.approx(0.7)
    assert summary['timeout_rate'] == pytest.approx(0.2)
    assert summary['invalid_output_rate'] == pytest.approx(0.1)
    assert summary['budget_rejection_rate'] == pytest.approx(0.1)
    assert summary['fallback_rate'] == pytest.approx(0.3)
    assert summary['ready_for_release'] is False
    assert any(issue['code'] == 'specialist_timeout_rate_exceeded' for issue in summary['blocking_issues'])
    assert any(issue['code'] == 'specialist_budget_rejection_rate_exceeded' for issue in summary['blocking_issues'])
    assert any(issue['code'] == 'specialist_fallback_rate_exceeded' for issue in summary['blocking_issues'])


def test_specialist_metrics_service_summarizes_grouped_strategy_snapshots() -> None:
    grouped = SpecialistMetricsService(
        max_timeout_rate=0.1,
        max_invalid_output_rate=0.1,
        max_budget_rejection_rate=0.05,
        max_fallback_rate=0.2,
    ).summarize_grouped(
        {
            'survey.teacher.report': {
                'counters': {'run_count': 5, 'timeout_count': 0, 'invalid_output_count': 0, 'budget_rejection_count': 0, 'fallback_count': 0},
                'by_phase': {'completed': 5},
            },
            'video_homework.teacher.report': {
                'counters': {'run_count': 4, 'timeout_count': 1, 'invalid_output_count': 0, 'budget_rejection_count': 0, 'fallback_count': 1},
                'by_phase': {'completed': 2},
            },
        }
    )

    assert grouped['survey.teacher.report']['ready_for_release'] is True
    assert grouped['video_homework.teacher.report']['ready_for_release'] is False
    assert grouped['video_homework.teacher.report']['timeout_rate'] == pytest.approx(0.25)
