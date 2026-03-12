from __future__ import annotations

from pathlib import Path

from services.api.analysis_metadata_repository import FileBackedAnalysisMetadataRepository
from services.api.review_feedback_store import read_review_feedback_rows
from services.api.review_queue_service import (
    ReviewQueueDeps,
    dismiss_review_item,
    enqueue_review_item,
    escalate_review_item,
    list_review_items,
    retry_review_item,
)


def _deps(tmp_path: Path) -> ReviewQueueDeps:
    return ReviewQueueDeps(
        metadata_repo=FileBackedAnalysisMetadataRepository(base_dir=tmp_path),
        queue_log='review/events.jsonl',
        review_feedback_log=tmp_path / 'analysis' / 'review_feedback.jsonl',
        now_iso=lambda: '2026-03-07T10:00:00',
    )



def test_review_queue_exposes_reason_taxonomy_unresolved_backlog_and_domain_summary(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    enqueue_review_item(
        domain='survey',
        report_id='report_1',
        teacher_id='teacher_1',
        reason='low_confidence_bundle',
        confidence=0.41,
        target_type='report',
        target_id='report_1',
        deps=deps,
    )
    enqueue_review_item(
        domain='class_report',
        report_id='report_9',
        teacher_id='teacher_1',
        reason='missing_fields',
        confidence=0.66,
        target_type='class',
        target_id='class_2403',
        deps=deps,
    )

    result = list_review_items(teacher_id='teacher_1', domain=None, status='unresolved', deps=deps)

    assert [item['report_id'] for item in result['items']] == ['report_1', 'report_9']
    assert result['items'][0]['reason_code'] == 'low_confidence'
    assert result['items'][0]['disposition'] == 'open'
    assert result['summary']['total_items'] == 2
    assert result['summary']['unresolved_items'] == 2
    assert result['summary']['reason_counts']['low_confidence'] == 1
    assert result['summary']['domains'][0]['domain'] == 'class_report'
    assert result['summary']['domains'][1]['domain'] == 'survey'



def test_review_queue_supports_retry_dismiss_and_escalate_states(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    queued = enqueue_review_item(
        domain='survey',
        report_id='report_1',
        teacher_id='teacher_1',
        reason='low_confidence',
        confidence=0.41,
        target_type='report',
        target_id='report_1',
        deps=deps,
    )
    retry_item = retry_review_item(
        item_id=queued['item_id'],
        reviewer_id='reviewer_1',
        operator_note='rerun with refreshed bundle',
        deps=deps,
    )

    queued_2 = enqueue_review_item(
        domain='survey',
        report_id='report_2',
        teacher_id='teacher_1',
        reason='needs_review',
        confidence=0.51,
        target_type='report',
        target_id='report_2',
        deps=deps,
    )
    dismiss_item = dismiss_review_item(
        item_id=queued_2['item_id'],
        reviewer_id='reviewer_2',
        operator_note='false positive after manual check',
        deps=deps,
    )

    queued_3 = enqueue_review_item(
        domain='video_homework',
        report_id='submission_7',
        teacher_id='teacher_1',
        reason='provider_attachment_noise',
        confidence=0.28,
        target_type='submission',
        target_id='submission_7',
        deps=deps,
    )
    escalated_item = escalate_review_item(
        item_id=queued_3['item_id'],
        reviewer_id='reviewer_3',
        operator_note='needs multimodal specialist review',
        deps=deps,
    )

    assert retry_item['status'] == 'retry_requested'
    assert retry_item['disposition'] == 'retry_requested'
    assert retry_item['operator_note'] == 'rerun with refreshed bundle'
    assert retry_item['retried_at'] == '2026-03-07T10:00:00'

    assert dismiss_item['status'] == 'dismissed'
    assert dismiss_item['disposition'] == 'dismissed'
    assert dismiss_item['operator_note'] == 'false positive after manual check'
    assert dismiss_item['dismissed_at'] == '2026-03-07T10:00:00'

    assert escalated_item['status'] == 'escalated'
    assert escalated_item['disposition'] == 'escalated'
    assert escalated_item['operator_note'] == 'needs multimodal specialist review'
    assert escalated_item['escalated_at'] == '2026-03-07T10:00:00'


def test_review_queue_persists_strategy_id_across_transitions(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    queued = enqueue_review_item(
        domain='survey',
        report_id='report_1',
        teacher_id='teacher_1',
        reason='low_confidence',
        confidence=0.41,
        target_type='report',
        target_id='report_1',
        strategy_id='survey.teacher.report',
        deps=deps,
    )

    retried = retry_review_item(
        item_id=queued['item_id'],
        reviewer_id='reviewer_1',
        operator_note='rerun with latest prompt',
        deps=deps,
    )
    listed = list_review_items(teacher_id='teacher_1', domain='survey', status=None, deps=deps)

    assert queued['strategy_id'] == 'survey.teacher.report'
    assert retried['strategy_id'] == 'survey.teacher.report'
    assert listed['items'][0]['strategy_id'] == 'survey.teacher.report'



def test_review_queue_terminal_operations_append_feedback_rows(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    queued = enqueue_review_item(
        domain='survey',
        report_id='report_3',
        teacher_id='teacher_1',
        reason='needs_review',
        confidence=0.5,
        target_type='report',
        target_id='report_3',
        strategy_id='survey.teacher.report',
        deps=deps,
    )

    retry_review_item(
        item_id=queued['item_id'],
        reviewer_id='reviewer_1',
        operator_note='rerun with latest prompt',
        deps=deps,
    )
    dismiss_review_item(
        item_id=queued['item_id'],
        reviewer_id='reviewer_1',
        operator_note='false positive after manual check',
        deps=deps,
    )
    escalate_review_item(
        item_id=queued['item_id'],
        reviewer_id='reviewer_2',
        operator_note='needs specialist follow-up',
        deps=deps,
    )

    rows = read_review_feedback_rows(tmp_path / 'analysis' / 'review_feedback.jsonl')
    assert [row['operation'] for row in rows] == ['retry', 'dismiss', 'escalate']
    assert [row['disposition'] for row in rows] == ['retry_requested', 'dismissed', 'escalated']
    assert all(row['strategy_id'] == 'survey.teacher.report' for row in rows)
