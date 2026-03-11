from __future__ import annotations

from services.api.analysis_gate_ownership_service import (
    classify_blocking_issues,
    summarize_issue_ownership,
)


def test_classify_runtime_blocking_issue_to_runtime_owner() -> None:
    issues = classify_blocking_issues(blocking_issues=[{'code': 'invalid_output_count_exceeded', 'detail': 'invalid_output_count=1'}])
    assert issues[0]['owner'] == 'runtime'
    assert issues[0]['owner_label'] == 'Runtime'
    assert issues[0]['recommended_action']


def test_classify_contract_failure_to_platform_api_owner() -> None:
    issues = classify_blocking_issues(blocking_issues=[{'code': 'contract_check_failed', 'detail': 'analysis domain contract check did not pass'}])
    assert issues[0]['owner'] == 'platform_api'
    assert issues[0]['owner_label'] == 'Platform/API'


def test_classify_eval_failure_to_evaluation_owner() -> None:
    issues = classify_blocking_issues(blocking_issues=[{'code': 'strategy_eval_not_ready_for_expansion', 'detail': 'ready_for_expansion=false expectation_failures=1'}])
    assert issues[0]['owner'] == 'evaluation'
    assert issues[0]['owner_label'] == 'Evaluation'


def test_summarize_issue_ownership_groups_counts_and_actions() -> None:
    summary = summarize_issue_ownership(
        classified_issues=[
            {
                'code': 'invalid_output_count_exceeded',
                'detail': 'invalid_output_count=1',
                'owner': 'runtime',
                'owner_label': 'Runtime',
                'recommended_action': 'Stabilize runtime quality gates.',
            },
            {
                'code': 'timeout_count_exceeded',
                'detail': 'timeout_count=2',
                'owner': 'runtime',
                'owner_label': 'Runtime',
                'recommended_action': 'Reduce timeout pressure.',
            },
            {
                'code': 'contract_check_failed',
                'detail': 'analysis domain contract check did not pass',
                'owner': 'platform_api',
                'owner_label': 'Platform/API',
                'recommended_action': 'Reconcile contract and implementation.',
            },
        ]
    )
    assert summary['total_blocking_issues'] == 3
    assert summary['by_owner']['runtime']['count'] == 2
    assert summary['by_owner']['platform_api']['count'] == 1
    assert 'invalid_output_count_exceeded' in summary['by_owner']['runtime']['codes']
    assert summary['top_actions'][0]['owner'] == 'runtime'
    assert summary['top_actions'][0]['count'] == 1
    assert summary['top_actions'][0]['recommended_action'] == 'Reduce timeout pressure.'
