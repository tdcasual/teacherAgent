from __future__ import annotations

from services.api.review_feedback_service import build_review_feedback_summary



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
