from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from services.api.review_feedback_service import (
    build_review_feedback_dataset,
    build_review_feedback_summary,
)

SCRIPT_PATH = Path('scripts/export_review_feedback_dataset.py')



def test_review_feedback_service_aggregates_rejections_and_retries() -> None:
    summary = build_review_feedback_summary(
        items=[
            {
                'item_id': 'rvw_1',
                'domain': 'survey',
                'operation': 'reject',
                'reason_code': 'low_confidence',
            },
            {
                'item_id': 'rvw_2',
                'domain': 'class_report',
                'operation': 'retry',
                'reason_code': 'missing_fields',
            },
        ]
    )

    assert summary['total_items'] == 2
    assert summary['by_action']['reject'] == 1
    assert summary['by_action']['retry'] == 1
    assert summary['by_domain']['survey'] == 1
    assert summary['by_reason_code']['low_confidence'] == 1



def test_review_feedback_dataset_exports_strategy_disposition_and_drift_breakdowns() -> None:
    dataset = build_review_feedback_dataset(
        items=[
            {
                'item_id': 'rvw_1',
                'report_id': 'report_1',
                'teacher_id': 'teacher_1',
                'domain': 'survey',
                'strategy_id': 'survey.teacher.report',
                'operation': 'retry',
                'status': 'retry_requested',
                'disposition': 'retry_requested',
                'reason_code': 'low_confidence',
                'operator_note': 'rerun requested from workbench',
                'reviewer_id': 'reviewer_1',
            },
            {
                'item_id': 'rvw_2',
                'report_id': 'report_2',
                'teacher_id': 'teacher_1',
                'domain': 'survey',
                'strategy_id': 'survey.teacher.report',
                'operation': 'reject',
                'status': 'rejected',
                'disposition': 'rejected',
                'reason_code': 'missing_fields',
                'operator_note': 'insufficient evidence',
                'reviewer_id': 'reviewer_2',
            },
        ]
    )

    assert dataset['summary']['total_items'] == 2
    assert dataset['summary']['by_strategy']['survey.teacher.report'] == 2
    assert dataset['summary']['by_disposition']['retry_requested'] == 1
    assert dataset['summary']['by_domain_reason_code']['survey']['low_confidence'] == 1
    assert dataset['summary']['by_domain_reason_code']['survey']['missing_fields'] == 1
    assert dataset['items'][0]['strategy_id'] == 'survey.teacher.report'
    assert dataset['items'][0]['operator_note'] == 'rerun requested from workbench'



def test_export_review_feedback_dataset_script_outputs_json_summary(tmp_path: Path) -> None:
    input_path = tmp_path / 'review_feedback.jsonl'
    input_path.write_text(
        '\n'.join(
            [
                json.dumps(
                    {
                        'item_id': 'rvw_1',
                        'report_id': 'report_1',
                        'teacher_id': 'teacher_1',
                        'domain': 'survey',
                        'strategy_id': 'survey.teacher.report',
                        'operation': 'retry',
                        'status': 'retry_requested',
                        'disposition': 'retry_requested',
                        'reason_code': 'low_confidence',
                    },
                    ensure_ascii=False,
                )
            ]
        )
        + '\n',
        encoding='utf-8',
    )

    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), '--input', str(input_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload['summary']['total_items'] == 1
    assert payload['summary']['by_strategy']['survey.teacher.report'] == 1


def test_review_feedback_service_builds_drift_summary() -> None:
    from services.api.review_feedback_service import summarize_review_feedback_drift

    summary = summarize_review_feedback_drift(
        items=[
            {
                'item_id': 'rvw_1',
                'domain': 'survey',
                'strategy_id': 'survey.teacher.report',
                'operation': 'reject',
                'disposition': 'rejected',
                'reason_code': 'invalid_output',
            },
            {
                'item_id': 'rvw_2',
                'domain': 'survey',
                'strategy_id': 'survey.teacher.report',
                'operation': 'retry',
                'disposition': 'retry_requested',
                'reason_code': 'low_confidence',
            },
            {
                'item_id': 'rvw_3',
                'domain': 'class_report',
                'strategy_id': 'class_signal.teacher.report',
                'operation': 'resolve',
                'disposition': 'resolved',
                'reason_code': 'missing_fields',
            },
        ]
    )

    assert summary['total_items'] == 3
    assert summary['by_domain']['survey'] == 2
    assert summary['by_strategy']['survey.teacher.report'] == 2
    assert summary['by_reason_code']['invalid_output'] == 1
    assert summary['top_regression_domains'][0]['domain'] == 'survey'
    assert summary['top_regression_strategies'][0]['strategy_id'] == 'survey.teacher.report'


def test_review_feedback_dataset_builds_tuning_recommendations() -> None:
    dataset = build_review_feedback_dataset(
        items=[
            {
                'item_id': 'rvw_1',
                'domain': 'survey',
                'strategy_id': 'survey.teacher.report',
                'operation': 'reject',
                'disposition': 'rejected',
                'reason_code': 'invalid_output',
            },
            {
                'item_id': 'rvw_2',
                'domain': 'survey',
                'strategy_id': 'survey.teacher.report',
                'operation': 'retry',
                'disposition': 'retry_requested',
                'reason_code': 'low_confidence',
            },
        ]
    )

    assert dataset['feedback_loop_summary']['total_recommendations'] >= 2
    assert any(item['scope_id'] == 'survey.teacher.report' and item['action_type'] == 'harden_output_schema' for item in dataset['tuning_recommendations'])
    assert any(item['scope_id'] == 'survey.teacher.report' and item['action_type'] == 'tune_selector_thresholds' for item in dataset['tuning_recommendations'])


def test_review_feedback_dataset_uses_policy_reason_specs_and_priority_rules() -> None:
    dataset = build_review_feedback_dataset(
        items=[
            {
                'item_id': 'rvw_1',
                'domain': 'survey',
                'strategy_id': 'survey.teacher.report',
                'operation': 'reject',
                'disposition': 'rejected',
                'reason_code': 'invalid_output',
            }
        ],
        policy={
            'review_feedback': {
                'reason_recommendation_specs': {
                    'invalid_output': {
                        'action_type': 'custom_invalid_output_fix',
                        'default_priority': 'low',
                        'recommended_action': 'Use the custom invalid-output playbook.',
                        'owner_hint': 'runtime_owner',
                    }
                },
                'priority_rules': {
                    'high_if_rejected_count_at_least': 2,
                    'medium_if_retry_count_at_least': 1,
                    'medium_if_item_count_at_least': 1,
                },
            }
        },
    )

    recommendation = dataset['tuning_recommendations'][0]
    assert recommendation['action_type'] == 'custom_invalid_output_fix'
    assert recommendation['recommended_action'] == 'Use the custom invalid-output playbook.'
    assert recommendation['owner_hint'] == 'runtime_owner'
    assert recommendation['priority'] == 'medium'
